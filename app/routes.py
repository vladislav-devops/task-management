"""
API route handlers for the Task Management API.

Defines all REST endpoints under ``APIRouter``.  Each endpoint uses
``Depends(get_db)`` for database sessions and ``Depends(get_redis)``
for the Redis client.  Redis operations are wrapped in try/except so
that a Redis outage never breaks core task CRUD functionality.

Endpoints:
    * ``POST   /tasks``     – create a new task
    * ``GET    /tasks``     – list all tasks (with optional filters)
    * ``GET    /tasks/{id}`` – get a single task by UUID
    * ``PUT    /tasks/{id}`` – update a task
    * ``DELETE /tasks/{id}`` – delete a task
    * ``GET    /health``    – health-check for DB and Redis
    * ``GET    /stats``     – aggregated task statistics
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import VALID_STATUSES, Task
from app.redis_client import get_redis
from app.schemas import (
    HealthResponse,
    StatsResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)

logger = logging.getLogger(__name__)

# ── Router ─────────────────────────────────────────────────────────────
router = APIRouter(tags=["tasks"])


# ── Helper ─────────────────────────────────────────────────────────────

async def _incr_redis(key: str) -> None:
    """Safely increment a Redis counter, logging warnings on failure.

    This helper wraps every Redis write so that a single catch-all
    try/except protects the application from Redis outages.

    Args:
        key: The Redis key to increment (e.g. ``"api:requests"``).
    """
    try:
        redis = get_redis()
        await redis.incr(key)
    except Exception:
        logger.warning("Redis INCR failed for key=%r", key, exc_info=True)


async def _decr_redis(key: str) -> None:
    """Safely decrement a Redis counter, logging warnings on failure.

    Args:
        key: The Redis key to decrement (e.g. ``"api:tasks_created"``).
    """
    try:
        redis = get_redis()
        await redis.decr(key)
    except Exception:
        logger.warning("Redis DECR failed for key=%r", key, exc_info=True)


async def _get_redis_int(key: str, default: int = 0) -> int:
    """Safely read an integer value from Redis, returning *default* on error.

    Args:
        key: The Redis key to fetch.
        default: Value to return if the key is missing or Redis is down.

    Returns:
        The integer value stored at *key*, or *default*.
    """
    try:
        redis = get_redis()
        value = await redis.get(key)
        return int(value) if value is not None else default
    except Exception:
        logger.warning(
            "Redis GET failed for key=%r, returning default=%d",
            key,
            default,
            exc_info=True,
        )
        return default


# ── Task CRUD Endpoints ────────────────────────────────────────────────


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=201,
    summary="Create a new task",
    description=(
        "Create a task with a unique UUID, initial status (defaults to "
        "`pending`), and automatic timestamps.  Increments Redis counters "
        "`api:requests` and `api:tasks_created`."
    ),
)
async def create_task(
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Create a new task and persist it to the database.

    Args:
        task_in: Validated request body with ``title``, optional
            ``description``, and optional ``status``.
        db: Async database session (injected via ``Depends``).

    Returns:
        The newly created :class:`Task` ORM instance (serialised as
        :class:`TaskResponse`).

    Raises:
        HTTPException 422: If the request body fails Pydantic validation.
    """
    # Build the ORM model from the validated input.  ``model_dump()``
    # includes only fields that were actually provided (via exclude_unset
    # behaviour — but for creation we want all defaults, so use plain dump).
    task_data = task_in.model_dump(exclude_unset=True)
    task = Task(**task_data)

    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info("Task created: id=%s, title=%r", task.id, task.title)

    # Update Redis metrics (non-critical — failure is logged but not raised).
    await _incr_redis("api:requests")
    await _incr_redis("api:tasks_created")

    return task


