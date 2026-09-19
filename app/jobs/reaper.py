"""Background reaper: reclaims expired task leases every 60 seconds."""

import asyncio
import logging

from app.db import async_session
from app.services.task_queue import reclaim_expired_tasks

logger = logging.getLogger(__name__)


async def reaper_loop():
    """Run reaper every 60 seconds until cancelled."""
    while True:
        try:
            async with async_session() as db:
                reclaimed = await reclaim_expired_tasks(db)
                if reclaimed > 0:
                    logger.info("Reaper reclaimed %d expired tasks", reclaimed)
        except Exception:
            logger.exception("Reaper error")
        await asyncio.sleep(60)
