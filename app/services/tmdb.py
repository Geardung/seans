import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_TIMEOUT = 5.0


def _search_endpoint(kp_type: str) -> tuple[str, str]:
    if kp_type == "tv":
        return "/search/tv", "first_air_date_year"
    return "/search/movie", "year"


def _query_candidates(title: str, original_title: str | None) -> list[str]:
    candidates: list[str] = []
    for value in (original_title, title):
        if value and value not in candidates:
            candidates.append(value)
    return candidates


async def resolve_tmdb_id(
    title: str,
    original_title: str | None,
    year: int | None,
    kp_type: str,
) -> int | None:
    """Resolve TMDB id via API v3 search. Never raises; returns None on any failure."""
    if not settings.TMDB_API_TOKEN:
        logger.info("TMDB_API_TOKEN not set, skipping tmdb resolve")
        return None

    path, year_param = _search_endpoint(kp_type)
    queries = _query_candidates(title, original_title)
    if not queries:
        return None

    try:
        async with httpx.AsyncClient(timeout=TMDB_TIMEOUT) as client:
            for query in queries:
                params: dict[str, Any] = {
                    "api_key": settings.TMDB_API_TOKEN,
                    "query": query,
                    "language": "en-US",
                }
                if year is not None:
                    params[year_param] = year
                resp = await client.get(f"{TMDB_API_BASE}{path}", params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results") or []
                if not results:
                    continue
                tmdb_id = results[0].get("id")
                if isinstance(tmdb_id, int):
                    return tmdb_id
                return None
    except Exception:
        logger.warning(
            "TMDB resolve failed for title=%r year=%s kp_type=%s",
            title,
            year,
            kp_type,
            exc_info=True,
        )
        return None
    return None
