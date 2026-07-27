from __future__ import annotations

import sys
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
sys.modules.setdefault("xbmcplugin", MagicMock())
sys.modules.setdefault("xbmcvfs", MagicMock())

from fanart_client import FanartClient, _fanart_cache  # noqa: E402
from http_client import HttpError  # noqa: E402


@pytest.fixture(autouse=True)
def clear_fanart_cache():
    _fanart_cache.clear()
    yield
    _fanart_cache.clear()


def _make_client() -> FanartClient:
    return FanartClient("test-api-key", logger=MagicMock())


class TestGetMovieArt:

    def test_get_movie_art_success(self):
        client = _make_client()
        api_response = {
            "hdmovielogo": [
                {"id": "50927", "url": "https://assets.fanart.tv/movies/120/logo.png", "lang": "en", "likes": "7"},
            ],
            "moviebanner": [
                {"id": "50928", "url": "https://assets.fanart.tv/movies/120/banner.jpg", "lang": "en", "likes": "3"},
            ],
            "moviethumb": [
                {"id": "50929", "url": "https://assets.fanart.tv/movies/120/thumb.jpg", "lang": "en", "likes": "5"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_movie_art("tt0120737")

        assert result["clearlogo"] == "https://assets.fanart.tv/movies/120/logo.png"
        assert result["banner"] == "https://assets.fanart.tv/movies/120/banner.jpg"
        assert result["landscape"] == "https://assets.fanart.tv/movies/120/thumb.jpg"

    def test_get_movie_art_best_by_likes(self):
        client = _make_client()
        api_response = {
            "hdmovielogo": [
                {"id": "1", "url": "https://fanart.tv/logo_7.png", "lang": "en", "likes": "7"},
                {"id": "2", "url": "https://fanart.tv/logo_3.png", "lang": "en", "likes": "3"},
                {"id": "3", "url": "https://fanart.tv/logo_15.png", "lang": "en", "likes": "15"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_movie_art("tt0000001")

        assert result["clearlogo"] == "https://fanart.tv/logo_15.png"

    def test_get_movie_art_lang_priority(self):
        client = _make_client()
        api_response = {
            "hdmovielogo": [
                {"id": "1", "url": "https://fanart.tv/logo_ru.png", "lang": "ru", "likes": "10"},
                {"id": "2", "url": "https://fanart.tv/logo_en.png", "lang": "en", "likes": "2"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_movie_art("tt0000002")

        assert result["clearlogo"] == "https://fanart.tv/logo_en.png"

    def test_get_movie_art_empty_imdb_id(self):
        client = _make_client()
        result = client.get_movie_art("")
        assert result == {}

    def test_get_movie_art_http_404(self):
        client = _make_client()
        with patch.object(
            client._http,
            "get_json",
            side_effect=HttpError(404, "Not Found", "http://test.url"),
        ):
            result = client.get_movie_art("tt9999999")

        assert result == {}

    def test_get_movie_art_http_429(self):
        client = _make_client()
        with patch.object(
            client._http,
            "get_json",
            side_effect=HttpError(429, "Too Many Requests", "http://test.url"),
        ):
            result = client.get_movie_art("tt0000003")

        assert result == {}

    def test_get_movie_art_connection_error(self):
        client = _make_client()
        with patch.object(
            client._http,
            "get_json",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = client.get_movie_art("tt0000004")

        assert result == {}

    def test_get_movie_art_excludes_poster_fanart(self):
        client = _make_client()
        api_response = {
            "movieposter": [
                {"id": "1", "url": "https://fanart.tv/poster.jpg", "lang": "en", "likes": "10"},
            ],
            "moviebackground": [
                {"id": "2", "url": "https://fanart.tv/background.jpg", "lang": "en", "likes": "8"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            result = client.get_movie_art("tt0000005")

        assert "poster" not in result
        assert "fanart" not in result
        assert "movieposter" not in result
        assert "moviebackground" not in result
        assert result == {}

    def test_get_movie_art_cache_hit(self):
        client = _make_client()
        api_response = {
            "hdmovielogo": [
                {"id": "1", "url": "https://fanart.tv/logo.png", "lang": "en", "likes": "5"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response) as mock_get:
            first = client.get_movie_art("tt0120737")
            second = client.get_movie_art("tt0120737")

        mock_get.assert_called_once()
        assert first == second
        assert first["clearlogo"] == "https://fanart.tv/logo.png"


class TestGetTvArt:

    def test_get_tv_art_success(self):
        client = _make_client()
        api_response = {
            "hdtvlogo": [
                {"id": "1", "url": "https://fanart.tv/tv/logo.png", "lang": "en", "likes": "5"},
            ],
            "tvbanner": [
                {"id": "2", "url": "https://fanart.tv/tv/banner.jpg", "lang": "en", "likes": "3"},
            ],
            "tvthumb": [
                {"id": "3", "url": "https://fanart.tv/tv/thumb.jpg", "lang": "en", "likes": "4"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            show_art, season_art = client.get_tv_art(121361)

        assert show_art["clearlogo"] == "https://fanart.tv/tv/logo.png"
        assert show_art["banner"] == "https://fanart.tv/tv/banner.jpg"
        assert show_art["landscape"] == "https://fanart.tv/tv/thumb.jpg"

    def test_get_tv_art_season_grouping(self):
        client = _make_client()
        api_response = {
            "seasonbanner": [
                {"id": "1", "url": "https://fanart.tv/tv/s1_banner.jpg", "lang": "en", "likes": "5", "season": "1"},
                {"id": "2", "url": "https://fanart.tv/tv/s2_banner.jpg", "lang": "en", "likes": "3", "season": "2"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            show_art, season_art = client.get_tv_art(121362)

        assert 1 in season_art
        assert 2 in season_art
        assert season_art[1]["banner"] == "https://fanart.tv/tv/s1_banner.jpg"
        assert season_art[2]["banner"] == "https://fanart.tv/tv/s2_banner.jpg"

    def test_get_tv_art_excludes_poster(self):
        client = _make_client()
        api_response = {
            "tvposter": [
                {"id": "1", "url": "https://fanart.tv/tv/poster.jpg", "lang": "en", "likes": "10"},
            ],
        }
        with patch.object(client._http, "get_json", return_value=api_response):
            show_art, season_art = client.get_tv_art(121363)

        assert "poster" not in show_art
        assert "tvposter" not in show_art
        assert show_art == {}


class TestPickBest:

    def test_pick_best_empty_list(self):
        client = _make_client()
        result = client._pick_best([])
        assert result is None

    def test_pick_best_no_url(self):
        client = _make_client()
        result = client._pick_best([{"lang": "en", "likes": "5"}])
        assert result is None

    def test_pick_best_likes_parsing(self):
        client = _make_client()
        result = client._pick_best([
            {"url": "https://fanart.tv/abc.png", "lang": "en", "likes": "abc"},
            {"url": "https://fanart.tv/five.png", "lang": "en", "likes": "5"},
        ])
        assert result == "https://fanart.tv/five.png"
