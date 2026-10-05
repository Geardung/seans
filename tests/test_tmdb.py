from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.media_item import MediaItem
from app.services import tmdb as tmdb_mod
from app.services.kinopoisk import MOCK_FIXTURES, upsert_media_items


def _settings(token: str) -> MagicMock:
    mock = MagicMock()
    mock.TMDB_API_TOKEN = token
    return mock


def _json_response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


@pytest.mark.asyncio
async def test_resolve_tmdb_id_movie():
    with (
        patch.object(tmdb_mod, "settings", _settings("token")),
        patch.object(tmdb_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_json_response({"results": [{"id": 157336}]})
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        result = await tmdb_mod.resolve_tmdb_id(
            title="Интерстеллар",
            original_title="Interstellar",
            year=2014,
            kp_type="movie",
        )

    assert result == 157336
    client.get.assert_awaited_once()
    args, kwargs = client.get.await_args
    assert args[0] == "https://api.themoviedb.org/3/search/movie"
    assert kwargs["params"]["query"] == "Interstellar"
    assert kwargs["params"]["year"] == 2014
    assert kwargs["params"]["api_key"] == "token"
    assert kwargs["params"]["language"] == "en-US"


@pytest.mark.asyncio
async def test_resolve_tmdb_id_tv():
    with (
        patch.object(tmdb_mod, "settings", _settings("token")),
        patch.object(tmdb_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_json_response({"results": [{"id": 1399}]}))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        result = await tmdb_mod.resolve_tmdb_id(
            title="Игра престолов",
            original_title="Game of Thrones",
            year=2011,
            kp_type="tv",
        )

    assert result == 1399
    args, kwargs = client.get.await_args
    assert args[0] == "https://api.themoviedb.org/3/search/tv"
    assert kwargs["params"]["first_air_date_year"] == 2011
    assert "year" not in kwargs["params"]


@pytest.mark.asyncio
async def test_resolve_tmdb_id_empty_token():
    with patch.object(tmdb_mod, "settings", _settings("")):
        result = await tmdb_mod.resolve_tmdb_id(
            title="Interstellar",
            original_title="Interstellar",
            year=2014,
            kp_type="movie",
        )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_tmdb_id_no_results():
    with (
        patch.object(tmdb_mod, "settings", _settings("token")),
        patch.object(tmdb_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(
            side_effect=[
                _json_response({"results": []}),
                _json_response({"results": []}),
            ]
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        result = await tmdb_mod.resolve_tmdb_id(
            title="Nonexistent Title XYZ",
            original_title="Nope",
            year=2020,
            kp_type="movie",
        )

    assert result is None
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_resolve_tmdb_id_http_error():
    with (
        patch.object(tmdb_mod, "settings", _settings("token")),
        patch.object(tmdb_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.HTTPError("boom"))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        result = await tmdb_mod.resolve_tmdb_id(
            title="Interstellar",
            original_title="Interstellar",
            year=2014,
            kp_type="movie",
        )

    assert result is None


@pytest.mark.asyncio
async def test_resolve_tmdb_id_prefers_original_title():
    with (
        patch.object(tmdb_mod, "settings", _settings("token")),
        patch.object(tmdb_mod, "httpx") as httpx_mod,
    ):
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_json_response({"results": [{"id": 378527}]})
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=None)
        httpx_mod.AsyncClient.return_value = cm

        result = await tmdb_mod.resolve_tmdb_id(
            title="Токийский гуль",
            original_title="Tokyo Ghoul",
            year=2017,
            kp_type="movie",
        )

    assert result == 378527
    assert client.get.await_count == 1
    assert client.get.await_args.kwargs["params"]["query"] == "Tokyo Ghoul"


@pytest.mark.asyncio
async def test_upsert_resolves_tmdb_id():
    fake_item = MagicMock()
    fake_item.tmdb_id = None
    fake_item.title = "Интерстеллар"
    fake_item.original_title = "Interstellar"
    fake_item.year = 2014
    fake_item.kp_type = "movie"

    row = MagicMock()
    row.scalar_one.return_value = fake_item
    db = MagicMock()
    db.execute = AsyncMock(return_value=row)
    db.commit = AsyncMock()

    with patch(
        "app.services.kinopoisk.resolve_tmdb_id", new_callable=AsyncMock
    ) as resolve_mock:
        resolve_mock.return_value = 157336
        result = await upsert_media_items(db, [dict(MOCK_FIXTURES[1])])

    assert len(result) == 1
    assert result[0].tmdb_id == 157336
    resolve_mock.assert_awaited_once()
    kwargs = resolve_mock.await_args.kwargs
    assert kwargs["title"] == "Интерстеллар"
    assert kwargs["original_title"] == "Interstellar"
    assert kwargs["kp_type"] == "movie"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_skips_tmdb_when_no_token():
    fake_item = MagicMock()
    fake_item.tmdb_id = None
    fake_item.title = "Интерстеллар"
    fake_item.original_title = "Interstellar"
    fake_item.year = 2014
    fake_item.kp_type = "movie"

    row = MagicMock()
    row.scalar_one.return_value = fake_item
    db = MagicMock()
    db.execute = AsyncMock(return_value=row)
    db.commit = AsyncMock()

    with (
        patch.object(tmdb_mod, "settings", _settings("")),
        patch(
            "app.services.kinopoisk.resolve_tmdb_id", new_callable=AsyncMock
        ) as resolve_mock,
    ):
        resolve_mock.return_value = None
        result = await upsert_media_items(db, [dict(MOCK_FIXTURES[1])])

    assert result[0].tmdb_id is None


@pytest.mark.asyncio
async def test_upsert_skips_resolve_when_fixture_has_tmdb_id():
    fake_item = MagicMock()
    fake_item.tmdb_id = 157336
    fake_item.title = "Интерстеллар"
    fake_item.original_title = "Interstellar"
    fake_item.year = 2014
    fake_item.kp_type = "movie"

    row = MagicMock()
    row.scalar_one.return_value = fake_item
    db = MagicMock()
    db.execute = AsyncMock(return_value=row)
    db.commit = AsyncMock()

    with patch(
        "app.services.kinopoisk.resolve_tmdb_id", new_callable=AsyncMock
    ) as resolve_mock:
        result = await upsert_media_items(db, [dict(MOCK_FIXTURES[1])])

    assert result[0].tmdb_id == 157336
    resolve_mock.assert_not_awaited()


def test_mock_fixtures_have_real_tmdb_ids():
    by_kp = {f["kp_id"]: f["tmdb_id"] for f in MOCK_FIXTURES}
    assert by_kp[11154872] == 378527
    assert by_kp[258687] == 157336
    assert by_kp[464963] == 1399


def test_media_item_model_has_tmdb_id_column():
    assert "tmdb_id" in MediaItem.__table__.columns
    col = MediaItem.__table__.columns["tmdb_id"]
    assert col.nullable is True
    assert col.unique is not True
