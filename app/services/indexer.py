"""Indexer provider: JacRed search.

Primary — external REST (`/api/search`, Bearer key).
Fallback — local JacRed (Jackett-compatible `/api/v2.0/indexers/all/results`).
"""

import hashlib
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.quality import parse_release_info

logger = logging.getLogger(__name__)

_SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "KIB": 1024,
    "MB": 1024**2,
    "MIB": 1024**2,
    "GB": 1024**3,
    "GIB": 1024**3,
    "TB": 1024**4,
    "TIB": 1024**4,
}

_SIZE_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([KMGT]?I?B)\s*$", re.IGNORECASE)
_BTIF_RE = re.compile(r"btih:([a-fA-F0-9]{40})")


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


def parse_size_name(size_name: str | None) -> int:
    """Parse human size like '11.81 GB' into bytes (binary units)."""
    if not size_name:
        return 0
    match = _SIZE_RE.match(str(size_name))
    if not match:
        return 0
    number = float(match.group(1).replace(",", "."))
    unit = match.group(2).upper()
    return int(number * _SIZE_UNITS[unit])


def _info_hash_from_magnet(magnet: str, guid: str | None = "") -> str:
    if magnet:
        match = _BTIF_RE.search(magnet)
        if match:
            return match.group(1).lower()
    if guid:
        return hashlib.sha1(guid.encode()).hexdigest()
    return ""


def _external_configured() -> bool:
    return bool(
        settings.JACRED_EXTERNAL_URL
        and settings.JACRED_EXTERNAL_URL.strip()
        and settings.JACRED_EXTERNAL_API_KEY
        and settings.JACRED_EXTERNAL_API_KEY.strip()
    )


def _map_external_item(item: dict) -> Release:
    title = item.get("title") or item.get("Title") or ""
    parsed = parse_release_info(title)
    magnet = item.get("magnet") or item.get("MagnetUri") or ""
    if magnet and not magnet.startswith("magnet:"):
        magnet = ""
    seeders = int(item.get("seeders") or item.get("Seeders") or 0)
    # External API: `peers` is leechers (can be lower than seeders).
    leechers = int(item.get("peers") or item.get("Peers") or 0)
    return Release(
        title=title,
        tracker=item.get("tracker") or item.get("Tracker") or "unknown",
        info_hash=_info_hash_from_magnet(magnet, item.get("guid") or item.get("Guid")),
        size_bytes=parse_size_name(item.get("size_name") or item.get("Size")),
        seeders=seeders,
        leechers=leechers,
        quality=parsed["quality"],
        voiceover=parsed["voiceover"],
        magnet=magnet or None,
        source="jacred",
    )


def _map_local_item(item: dict) -> Release:
    title = item.get("Title", "")
    parsed = parse_release_info(title)
    magnet = item.get("MagnetUri") or item.get("Link") or ""
    magnet_value = magnet if magnet.startswith("magnet:") else None
    size_raw = item.get("Size", 0)
    size_bytes = (
        parse_size_name(size_raw) if isinstance(size_raw, str) else int(size_raw or 0)
    )
    return Release(
        title=title,
        tracker=item.get("Tracker", "unknown"),
        info_hash=_info_hash_from_magnet(magnet, item.get("Guid")),
        size_bytes=size_bytes,
        seeders=int(item.get("Seeders", 0) or 0),
        leechers=int(item.get("Peers", 0) or 0) - int(item.get("Seeders", 0) or 0),
        quality=parsed["quality"],
        voiceover=parsed["voiceover"],
        magnet=magnet_value,
        source="jacred_local",
    )


async def _search_external(query: str) -> list[Release]:
    base = settings.JACRED_EXTERNAL_URL.rstrip("/")
    url = f"{base}/api/search"
    headers = {"Authorization": f"Bearer {settings.JACRED_EXTERNAL_API_KEY}"}
    params = {"query": query}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "?")
            logger.warning("External JacRed rate limited, Retry-After=%s", retry_after)
            raise httpx.HTTPError("jacred external rate limited")
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results") or data.get("Results") or []
    return [_map_external_item(item) for item in results]


async def _search_local(query: str) -> list[Release]:
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

    return [_map_local_item(item) for item in data.get("Results", [])]


async def search_releases(query: str, media_item_id: str) -> list[Release]:
    """Search releases via external JacRed first, fall back to local on failure.

    Empty external results are treated as a successful (empty) search —
    fallback only happens on network/HTTP errors, 429, or auth failures.
    """
    if _external_configured():
        try:
            return await _search_external(query)
        except httpx.HTTPError as exc:
            logger.warning(
                "External JacRed search failed (%s), falling back to local", exc
            )
        except Exception:
            logger.exception("External JacRed unexpected error, falling back to local")
    else:
        logger.debug("External JacRed not configured, using local only")

    return await _search_local(query)
