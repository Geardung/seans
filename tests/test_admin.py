"""Admin API: quota override, plan assignment, plan expiry."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db import async_session
from app.main import app
from app.models.invite_key import InviteKey
from app.models.user import User
from app.services.plans import PLANS
from app.services.quota import get_effective_quota_bytes


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_invite_key() -> str:
    key = uuid.uuid4().hex
    async with async_session() as session:
        session.add(InviteKey(key=key, created_by=None))
        await session.commit()
    return key


async def _register(client: AsyncClient) -> tuple[str, str]:
    invite = await _create_invite_key()
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": f"admin-test-{uuid.uuid4().hex[:8]}@test.local",
            "password": "test123",
            "display_name": "Admin Tester",
            "invite_key": invite,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["access_token"], data["user"]["id"]


async def _set_admin(user_id: str, is_admin: bool = True) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one()
        user.is_admin = is_admin
        await session.commit()


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_api(client: AsyncClient):
    token, _ = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 403

    resp = await client.patch(
        f"/api/admin/users/{uuid.uuid4()}", headers=headers, json={"quota_bytes": 1}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_expand_quota_and_set_can_invite(client: AsyncClient):
    admin_token, admin_id = await _register(client)
    await _set_admin(admin_id)
    user_token, user_id = await _register(client)

    # Default quota
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["quota_bytes"] == PLANS["free"].quota_bytes

    # Expand quota via admin PATCH
    resp = await client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"quota_bytes": 100_000, "can_invite": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quota_bytes"] == 100_000
    assert body["effective_quota_bytes"] == 100_000
    assert body["can_invite"] is True

    # User sees the new quota
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.json()["quota_bytes"] == 100_000


@pytest.mark.asyncio
async def test_plan_assignment_sets_quota(client: AsyncClient):
    admin_token, admin_id = await _register(client)
    await _set_admin(admin_id)
    _, user_id = await _register(client)

    resp = await client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan": "plus", "plan_expires_at": None},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "plus"
    assert body["plan_expires_at"] is None
    assert body["quota_bytes"] == PLANS["plus"].quota_bytes
    assert body["effective_quota_bytes"] == PLANS["plus"].quota_bytes

    # Custom quota together with plan wins over plan default
    resp = await client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan": "pro", "quota_bytes": 555},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "pro"
    assert body["quota_bytes"] == 555
    assert body["effective_quota_bytes"] == 555


@pytest.mark.asyncio
async def test_unknown_plan_rejected(client: AsyncClient):
    admin_token, admin_id = await _register(client)
    await _set_admin(admin_id)
    _, user_id = await _register(client)

    resp = await client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan": "gold"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_expired_plan_falls_back_to_free(client: AsyncClient):
    admin_token, admin_id = await _register(client)
    await _set_admin(admin_id)
    user_token, user_id = await _register(client)

    expired = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    resp = await client.patch(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan": "pro", "plan_expires_at": expired},
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "pro"

    # Effective quota is free even though stored quota_bytes is pro's
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.json()["quota_bytes"] == PLANS["free"].quota_bytes

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one()
        assert get_effective_quota_bytes(user) == PLANS["free"].quota_bytes
        assert user.quota_bytes == PLANS["pro"].quota_bytes


@pytest.mark.asyncio
async def test_admin_lists_plans_and_users(client: AsyncClient):
    admin_token, admin_id = await _register(client)
    await _set_admin(admin_id)
    _, user_id = await _register(client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = await client.get("/api/admin/plans", headers=headers)
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert {"free", "plus", "pro"} <= codes

    resp = await client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 200
    users = resp.json()
    assert any(u["id"] == user_id for u in users)
    sample = next(u for u in users if u["id"] == user_id)
    assert "effective_quota_bytes" in sample
    assert "used_bytes" in sample

    resp = await client.get(f"/api/admin/users/{user_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(client: AsyncClient):
    admin_token, admin_id = await _register(client)
    await _set_admin(admin_id)

    resp = await client.patch(
        f"/api/admin/users/{admin_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_admin": False},
    )
    assert resp.status_code == 400
