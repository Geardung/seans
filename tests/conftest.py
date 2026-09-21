import uuid

import pytest_asyncio

from app.db import async_session
from app.models.invite_key import InviteKey


@pytest_asyncio.fixture
async def invite_key() -> str:
    key = uuid.uuid4().hex
    async with async_session() as session:
        invite = InviteKey(key=key, created_by=uuid.uuid4())
        session.add(invite)
        await session.commit()
    return key