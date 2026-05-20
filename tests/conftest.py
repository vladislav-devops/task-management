"""
Pytest fixtures for the Task Management API test suite.

Provides a test database (SQLite), mocked Redis client, and an async
HTTP client (httpx) for making requests to the FastAPI application.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch

from app.main import app as fastapi_app
from app.database import Base, get_db
from app.models import Task  # noqa: F401 — ensure ORM models are registered

# Use SQLite file-based database for tests (no real PostgreSQL needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def setup_database():
    """Create all tables before the test session and drop them after.

    Session-scoped so that table creation happens only once per
    ``pytest`` invocation, keeping the test suite fast.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def app(setup_database):
    """Override database dependency and mock Redis for each test.

    Sets up FastAPI ``dependency_overrides`` so that every endpoint uses
    the test database session, and patches ``app.routes.get_redis`` with
    an ``AsyncMock`` that provides the expected Redis interface
    (``incr``, ``decr``, ``get``, ``ping``).

    Clears all tasks between tests to guarantee isolation — a test that
    creates tasks won't leak data into the next test.
    """
    # ── Override get_db to use the test session factory ──────────────
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # ── Mock Redis client ────────────────────────────────────────────
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.decr = AsyncMock(return_value=0)
    mock_redis.get = AsyncMock(return_value=b"5")
    mock_redis.ping = AsyncMock(return_value=True)

    # Patch ``get_redis`` inside the routes module (where it is called
    # directly, not via ``Depends``).
    with patch("app.routes.get_redis", return_value=mock_redis):
        # ── Clear any leftover tasks from previous tests ──────────
        async with TestSessionLocal() as session:
            await session.execute(delete(Task))
            await session.commit()

        yield mock_redis

    # Tear down: remove dependency overrides so they don't leak between tests.
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client for testing the FastAPI application.

    Uses ``httpx.AsyncClient`` with ``ASGITransport`` to send requests
    directly to the FastAPI app without starting a real HTTP server.
    """
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
