"""
Configuration module — environment-driven settings via Pydantic BaseSettings.

All values are read from environment variables or a ``.env`` file placed
in the project root.  Sensible defaults are provided so the application
can start with zero configuration for local development.

Usage::

    from app.config import settings
    print(settings.DATABASE_URL)
"""

from __future__ import annotations

import logging

from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings sourced from environment / ``.env`` file.

    Environment variables take precedence over the ``.env`` file.
    All names are case-sensitive.

    Attributes:
        DATABASE_URL: Async PostgreSQL connection string.
        REDIS_HOST: Redis server hostname or IP address.
        REDIS_PORT: Redis server TCP port.
        APP_PORT: Port the FastAPI application listens on.
        LOG_LEVEL: Python logging level string (e.g. ``INFO``, ``DEBUG``).
        REDIS_URL: Computed Redis connection URL (property).
    """

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://user:pass@db:5432/tasksdb"
    )

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # ── Application ───────────────────────────────────────────────────
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    @property
    def REDIS_URL(self) -> str:
        """Build the Redis connection URL from host and port."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# Singleton settings instance – import this throughout the application.
settings = Settings()

db_url = urlparse(settings.DATABASE_URL)
masked_db = db_url._replace(
    netloc=db_url.netloc.replace(f":{db_url.password}@", ":***@") #making password invisible
) if db_url.password else db_url

logger.info(
    "Settings loaded (DB=%s, Redis=%s:%d, Port=%d)",
    masked_db.geturl(),
    settings.REDIS_HOST,
    settings.REDIS_PORT,
    settings.APP_PORT,
)
