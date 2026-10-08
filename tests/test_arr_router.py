"""HTTP-level tests for /api/arr (ASGI, dependency_overrides, no DB)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.user import User
from app.schemas.arr import ArrEpisode, ArrMovie
from app.services import arr as arr_mod
from app.services.arr import ArrError, ArrNotFound
from app.services.arr_cache import arr_cache
from app.services.auth import get_current_user

SERIES_RAW = {"id": 10, "title": "Show", "year": 2020, "status": "ended"}


async def _fake_user() -> User:
    return User(
        id=__import__("uuid").uuid4(),
        email="a@b.c",
        password_hash="x",
        display_name="t",
    )


@pytest.fixture
async def client():
    arr_cache.invalidate()
    app.dependency_overrides[get_current_user] = _fake_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)
    arr_cache.invalidate()


def _settings(
    sonarr_url="http://sonarr:8989", sonarr_key="k", radarr_url="", radarr_key=""
):
    mock = MagicMock()
    mock.SONARR_URL = sonarr_url
    mock.SONARR_API_KEY = sonarr_key
    mock.RADARR_URL = radarr_url
    mock.RADARR_API_KEY = radarr_key
    mock.ARR_CACHE_TTL_SECONDS = 300
    mock.ARR_EPISODE_CACHE_TTL_SECONDS = 1800
    return mock


def _json_response(payload, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


@pytest.mark.asyncio
async def test_series_503_when_not_configured(client: AsyncClient):
    with patch.object(arr_mod, "settings", _settings(sonarr_url="", sonarr_key="")):
        resp = await client.get("/api/arr/series")
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_series_200_cache_hit(client: AsyncClient):
    with (
        patch.object(arr_mod, "settings", _settings()),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client_http = AsyncMock()
        client_http.get = AsyncMock(return_value=_json_response([SERIES_RAW]))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client_http)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        first = await client.get("/api/arr/series")
        second = await client.get("/api/arr/series")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()[0]["id"] == 10
    assert second.json() == first.json()
    assert client_http.get.await_count == 1


@pytest.mark.asyncio
async def test_series_refresh_bypasses_cache(client: AsyncClient):
    with (
        patch.object(arr_mod, "settings", _settings()),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client_http = AsyncMock()
        client_http.get = AsyncMock(return_value=_json_response([SERIES_RAW]))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client_http)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        await client.get("/api/arr/series")
        refreshed = await client.get("/api/arr/series?refresh=true")

    assert refreshed.status_code == 200
    assert client_http.get.await_count == 2


@pytest.mark.asyncio
async def test_series_detail_404(client: AsyncClient):
    with (
        patch.object(arr_mod, "settings", _settings()),
        patch.object(arr_mod, "httpx") as httpx_mod,
    ):
        client_http = AsyncMock()
        client_http.get = AsyncMock(return_value=_json_response({}, status_code=404))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client_http)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        resp = await client.get("/api/arr/series/999")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_episodes_200(client: AsyncClient):
    eps = [ArrEpisode(id=1, season_number=1, episode_number=1, title="Pilot")]
    with patch("app.services.arr.get_episodes", AsyncMock(return_value=eps)):
        resp = await client.get("/api/arr/series/10/episodes")
    assert resp.status_code == 200
    assert resp.json()[0]["episode_number"] == 1


@pytest.mark.asyncio
async def test_movies_502_on_upstream_error(client: AsyncClient):
    with patch(
        "app.services.arr.get_movies",
        AsyncMock(side_effect=ArrError("radarr request failed")),
    ):
        resp = await client.get("/api/arr/movies")
    assert resp.status_code == 502
    assert "radarr" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_movie_200(client: AsyncClient):
    movie = ArrMovie(id=5, title="Movie", tmdb_id=1, has_file=True)
    with patch("app.services.arr.get_movie", AsyncMock(return_value=movie)):
        resp = await client.get("/api/arr/movies/5")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Movie"


@pytest.mark.asyncio
async def test_requires_auth(client: AsyncClient):
    app.dependency_overrides.pop(get_current_user, None)
    resp = await client.get("/api/arr/series")
    assert resp.status_code in (401, 403)
    app.dependency_overrides[get_current_user] = _fake_user


@pytest.mark.asyncio
async def test_series_detail_uses_arr_not_found(client: AsyncClient):
    with patch(
        "app.services.arr.get_series_detail",
        AsyncMock(side_effect=ArrNotFound("series 999 not found")),
    ):
        resp = await client.get("/api/arr/series/999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
