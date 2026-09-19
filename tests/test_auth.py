import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "secret123",
            "display_name": "Test User",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"
    token = data["access_token"]

    # Duplicate register -> 409
    resp2 = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "secret123",
            "display_name": "Test User",
        },
    )
    assert resp2.status_code == 409

    # Login
    resp3 = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "secret123",
        },
    )
    assert resp3.status_code == 200
    assert "access_token" in resp3.json()

    # Wrong password -> 401
    resp4 = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrong",
        },
    )
    assert resp4.status_code == 401

    # /me
    resp5 = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp5.status_code == 200
    assert resp5.json()["email"] == "test@example.com"

    # /me without token -> 403
    resp6 = await client.get("/api/auth/me")
    assert resp6.status_code == 403
