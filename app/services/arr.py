"""Sonarr / Radarr (Servarr API v3) clients with in-memory TTL cache."""

import logging
from typing import Any

import httpx

from app.config import settings
from app.schemas.arr import ArrEpisode, ArrMovie, ArrSeason, ArrSeries
from app.services.arr_cache import arr_cache

logger = logging.getLogger(__name__)

ARR_TIMEOUT = 10.0


class ArrError(Exception):
    """Upstream *arr request failed."""


class ArrNotConfigured(Exception):
    """SONARR_/RADARR_ settings are missing."""


class ArrNotFound(Exception):
    """Entity missing in Sonarr/Radarr."""


def _service_settings(service: str) -> tuple[str, str]:
    if service == "sonarr":
        return settings.SONARR_URL.rstrip("/"), settings.SONARR_API_KEY
    return settings.RADARR_URL.rstrip("/"), settings.RADARR_API_KEY


def _require_configured(service: str) -> tuple[str, str]:
    base_url, api_key = _service_settings(service)
    if not base_url or not api_key:
        raise ArrNotConfigured(f"{service} is not configured")
    return base_url, api_key


async def _get_json(service: str, path: str) -> Any:
    base_url, api_key = _require_configured(service)
    headers = {"X-Api-Key": api_key}
    try:
        async with httpx.AsyncClient(timeout=ARR_TIMEOUT) as client:
            resp = await client.get(f"{base_url}{path}", headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("%s GET %s failed: %s", service, path, exc)
        raise ArrError(f"{service} request failed") from exc

    if resp.status_code == 404:
        raise ArrNotFound(f"{service} {path} not found")
    try:
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("%s GET %s failed: %s", service, path, exc)
        raise ArrError(f"{service} request failed") from exc
    return resp.json()


def map_season(raw: dict[str, Any]) -> ArrSeason:
    stats = raw.get("statistics") or {}
    return ArrSeason(
        season_number=raw.get("seasonNumber", 0),
        monitored=bool(raw.get("monitored", False)),
        episode_count=int(stats.get("totalEpisodeCount") or 0),
        episode_file_count=int(stats.get("episodeFileCount") or 0),
    )


def map_series(raw: dict[str, Any]) -> ArrSeries:
    seasons = [map_season(s) for s in raw.get("seasons") or []]
    return ArrSeries(
        id=raw["id"],
        title=raw.get("title") or "",
        year=raw.get("year"),
        status=raw.get("status") or "unknown",
        overview=raw.get("overview"),
        poster_url=_first_image(raw.get("images"), "poster"),
        network=raw.get("network"),
        tvdb_id=raw.get("tvdbId"),
        path=raw.get("path"),
        seasons=seasons,
    )


def map_episode(raw: dict[str, Any]) -> ArrEpisode:
    return ArrEpisode(
        id=raw["id"],
        season_number=raw.get("seasonNumber", 0),
        episode_number=raw.get("episodeNumber", 0),
        title=raw.get("title"),
        overview=raw.get("overview"),
        air_date=raw.get("airDate") or raw.get("airDateUtc"),
        has_file=bool(raw.get("hasFile", False)),
        monitored=bool(raw.get("monitored", False)),
    )


def map_movie(raw: dict[str, Any]) -> ArrMovie:
    return ArrMovie(
        id=raw["id"],
        title=raw.get("title") or "",
        year=raw.get("year"),
        overview=raw.get("overview"),
        poster_url=_first_image(raw.get("images"), "poster"),
        status=raw.get("status") or "unknown",
        has_file=bool(raw.get("hasFile", False)),
        monitored=bool(raw.get("monitored", False)),
        tmdb_id=raw.get("tmdbId"),
        path=raw.get("path"),
    )


def _first_image(images: list[dict[str, Any]] | None, cover_type: str) -> str | None:
    for image in images or []:
        if image.get("coverType") == cover_type:
            return image.get("remoteUrl") or image.get("url")
    return None


async def get_series() -> list[ArrSeries]:
    async def factory() -> list[ArrSeries]:
        data = await _get_json("sonarr", "/api/v3/series")
        return [map_series(item) for item in data or []]

    return await arr_cache.get_or_set(
        "arr:series:list",
        float(settings.ARR_CACHE_TTL_SECONDS),
        factory,
    )


async def get_series_detail(sonarr_id: int) -> ArrSeries:
    async def factory() -> ArrSeries:
        data = await _get_json("sonarr", f"/api/v3/series/{sonarr_id}")
        return map_series(data)

    return await arr_cache.get_or_set(
        f"arr:series:{sonarr_id}",
        float(settings.ARR_CACHE_TTL_SECONDS),
        factory,
    )


async def get_episodes(sonarr_id: int) -> list[ArrEpisode]:
    async def factory() -> list[ArrEpisode]:
        data = await _get_json(
            "sonarr", f"/api/v3/episode?seriesId={sonarr_id}"
        )
        return [map_episode(item) for item in data or []]

    return await arr_cache.get_or_set(
        f"arr:series:{sonarr_id}:episodes",
        float(settings.ARR_EPISODE_CACHE_TTL_SECONDS),
        factory,
    )


async def get_movies() -> list[ArrMovie]:
    async def factory() -> list[ArrMovie]:
        data = await _get_json("radarr", "/api/v3/movie")
        return [map_movie(item) for item in data or []]

    return await arr_cache.get_or_set(
        "arr:movies:list",
        float(settings.ARR_CACHE_TTL_SECONDS),
        factory,
    )


async def get_movie(radarr_id: int) -> ArrMovie:
    async def factory() -> ArrMovie:
        data = await _get_json("radarr", f"/api/v3/movie/{radarr_id}")
        return map_movie(data)

    return await arr_cache.get_or_set(
        f"arr:movies:{radarr_id}",
        float(settings.ARR_CACHE_TTL_SECONDS),
        factory,
    )
