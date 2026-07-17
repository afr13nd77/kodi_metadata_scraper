from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
sys.modules.setdefault("xbmcplugin", MagicMock())
sys.modules.setdefault("xbmcvfs", MagicMock())

from tvmaze_client import TvmazeClient, _seasons_cache, _tvmaze_cache_lock
from models import SeasonArtInfo
from http_client import HttpError


@pytest.fixture(autouse=True)
def clear_cache():
    with _tvmaze_cache_lock:
        _seasons_cache.clear()
    yield
    with _tvmaze_cache_lock:
        _seasons_cache.clear()


def _make_client() -> TvmazeClient:
    return TvmazeClient(logger=MagicMock())


class TestGetSeasons:

    def test_get_seasons_success(self):
        client = _make_client()
        api_response = [
            {
                "number": 1,
                "name": "Season 1",
                "image": {"medium": "http://m1.jpg", "original": "http://o1.jpg"},
            },
            {
                "number": 2,
                "name": "The Return",
                "image": {"medium": "http://m2.jpg", "original": "http://o2.jpg"},
            },
        ]
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_seasons(100)

        assert result is not None
        assert len(result) == 2
        assert result[0].number == 1
        assert result[0].name == "Season 1"
        assert result[0].poster_url == "http://o1.jpg"
        assert result[0].poster_preview_url == "http://m1.jpg"
        assert result[1].number == 2
        assert result[1].name == "The Return"
        assert result[1].poster_url == "http://o2.jpg"
        assert result[1].poster_preview_url == "http://m2.jpg"

    def test_get_seasons_cache_hit(self):
        client = _make_client()
        api_response = [
            {
                "number": 1,
                "name": "Season 1",
                "image": {"medium": "http://m1.jpg", "original": "http://o1.jpg"},
            },
        ]
        with patch.object(client._http, "get_json", return_value=api_response) as mock_get:
            first = client.get_seasons(200)
            second = client.get_seasons(200)

        mock_get.assert_called_once()
        assert first is not None
        assert second is not None
        assert len(first) == 1
        assert first[0].number == 1
        assert second[0].number == 1

    def test_get_seasons_http_error(self):
        client = _make_client()
        with patch.object(
            client._http,
            "get_json",
            side_effect=HttpError(500, "Server Error", "http://api.tvmaze.com/shows/300/seasons"),
        ):
            result = client.get_seasons(300)

        assert result is None

    def test_get_seasons_null_image(self):
        client = _make_client()
        api_response = [
            {"number": 1, "name": "Specials", "image": None},
        ]
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_seasons(400)

        assert result is not None
        assert len(result) == 1
        assert result[0].number == 1
        assert result[0].name == "Specials"
        assert result[0].poster_url == ""
        assert result[0].poster_preview_url == ""

    def test_get_seasons_null_number(self):
        client = _make_client()
        api_response = [
            {"number": None, "name": "Specials", "image": {"medium": "http://m.jpg", "original": "http://o.jpg"}},
            {"number": 1, "name": "Season 1", "image": {"medium": "http://m1.jpg", "original": "http://o1.jpg"}},
        ]
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_seasons(500)

        assert result is not None
        assert len(result) == 1
        assert result[0].number == 1
        assert result[0].name == "Season 1"

    def test_get_seasons_empty_list(self):
        client = _make_client()
        with patch.object(client._http, "get_json", return_value=[]):
            result = client.get_seasons(600)

        assert result is not None
        assert result == []
