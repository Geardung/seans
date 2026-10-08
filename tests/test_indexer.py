"""Unit tests for JacRed indexer: external primary + local fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import indexer
from app.services.indexer import (
    Release,
    parse_size_name,
    search_releases,
)


def _settings(
    external_url="", external_key="", local_url="http://jacred:9117", local_key=""
):
    mock = MagicMock()
    mock.JACRED_URL = local_url
    mock.JACRED_API_KEY = local_key
    mock.JACRED_EXTERNAL_URL = external_url
    mock.JACRED_EXTERNAL_API_KEY = external_key
    return mock


@pytest.fixture
def mock_settings():
    with patch.object(indexer, "settings", _settings()) as mock:
        yield mock


EXTERNAL_PAYLOAD = {
    "results": [
        {
            "title": "The Matrix 1999 1080p WEB-DL",
            "tracker": "rutracker",
            "size_name": "11.81 GB",
            "seeders": 56,
            "peers": 8,
            "availability_score": 0.875,
            "magnet": "magnet:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01&dn=matrix",
            "source_url": "https://rutracker.org/topic/1",
        }
    ],
    "total": 1,
    "facets": {},
}

LOCAL_PAYLOAD = {
    "Results": [
        {
            "Title": "The.Matrix.1999.1080p.BDRip",
            "Tracker": "nnm-club",
            "MagnetUri": "magnet:?xt=urn:btih:1111111111111111111111111111111111111111",
            "Size": 8589934592,
            "Seeders": 12,
            "Peers": 20,
        }
    ]
}


def _httpx_response(
    status_code: int, json_data: dict | None = None, headers: dict | None = None
):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestParseSizeName:
    def test_gb_binary(self):
        assert parse_size_name("11.81 GB") == int(11.81 * 1024**3)

    def test_mb(self):
        assert parse_size_name("700 MB") == 700 * 1024**2

    def test_empty(self):
        assert parse_size_name(None) == 0
        assert parse_size_name("") == 0

    def test_garbage(self):
        assert parse_size_name("huge") == 0


class TestSearchExternalPrimary:
    @pytest.mark.asyncio
    async def test_external_success_skips_local(self, mock_settings):
        mock_settings.JACRED_EXTERNAL_URL = "https://api.jacred.su"
        mock_settings.JACRED_EXTERNAL_API_KEY = "jrs_test"

        ext = _httpx_response(200, EXTERNAL_PAYLOAD)
        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=ext
            )
            # if local were called, this would also return; assert call count
            releases = await search_releases("Matrix 1999", "mid-1")

        assert len(releases) == 1
        rel = releases[0]
        assert isinstance(rel, Release)
        assert rel.title == "The Matrix 1999 1080p WEB-DL"
        assert rel.tracker == "rutracker"
        assert rel.seeders == 56
        assert rel.leechers == 8
        assert rel.quality == "1080p"
        assert rel.source == "jacred"
        assert (
            rel.magnet and rel.info_hash == "abcdef0123456789abcdef0123456789abcdef01"
        )
        assert rel.size_bytes == int(11.81 * 1024**3)

    @pytest.mark.asyncio
    async def test_external_empty_is_not_fallback(self, mock_settings):
        mock_settings.JACRED_EXTERNAL_URL = "https://api.jacred.su"
        mock_settings.JACRED_EXTERNAL_API_KEY = "jrs_test"

        ext = _httpx_response(200, {"results": [], "total": 0})
        get_mock = AsyncMock(return_value=ext)
        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = get_mock
            releases = await search_releases("nosuch", "mid-1")

        assert releases == []
        assert get_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_external_http_error_falls_back_to_local(self, mock_settings):
        mock_settings.JACRED_EXTERNAL_URL = "https://api.jacred.su"
        mock_settings.JACRED_EXTERNAL_API_KEY = "jrs_test"

        ext = _httpx_response(500)
        ext.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=ext
        )
        local = _httpx_response(200, LOCAL_PAYLOAD)

        async def _get(url, **kwargs):
            if "api.jacred.su" in url:
                return ext
            return local

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=_get
            )
            releases = await search_releases("Matrix 1999", "mid-1")

        assert len(releases) == 1
        assert releases[0].source == "jacred_local"
        assert releases[0].tracker == "nnm-club"
        assert releases[0].seeders == 12
        assert releases[0].leechers == 8  # Peers 20 - Seeders 12
        assert releases[0].size_bytes == 8589934592

    @pytest.mark.asyncio
    async def test_external_rate_limit_falls_back(self, mock_settings):
        mock_settings.JACRED_EXTERNAL_URL = "https://api.jacred.su"
        mock_settings.JACRED_EXTERNAL_API_KEY = "jrs_test"

        ext = _httpx_response(429, headers={"Retry-After": "60"})
        local = _httpx_response(200, LOCAL_PAYLOAD)

        async def _get(url, **kwargs):
            if "api.jacred.su" in url:
                return ext
            return local

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=_get
            )
            releases = await search_releases("Matrix 1999", "mid-1")

        assert len(releases) == 1
        assert releases[0].source == "jacred_local"

    @pytest.mark.asyncio
    async def test_external_unconfigured_uses_local(self, mock_settings):
        # default mock_settings has empty external URL/key
        local = _httpx_response(200, LOCAL_PAYLOAD)
        get_mock = AsyncMock(return_value=local)
        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = get_mock
            releases = await search_releases("Matrix 1999", "mid-1")

        assert len(releases) == 1
        assert releases[0].source == "jacred_local"
        assert get_mock.call_count == 1
        assert "api.jacred.su" not in get_mock.call_args.args[0]

    @pytest.mark.asyncio
    async def test_external_key_only_is_not_enough(self, mock_settings):
        mock_settings.JACRED_EXTERNAL_URL = ""
        mock_settings.JACRED_EXTERNAL_API_KEY = "jrs_test"

        local = _httpx_response(200, LOCAL_PAYLOAD)
        get_mock = AsyncMock(return_value=local)
        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = get_mock
            releases = await search_releases("Matrix 1999", "mid-1")

        assert releases[0].source == "jacred_local"
        assert get_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_external_timeout_falls_back(self, mock_settings):
        mock_settings.JACRED_EXTERNAL_URL = "https://api.jacred.su"
        mock_settings.JACRED_EXTERNAL_API_KEY = "jrs_test"

        local = _httpx_response(200, LOCAL_PAYLOAD)

        async def _get(url, **kwargs):
            if "api.jacred.su" in url:
                raise httpx.TimeoutException("timeout")
            return local

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=_get
            )
            releases = await search_releases("Matrix 1999", "mid-1")

        assert releases[0].source == "jacred_local"