@router.get(
    "/tasks",
    response_model=list[TaskResponse],
    summary="List all tasks",
    description=(
        "Return every task, ordered by `created_at` descending.  "
        "Optionally filter by `status` and paginate with `skip` / `limit`.  "
        "Increments Redis counter `api:requests`."
    ),
)
async def list_tasks(
    status: str | None = Query(
        None,
        description="Filter tasks by status (pending, in_progress, completed).",
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip (offset)."),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return.",
    ),
    db: AsyncSession = Depends(get_db),
) -> list[Task]:
    """List tasks with optional filtering and pagination.

    Args:
        status: If provided, only tasks matching this status are returned.
        skip: Offset for pagination (default 0).
        limit: Page size (default 100, max 1000).
        db: Async database session.

    Returns:
        A list of :class:`Task` instances.
    """
    from sqlalchemy import select

    stmt = select(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit)

    if status is not None:
        # Only allow known status values to avoid silently returning an
        # empty list for a typo like ``?status=pendin``.
        if status not in VALID_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid status '{status}'. "
                    f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
                ),
            )
        stmt = stmt.where(Task.status == status)

    result = await db.execute(stmt)
    tasks = list(result.scalars().all())

    await _incr_redis("api:requests")
    return tasks


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Get a single task",
    description=(
        "Retrieve a task by its UUID.  Returns 404 if the task does not exist.  "
        "Increments Redis counter `api:requests`."
    ),
)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Fetch a single task by its primary key.

    Args:
        task_id: UUID of the task to retrieve (validated automatically by
            FastAPI's type system).
        db: Async database session.

    Returns:
        The matching :class:`Task`.

    Raises:
        HTTPException 404: No task with the given UUID exists.
    """
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    await _incr_redis("api:requests")
    return task


@router.put(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
    description=(
        "Partially update a task.  Only fields present in the request body "
        "are modified — omit a field to leave it unchanged.  Increments Redis "
        "counters `api:requests` and `api:tasks_updated`."
    ),
)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Update an existing task's fields.

    Uses ``model_dump(exclude_unset=True)`` so that only the fields the
    client explicitly sent are applied.  This means sending
    ``{"title": "New"}`` updates only the title; all other fields remain
    untouched.  (Using ``exclude_none=True`` would incorrectly treat an
    explicit ``null`` description as "not set".)

    Args:
        task_id: UUID of the task to update.
        task_update: Request body with optional ``title``, ``description``,
            and/or ``status``.
        db: Async database session.

    Returns:
        The updated :class:`Task`.

    Raises:
        HTTPException 404: No task with the given UUID exists.
    """
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # ``exclude_unset=True`` ensures only fields the client actually
    # provided are applied.  Fields that were not sent at all are skipped.
    update_data = task_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(task, field, value)

    await db.commit()
    await db.refresh(task)

    logger.info(
        "Task updated: id=%s, fields=%s",
        task.id,
        list(update_data.keys()),
    )

    await _incr_redis("api:requests")
    await _incr_redis("api:tasks_updated")

    return task


@router.delete(
    "/tasks/{task_id}",
    status_code=200,
    summary="Delete a task",
    description=(
        "Permanently remove a task by UUID.  Decrements `api:tasks_created` "
        "in Redis to keep aggregate counters consistent, and increments "
        "`api:requests` and `api:tasks_deleted`."
    ),
)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a task from the database.

    Args:
        task_id: UUID of the task to delete.
        db: Async database session.

    Returns:
        A confirmation message.

    Raises:
        HTTPException 404: No task with the given UUID exists.
    """
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()

    logger.info("Task deleted: id=%s, title=%r", task.id, task.title)

    # Decrement tasks_created so the stats endpoint reflects reality.
    await _decr_redis("api:tasks_created")
    await _incr_redis("api:requests")
    await _incr_redis("api:tasks_deleted")

    return {"detail": "Task deleted successfully"}


# ── Health Check ───────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Verify that the service and its dependencies (database, Redis) "
        "are operational.  Returns 200 even when one dependency is down; "
        "the individual service statuses indicate what is healthy."
    ),
)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Check the health of the service and its dependencies.

    Performs a lightweight ``SELECT 1`` against the database and a
    ``PING`` against Redis.  Failures are caught individually so that
    one down dependency does not mask the status of the other.

    Args:
        db: Async database session.

    Returns:
        :class:`HealthResponse` with per-service status strings.
    """
    # ── Database check ───────────────────────────────────────────────
    db_status: str
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.exception("Database health check failed")
        db_status = "disconnected"

    # ── Redis check ──────────────────────────────────────────────────
    redis_status: str
    try:
        r = get_redis()
        await r.ping()
        redis_status = "connected"
    except Exception:
        logger.exception("Redis health check failed")
        redis_status = "disconnected"

    # ── Overall status ───────────────────────────────────────────────
    overall = "healthy" if db_status == "connected" and redis_status == "connected" else "unhealthy"

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc),
    )


# ── Statistics ─────────────────────────────────────────────────────────


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Task statistics",
    description=(
        "Return aggregated task counts grouped by status, plus Redis-backed "
        "API usage counters.  Useful for monitoring dashboards."
    ),
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Aggregate task counts and return API usage stats.

    Queries the database for per-status counts and reads Redis counters
    for API usage metrics.

    Args:
        db: Async database session.

    Returns:
        :class:`StatsResponse` with all fields populated.
    """
    from sqlalchemy import func, select

    # ── Per-status counts from the database ──────────────────────────
    # Run three lightweight COUNT queries, one per status.  For small
    # datasets this is fine; for larger ones a single GROUP BY query
    # would be more efficient, but the three-query approach is simpler
    # and works well with the existing VALID_STATUSES set.
    stmt_pending = select(func.count()).where(Task.status == "pending")
    stmt_in_progress = select(func.count()).where(Task.status == "in_progress")
    stmt_completed = select(func.count()).where(Task.status == "completed")

    pending_count = (await db.execute(stmt_pending)).scalar() or 0
    in_progress_count = (await db.execute(stmt_in_progress)).scalar() or 0
    completed_count = (await db.execute(stmt_completed)).scalar() or 0

    total_tasks = pending_count + in_progress_count + completed_count

    # ── Redis API counters (fall back to 0 if Redis is unreachable) ──
    api_requests = await _get_redis_int("api:requests")
    tasks_created = await _get_redis_int("api:tasks_created")
    tasks_updated = await _get_redis_int("api:tasks_updated")
    tasks_deleted = await _get_redis_int("api:tasks_deleted")

    logger.info(
        "Stats: total=%d, pending=%d, in_progress=%d, completed=%d, "
        "api_requests=%d",
        total_tasks,
        pending_count,
        in_progress_count,
        completed_count,
        api_requests,
    )

    return StatsResponse(
        total_tasks=total_tasks,
        pending_tasks=pending_count,
        in_progress_tasks=in_progress_count,
        completed_tasks=completed_count,
        api_requests=api_requests,
    )
