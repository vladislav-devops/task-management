"""
ORM models — SQLAlchemy declarative mapping for the ``tasks`` table.

Defines the :class:`Task` entity that represents a single task in the
task management system.

Status values:
    * ``pending``       – task has been created but work hasn't started
    * ``in_progress``   – task is actively being worked on
    * ``completed``     – task is done
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

logger = logging.getLogger(__name__)

# Canonical set of allowed task statuses.
VALID_STATUSES = frozenset({"pending", "in_progress", "completed"})


class Task(Base):
    """Represents a single task in the system.

    Each task has a unique UUID primary key, a required title, an
    optional longer description, a status (one of ``pending``,
    ``in_progress``, ``completed``), and automatic creation / update
    timestamps.
    """

    __tablename__ = "tasks"

    # ── Columns ───────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the task (UUID v4).",
    )
    title = Column(
        String(255),
        nullable=False,
        doc="Short task title (required, max 255 characters).",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Optional longer description of the task.",
    )
    status = Column(
        String(50),
        default="pending",
        nullable=False,
        doc="Current task status. One of: pending, in_progress, completed.",
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the task was created (UTC).",
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the task was last modified (UTC).",
    )

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return (
            f"<Task(id={self.id!r}, title={self.title!r}, "
            f"status={self.status!r})>"
        )
