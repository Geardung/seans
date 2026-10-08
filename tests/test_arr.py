"""Unit tests for *arr mappers and client behaviour (no network)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.arr import ArrEpisode, ArrMovie, ArrSeries
from app.services import arr as arr_mod
from app.services.arr import (
    ArrNotConfigured,
    ArrNotFound,
    get_episodes,
    get_movie,
    get_movies,
    get_series,
    get_series_detail,
    map_episode,
    map_movie,
    map_series,
)
from app.services.arr_cache import arr_cache


@pytest.fixture(autouse=True)
def clear_cache():
    arr_cache.invalidate()
    yield
    arr_cache.invalidate()


def _settings(sonarr_url="", sonarr_key="", radarr_url="", radarr_key=""):
    mock = MagicMock()
    mock.SONARR_URL = sonarr_url
    mock.SONARR_API_KEY = sonarr_key
    mock.RADARR_URL = radarr_url
    mock.RADARR_API_KEY = radarr_key
    mock.ARR_CACHE_TTL_SECONDS = 300
    mock.ARR_EPISODE_CACHE_TTL_SECONDS = 1800
    return mock


SERIES_RAW = {
    "id": 10,
    "title": "Игра престолов",
    "year": 2011,
    "status": "ended",
    "overview": "epic",
    "network": "HBO",
    "tvdbId": 123,
    "path": "/data/media/tv/Game of Thrones",
    "images": [{"coverType": "poster", "remoteUrl": "http://img/poster.jpg"}],
    "seasons": [
        {
            "seasonNumber": 1,
            "monitored": True,
            "statistics": {"totalEpisodeCount": 10, "episodeFileCount": 10},
        }
    ],
}

EPISODE_RAW = {
    "id": 100,
    "seasonNumber": 1,
    "episodeNumber": 1,
    "title": "Winter Is Coming",
    "overview": "pilot",
    "airDate": "2011-04-17",
    "hasFile": True,
    "monitored": True,
}

MOVIE_RAW = {
    "id": 5,
    "title": "Интерстеллар",
    "year": 2014,
    "overview": "space",
    "status": "released",
    "hasFile": True,
    "monitored": True,
    "tmdbId": 157336,
    "path": "/data/media/movies/Interstellar",
    "images": [{"coverType": "poster", "remoteUrl": "http://img/m.jpg"}],
}


def test_map_series():
    series = map_series(SERIES_RAW)
    assert isinstance(series, ArrSeries)
    assert series.id == 10
    assert series.tvdb_id == 123
    assert series.poster_url == "http://img/poster.jpg"
    assert series.seasons[0].season_number == 1
    assert series.seasons[0].episode_file_count == 10


def test_map_episode():
    ep = map_episode(EPISODE_RAW)
    assert isinstance(ep, ArrEpisode)
    assert ep.has_file is True
    assert ep.air_date == "2011-04-17"


def test_map_movie():
    movie = map_movie(MOVIE_RAW)
    assert isinstance(movie, ArrMovie)
    assert movie.tmdb_id == 157336
    assert movie.has_file is True


@pytest.mark.asyncio
async def test_not_configured():
    with (
        patch.object(arr_mod, "settings", _settings()),
        pytest.raises(ArrNotConfigured),
    ):
        await get_series()


def _json_response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


@pytest.mark.asyncio
async def test_get_series_cached():
    with (
        patch.object(
            arr_mod, "settings", _settings("http://sonarr:8989", "key")
        ),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_json_response([SERIES_RAW]))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        first = await get_series()
        second = await get_series()

    assert [s.id for s in first] == [10]
    assert second == first
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_get_series_detail_not_found():
    with (
        patch.object(
            arr_mod, "settings", _settings("http://sonarr:8989", "key")
        ),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_json_response({}, status_code=404))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        with pytest.raises(ArrNotFound):
            await get_series_detail(999)


@pytest.mark.asyncio
async def test_get_episodes_cached_longer_key():
    with (
        patch.object(
            arr_mod, "settings", _settings("http://sonarr:8989", "key")
        ),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_json_response([EPISODE_RAW]))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        eps = await get_episodes(10)
        again = await get_episodes(10)

    assert eps[0].episode_number == 1
    assert again == eps
    assert client.get.await_count == 1


@pytest.mark.asyncio
async def test_get_movies_and_detail():
    with (
        patch.object(
            arr_mod,
            "settings",
            _settings(
                radarr_url="http://radarr:7878",
                radarr_key="key",
            ),
        ),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(
            side_effect=[
                _json_response([MOVIE_RAW]),
                _json_response(MOVIE_RAW),
            ]
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        movies = await get_movies()
        movie = await get_movie(5)

    assert [m.id for m in movies] == [5]
    assert movie.title == "Интерстеллар"
    assert client.get.await_count == 2
