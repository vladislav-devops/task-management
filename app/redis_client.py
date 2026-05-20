"""
Redis client module — async Redis connection, lifecycle, and accessor.

Manages a module-level ``redis_client`` instance that is initialised
at application startup and torn down at shutdown.  All other modules
obtain the client through ``get_redis()``.

Usage::

    from app.redis_client import get_redis, init_redis, close_redis

    # During application startup:
    await init_redis()

    # In a FastAPI route:
    r = get_redis()
    await r.set("key", "value")
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level Redis client ────────────────────────────────────────
# Initialised as ``None``; call ``init_redis()`` before first use.
redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """Create the async Redis client and verify connectivity.

    Assigns the new client to the module-level ``redis_client`` variable
    and sends a ``PING`` command to confirm the connection is healthy.

    Raises:
        redis.exceptions.ConnectionError: If Redis is unreachable.
    """
    global redis_client

    logger.info(
        "Connecting to Redis at %s:%d ...",
        settings.REDIS_HOST,
        settings.REDIS_PORT,
    )

    redis_client = aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
        max_connections=20,
    )

    # Verify the connection immediately so misconfiguration is caught
    # at startup rather than on the first request.
    await redis_client.ping()
    logger.info("Redis connection established and verified (PING OK)")


async def close_redis() -> None:
    """Gracefully close the Redis connection.

    Safe to call even if ``init_redis()`` was never invoked; silently
    returns when ``redis_client`` is ``None``.
    """
    global redis_client

    if redis_client is not None:
        await redis_client.close()
        redis_client = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Return the global Redis client instance.

    Returns:
        The active :class:`redis.asyncio.Redis` client.

    Raises:
        RuntimeError: If ``init_redis()`` has not been called yet.
    """
    if redis_client is None:
        raise RuntimeError(
            "Redis client is not initialised. Call init_redis() first."
        )
    return redis_client
