import uuid

import pytest_asyncio

from app.db import async_session, engine
from app.models.invite_key import InviteKey


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine():
    """Drop pooled connections after each test.

    pytest-asyncio creates a new event loop per test; the shared async engine
    must not hand a connection created on a previous loop to the next one.
    """
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def invite_key() -> str:
    key = uuid.uuid4().hex
    async with async_session() as session:
        invite = InviteKey(key=key, created_by=None)
        session.add(invite)
        await session.commit()
    return key
