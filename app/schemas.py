"""
Pydantic schemas — request/response validation models.

These schemas define the shape of data that the API accepts and returns.
They are used by FastAPI for automatic request validation, serialisation,
and OpenAPI documentation generation.

Schemas:
    * :class:`TaskCreate`     – payload for creating a new task
    * :class:`TaskUpdate`     – payload for updating an existing task
    * :class:`TaskResponse`   – task representation returned by the API
    * :class:`HealthResponse` – health-check endpoint response
    * :class:`StatsResponse`  – aggregated task statistics
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import VALID_STATUSES

logger = logging.getLogger(__name__)


# ── Helper ────────────────────────────────────────────────────────────

def _validate_status(value: str, field_name: str) -> str:
    """Ensure the status value belongs to the allowed set."""
    if value not in VALID_STATUSES:
        raise ValueError(
            f"'{value}' is not a valid status for '{field_name}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
    return value


# ── Task Schemas ──────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    """Schema for creating a new task.

    Only ``title`` is required.  ``description`` and ``status`` are
    optional; if ``status`` is omitted it defaults to ``"pending"``.
    """

    title: str = Field(
        ...,
        min_length=1,
        description="Task title (required, at least 1 character).",
        examples=["Set up CI/CD pipeline"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional longer description of the task.",
        examples=["Configure GitHub Actions to run tests on every push."],
    )
    status: Optional[str] = Field(
        None,
        description="Task status. Defaults to 'pending' if not provided.",
        examples=["pending"],
    )

    @field_validator("status")
    @classmethod
    def validate_status_field(cls, value: Optional[str]) -> Optional[str]:
        """Validate the status field, allowing ``None`` (treated as default)."""
        if value is None:
            return value  # Models.py will apply the default
        return _validate_status(value, "status")


class TaskUpdate(BaseModel):
    """Schema for updating an existing task.

    All fields are optional — only the provided fields will be updated.
    """

    title: Optional[str] = Field(
        None,
        min_length=1,
        description="New task title.",
        examples=["Update CI/CD pipeline"],
    )
    description: Optional[str] = Field(
        None,
        description="New task description.",
    )
    status: Optional[str] = Field(
        None,
        description="New task status.",
        examples=["in_progress"],
    )

    @field_validator("status")
    @classmethod
    def validate_status_field(cls, value: Optional[str]) -> Optional[str]:
        """Validate the status field when provided."""
        if value is None:
            return value
        return _validate_status(value, "status")


class TaskResponse(BaseModel):
    """Schema for a task returned by the API.

    Enables ORM-mode serialisation so that SQLAlchemy model instances
    can be returned directly from endpoints.
    """

    id: UUID = Field(
        ...,
        description="Unique task identifier (UUID).",
    )
    title: str = Field(
        ...,
        description="Task title.",
    )
    description: Optional[str] = Field(
        None,
        description="Task description, if any.",
    )
    status: str = Field(
        ...,
        description="Current task status.",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp of task creation.",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp of last modification.",
    )

    model_config = ConfigDict(from_attributes=True)


# ── Health / Stats Schemas ────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Schema for the health-check endpoint.

    Reports the health of the service and its dependencies.
    """

    status: str = Field(
        ...,
        description="Overall service health: 'healthy' or 'unhealthy'.",
        examples=["healthy"],
    )
    database: str = Field(
        ...,
        description="Database connectivity status.",
        examples=["connected"],
    )
    redis: str = Field(
        ...,
        description="Redis connectivity status.",
        examples=["connected"],
    )
    timestamp: datetime = Field(
        ...,
        description="UTC timestamp of the health check.",
    )


class StatsResponse(BaseModel):
    """Schema for the task statistics endpoint.

    Aggregated counts of tasks grouped by status, plus a counter of
    total API requests served (tracked via Redis).
    """

    total_tasks: int = Field(
        ...,
        description="Total number of tasks in the database.",
        examples=[42],
    )
    pending_tasks: int = Field(
        ...,
        description="Number of tasks with status 'pending'.",
        examples=[10],
    )
    in_progress_tasks: int = Field(
        ...,
        description="Number of tasks with status 'in_progress'.",
        examples=[15],
    )
    completed_tasks: int = Field(
        ...,
        description="Number of tasks with status 'completed'.",
        examples=[17],
    )
    api_requests: int = Field(
        ...,
        description="Total number of API requests served (from Redis counter).",
        examples=[1280],
    )
