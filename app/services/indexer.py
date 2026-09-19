"""Indexer provider: mock fixtures or Jackett (Torznab) search."""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Protocol

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
    source: str  # 'mock' or 'jackett'


class IndexerProvider(Protocol):
    async def search(self, query: str, media_item_id: str) -> list[Release]: ...


class MockProvider:
    """Deterministic mock releases for development without network."""

    async def search(self, query: str, media_item_id: str) -> list[Release]:
        base = f"{query}|{media_item_id}"
        releases = []
        configs = [
            ("1080p WEB-DL LostFilm", 4_500_000_000, 150, 10),
            ("720p BDRip JASKIER", 2_100_000_000, 80, 5),
            ("2160p WEB-DL HDrezka Studio", 12_000_000_000, 45, 3),
            ("1080p HDTVRip NewStudio", 3_800_000_000, 200, 15),
        ]
        for i, (title_suffix, size, seeders, leechers) in enumerate(configs):
            raw = f"{base}|{i}"
            info_hash = hashlib.sha1(raw.encode()).hexdigest()
            parsed = parse_release_info(title_suffix)
            releases.append(
                Release(
                    title=f"{query} [{title_suffix}]",
                    tracker="mock",
                    info_hash=info_hash,
                    size_bytes=size,
                    seeders=seeders,
                    leechers=leechers,
                    quality=parsed["quality"],
                    voiceover=parsed["voiceover"],
                    magnet=f"magnet:?xt=urn:btih:{info_hash}",
                    source="mock",
                )
            )
        return releases


class JackettProvider:
    """Search via Jackett Torznab API."""

    async def search(self, query: str, media_item_id: str) -> list[Release]:
        url = f"{settings.JACKETT_URL.rstrip('/')}/api/v2.0/indexers/all/results"
        params = {
            "apikey": settings.JACKETT_API_KEY,
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

            # Extract info_hash from magnet or GUID
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
                    source="jackett",
                )
            )
        return releases


def get_indexer() -> IndexerProvider:
    if settings.INDEXER_PROVIDER == "jackett":
        return JackettProvider()
    return MockProvider()
