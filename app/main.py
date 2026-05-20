"""
FastAPI application entry point for the Task Management API.

Uses the modern lifespan pattern (``@asynccontextmanager``) to manage
database and Redis connection lifecycles.  This approach is cleaner than
the deprecated ``on_event`` decorators because it keeps startup and
shutdown logic co-located and plays nicely with async resources.

Start the application::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import close_db, init_db
from app.redis_client import close_redis, init_redis

logger = logging.getLogger(__name__)

# Configure the root logger at startup so that uvicorn / application logs
# respect the level chosen in settings.
logging.basicConfig(level=settings.LOG_LEVEL.upper())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async context manager that handles application startup and shutdown.

    Startup:
        - Initialise the database connection pool and create tables.
        - Initialise the Redis connection and verify connectivity.

    Shutdown:
        - Gracefully close the Redis connection.
        - Dispose of the database engine's connection pool.
    """
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("Task Management API starting up...")
    await init_db()
    await init_redis()
    logger.info("Startup complete — ready to accept requests")
    yield  # ← Application runs while we are suspended here
    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Task Management API shutting down...")
    await close_redis()
    await close_db()
    logger.info("Shutdown complete")


# ── FastAPI Application Instance ───────────────────────────────────────
app = FastAPI(
    title="Task Management API",
    description="REST API for managing tasks — DevOps test assignment",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Register API Routes ────────────────────────────────────────────────
# Import is placed here (rather than at the top) so that the ``app``
# object exists before route modules try to reference it.  In practice
# this is not strictly necessary for an ``APIRouter``, but it follows
# the common FastAPI convention of late-importing route modules.
from app.routes import router  # noqa: E402

app.include_router(router)


@app.get(
    "/",
    summary="Root endpoint",
    description="Returns basic service information and a link to the API documentation.",
    tags=["General"],
)
async def root():
    """Root endpoint — quick check that the service is running.

    Returns:
        dict: Service name, version, and a link to the interactive docs.
    """
    return {
        "service": "Task Management API",
        "version": "1.0.0",
        "docs": "/docs",
    }
