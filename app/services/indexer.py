"""Indexer provider: JacRed (Torznab) search."""

import hashlib
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.quality import parse_release_info

logger = logging.getLogger(__name__)


@dataclass
class Release:
    title: str
    tracker: str
    info_hash: str
    size_bytes: int
    seeders: int
    leechers: int
    quality: str | None
    voiceover: str | None
    magnet: str | None
    source: str


async def search_releases(query: str, media_item_id: str) -> list[Release]:
    url = f"{settings.JACRED_URL.rstrip('/')}/api/v2.0/indexers/all/results"
    params = {
        "apikey": settings.JACRED_API_KEY,
        "Query": query,
        "Category[]": "2000",  # movies; will add 5000 for TV
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    releases = []
    for item in data.get("Results", []):
        title = item.get("Title", "")
        parsed = parse_release_info(title)

        info_hash = ""
        magnet = item.get("MagnetUri") or item.get("Link") or ""
        magnet_match = re.search(r"btih:([a-fA-F0-9]{40})", magnet)
        if magnet_match:
            info_hash = magnet_match.group(1).lower()
        elif item.get("Guid"):
            info_hash = hashlib.sha1(item["Guid"].encode()).hexdigest()

        releases.append(
            Release(
                title=title,
                tracker=item.get("Tracker", "unknown"),
                info_hash=info_hash,
                size_bytes=item.get("Size", 0),
                seeders=item.get("Seeders", 0),
                leechers=item.get("Peers", 0) - item.get("Seeders", 0),
                quality=parsed["quality"],
                voiceover=parsed["voiceover"],
                magnet=magnet if magnet.startswith("magnet:") else None,
                source="jacred",
            )
        )
    return releases