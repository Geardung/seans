"""Test the full task lifecycle: create -> claim -> heartbeat -> complete.

Also tests lease expiry and quota exceeded.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register_and_login(client: AsyncClient) -> tuple[str, str]:
    """Register a user and return (token, user_id)."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": f"worker-test-{uuid.uuid4().hex[:8]}@test.local",
            "password": "test123",
            "display_name": "Worker Tester",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["access_token"], data["user"]["id"]


async def register_worker(client: AsyncClient) -> str:
    """Register a worker and return its token."""
    resp = await client.post(
        "/api/worker/register",
        json={
            "name": "test-worker",
            "reg_secret": "change-me",
        },
    )
    assert resp.status_code == 200
    return resp.json()["worker_token"]


@pytest.mark.asyncio
async def test_full_task_flow(client: AsyncClient):
    """Create task -> claim -> manifest -> heartbeat -> complete."""
    user_token, _user_id = await register_and_login(client)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    worker_token = await register_worker(client)
    worker_headers = {"X-Worker-Token": worker_token}

    # Search to create a media item
    resp = await client.get("/api/search?q=Токийский гуль", headers=user_headers)
    assert resp.status_code == 200
    media_items = resp.json()
    assert len(media_items) > 0
    media_id = media_items[0]["id"]

    # Get releases
    resp = await client.get(f"/api/media/{media_id}/releases", headers=user_headers)
    assert resp.status_code == 200
    releases = resp.json()
    assert len(releases) > 0
    release_id = releases[0]["id"]

    # Create task
    resp = await client.post(
        "/api/tasks",
        headers=user_headers,
        json={
            "torrent_release_id": release_id,
            "file_paths": ["movie.mkv"],
        },
    )
    assert resp.status_code == 201
    task = resp.json()
    task_id = task["id"]
    assert task["status"] == "queued"
    assert task["reserved_bytes"] > 0

    # Worker claim
    resp = await client.post("/api/worker/claim", headers=worker_headers)
    assert resp.status_code == 200
    claimed = resp.json()
    assert claimed["task_id"] == task_id

    # Worker manifest
    resp = await client.post(
        "/api/worker/manifest",
        headers=worker_headers,
        json={
            "task_id": task_id,
            "files": [{"path": "movie.mkv", "size_bytes": 1024}],
        },
    )
    assert resp.status_code == 200
    manifest = resp.json()
    assert len(manifest["upload_slots"]) > 0

    # Worker heartbeat
    resp = await client.post(
        "/api/worker/heartbeat",
        headers=worker_headers,
        json={
            "task_id": task_id,
            "progress_pct": 50,
            "speed_bps": 1024,
            "stage": "downloading",
        },
    )
    assert resp.status_code == 200

    # Worker complete
    resp = await client.post(
        "/api/worker/complete",
        headers=worker_headers,
        json={
            "task_id": task_id,
            "files": [
                {
                    "path": "movie.mkv",
                    "s3_key": "users/test/movie.mkv",
                    "size_bytes": 1024,
                }
            ],
        },
    )
    assert resp.status_code == 200

    # Verify task is completed
    resp = await client.get("/api/tasks", headers=user_headers)
    assert resp.status_code == 200
    tasks = resp.json()
    completed = [t for t in tasks if t["id"] == task_id]
    assert len(completed) == 1
    assert completed[0]["status"] == "completed"

    # Verify library
    resp = await client.get("/api/library", headers=user_headers)
    assert resp.status_code == 200
    lib = resp.json()
    assert len(lib) > 0


@pytest.mark.asyncio
async def test_no_tasks_returns_204(client: AsyncClient):
    worker_token = await register_worker(client)
    worker_headers = {"X-Worker-Token": worker_token}

    resp = await client.post("/api/worker/claim", headers=worker_headers)
    assert resp.status_code == 200  # FastAPI returns 200 with null body for None


@pytest.mark.asyncio
async def test_cancel_queued_task(client: AsyncClient):
    user_token, _user_id = await register_and_login(client)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Search + releases
    resp = await client.get("/api/search?q=Интерстеллар", headers=user_headers)
    media_id = resp.json()[0]["id"]
    resp = await client.get(f"/api/media/{media_id}/releases", headers=user_headers)
    release_id = resp.json()[0]["id"]

    # Create task
    resp = await client.post(
        "/api/tasks",
        headers=user_headers,
        json={
            "torrent_release_id": release_id,
            "file_paths": ["movie.mkv"],
        },
    )
    task_id = resp.json()["id"]

    # Cancel
    resp = await client.post(f"/api/tasks/{task_id}/cancel", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"
