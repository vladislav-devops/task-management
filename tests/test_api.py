"""
API tests for the Task Management API.

Covers health, CRUD, filtering, and stats endpoints using an in-memory
SQLite database and a mocked Redis client so that no real infrastructure
is required.

All test functions are ``async`` and use ``httpx.AsyncClient`` with
``ASGITransport`` to communicate with the FastAPI application directly.
"""
import pytest
from uuid import uuid4


# ═══════════════════════════════════════════════════════════════════════
# Health Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    """Tests for ``GET /health`` and ``GET /``."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """``GET /health`` must return HTTP 200 when dependencies are mocked."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_structure(self, client):
        """``GET /health`` response JSON must contain the expected top-level keys."""
        response = await client.get("/health")
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """``GET /`` must return service information with expected fields."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Task Management API"
        assert data["version"] == "1.0.0"
        assert "docs" in data


# ═══════════════════════════════════════════════════════════════════════
# Create Task
# ═══════════════════════════════════════════════════════════════════════


class TestCreateTask:
    """Tests for ``POST /tasks``."""

    @pytest.mark.asyncio
    async def test_create_task_valid(self, client):
        """Creating a task with title and description returns 201 with correct shape."""
        payload = {"title": "Test Task", "description": "A test"}
        response = await client.post("/tasks", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] == "Test Task"
        assert data["description"] == "A test"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_task_minimal(self, client):
        """Creating a task with only a title defaults description to None."""
        payload = {"title": "Minimal"}
        response = await client.post("/tasks", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Minimal"
        assert data["description"] is None

    @pytest.mark.asyncio
    async def test_create_task_empty_title(self, client):
        """An empty title must be rejected with HTTP 422."""
        payload = {"title": ""}
        response = await client.post("/tasks", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_invalid_status(self, client):
        """A status outside the allowed set must be rejected with HTTP 422."""
        payload = {"title": "X", "status": "invalid"}
        response = await client.post("/tasks", json=payload)
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Get Tasks
# ═══════════════════════════════════════════════════════════════════════


class TestGetTasks:
    """Tests for ``GET /tasks`` and ``GET /tasks/{id}``."""

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client):
        """Listing tasks on a clean database must return an empty array."""
        response = await client.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_tasks_with_items(self, client):
        """Listing tasks after creating three must return exactly three items."""
        for i in range(3):
            await client.post("/tasks", json={"title": f"Task {i}"})
        response = await client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, client):
        """Fetching a task by its UUID must return the matching task."""
        create_resp = await client.post("/tasks", json={"title": "Fetch Me"})
        task_id = create_resp.json()["id"]
        response = await client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["id"] == task_id
        assert response.json()["title"] == "Fetch Me"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client):
        """Requesting a non-existent UUID must return HTTP 404."""
        response = await client.get(f"/tasks/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client):
        """Filtering by ``status=completed`` must return only completed tasks."""
        # Create one pending and two completed tasks
        await client.post("/tasks", json={"title": "Pending Task", "status": "pending"})
        await client.post(
            "/tasks", json={"title": "Done 1", "status": "completed"}
        )
        await client.post(
            "/tasks", json={"title": "Done 2", "status": "completed"}
        )

        response = await client.get("/tasks", params={"status": "completed"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(t["status"] == "completed" for t in data)


# ═══════════════════════════════════════════════════════════════════════
# Update Task
# ═══════════════════════════════════════════════════════════════════════


class TestUpdateTask:
    """Tests for ``PUT /tasks/{id}``."""

    @pytest.mark.asyncio
    async def test_update_task_title(self, client):
        """Updating only the title must preserve the old description."""
        create_resp = await client.post(
            "/tasks", json={"title": "Original", "description": "Keep me"}
        )
        task_id = create_resp.json()["id"]

        response = await client.put(
            f"/tasks/{task_id}", json={"title": "Updated"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["description"] == "Keep me"

    @pytest.mark.asyncio
    async def test_update_task_status(self, client):
        """Updating the status to ``in_progress`` must be reflected in the response."""
        create_resp = await client.post("/tasks", json={"title": "Progress Me"})
        task_id = create_resp.json()["id"]

        response = await client.put(
            f"/tasks/{task_id}", json={"status": "in_progress"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, client):
        """Updating a non-existent task must return HTTP 404."""
        response = await client.put(
            f"/tasks/{uuid4()}", json={"title": "Ghost"}
        )
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Delete Task
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteTask:
    """Tests for ``DELETE /tasks/{id}``."""

    @pytest.mark.asyncio
    async def test_delete_task(self, client):
        """Deleting a task must succeed and a subsequent GET must return 404."""
        create_resp = await client.post("/tasks", json={"title": "Delete Me"})
        task_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/tasks/{task_id}")
        assert delete_resp.status_code == 200

        get_resp = await client.get(f"/tasks/{task_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, client):
        """Deleting a non-existent task must return HTTP 404."""
        response = await client.delete(f"/tasks/{uuid4()}")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Stats Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestStatsEndpoint:
    """Tests for ``GET /stats``."""

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, client):
        """The stats endpoint must return 200 with all expected aggregate fields."""
        response = await client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_tasks" in data
        assert "pending_tasks" in data
        assert "in_progress_tasks" in data
        assert "completed_tasks" in data
        assert "api_requests" in data
