"""
Database module — async SQLAlchemy engine, session factory, and helpers.

Provides the async session dependency (``get_db``) for FastAPI endpoints
as well as lifecycle functions for initialising and tearing down the
database connection pool.

Usage::

    from app.database import get_db, init_db, close_db

    # During application startup:
    await init_db()

    # In a FastAPI route:
    @router.get("/tasks")
    async def list_tasks(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

# ── Engine ────────────────────────────────────────────────────────────
# The async engine manages the connection pool.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True during debugging to see SQL queries
    pool_pre_ping=True,  # Verify connections before using them
)

# ── Session Factory ───────────────────────────────────────────────────
# Each call to ``async_session_maker()`` produces a new AsyncSession.
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
)

# ── Declarative Base ──────────────────────────────────────────────────
# All ORM models inherit from this class.
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically closed when the request finishes,
    even if an exception occurs.

    Yields:
        An :class:`AsyncSession` bound to the application engine.
    """
    async with async_session_maker() as session:
        try:
            yield session
            logger.debug("Database session yielded successfully")
        except Exception:
            logger.exception("Database session rolled back due to error")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all database tables that do not yet exist.

    Safe to call on every application startup — existing tables are
    left untouched.  The ``Base.metadata`` is automatically populated
    when ORM model modules are imported.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified")


async def close_db() -> None:
    """Dispose of the engine's connection pool.

    Call during application shutdown to release all pooled connections.
    """
    await engine.dispose()
    logger.info("Database engine disposed")
