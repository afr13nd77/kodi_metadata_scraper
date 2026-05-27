from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from tvmaze_client import (
    TvmazeClient, _show_cache, _episodes_cache, _TVMAZE_CACHE_MAX_SHOWS,
)
from http_client import HttpError


@pytest.fixture(autouse=True)
def clear_tvmaze_cache():
    """Clear module-level TVMaze caches between tests."""
    _show_cache.clear()
    _episodes_cache.clear()
    yield
    _show_cache.clear()
    _episodes_cache.clear()


# ---------------------------------------------------------------------------
# Tests for get_episode_plot
# ---------------------------------------------------------------------------

class TestGetEpisodePlot:

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_plot_success(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},  # lookup response
            [{"season": 1, "number": 1, "summary": "<p>Test <b>plot</b></p>"}],  # episodes response
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_plot("tt1234567", 1, 1)

        assert result == "Test plot"

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_plot_empty_imdb(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_plot("", 1, 1)

        assert result is None
        mock_http.get_json.assert_not_called()

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_plot_show_not_found(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = HttpError(404, "Not Found", "url")

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_plot("tt1234567", 1, 1)

        assert result is None

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_plot_api_timeout(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = Exception("Connection timed out")

        logger = MagicMock()
        client = TvmazeClient(logger=logger)
        result = client.get_episode_plot("tt1234567", 1, 1)

        assert result is None
        logger.warning.assert_called()

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_plot_episode_not_found(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},  # lookup response
            [{"season": 1, "number": 5, "summary": "other"}],  # episodes - no match
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_plot("tt1234567", 1, 1)

        assert result is None

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_plot_empty_summary(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},  # lookup response
            [{"season": 1, "number": 1, "summary": None}],  # episode with no summary
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_plot("tt1234567", 1, 1)

        assert result is None


# ---------------------------------------------------------------------------
# Tests for cache behavior
# ---------------------------------------------------------------------------

class TestCacheBehavior:

    @patch('tvmaze_client.HttpClient')
    def test_lookup_show_cache_hit(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 100}

        client = TvmazeClient(logger=MagicMock())

        # First call - fetches from API
        result1 = client.lookup_show("tt1234567")
        assert result1 == 100
        assert mock_http.get_json.call_count == 1

        # Second call - served from cache
        result2 = client.lookup_show("tt1234567")
        assert result2 == 100
        assert mock_http.get_json.call_count == 1  # Not called again

    @patch('tvmaze_client.HttpClient')
    def test_get_episodes_cache_hit(self, mock_http_cls):
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = [
            {"season": 1, "number": 1, "summary": "<p>Ep1</p>"}
        ]

        client = TvmazeClient(logger=MagicMock())

        # First call - fetches from API
        result1 = client.get_episodes(100)
        assert result1 is not None
        assert len(result1) == 1
        assert mock_http.get_json.call_count == 1

        # Second call - served from cache
        result2 = client.get_episodes(100)
        assert result2 is not None
        assert mock_http.get_json.call_count == 1  # Not called again

    def test_cache_eviction_shows(self):
        """Fill _show_cache to max, add one more, check eviction."""
        # Pre-fill cache to max capacity
        for i in range(_TVMAZE_CACHE_MAX_SHOWS):
            _show_cache[f"tt{i:07d}"] = i

        assert len(_show_cache) == _TVMAZE_CACHE_MAX_SHOWS

        # The first key inserted
        first_key = "tt0000000"
        assert first_key in _show_cache

        # Now add one more via lookup_show to trigger eviction logic
        with patch('tvmaze_client.HttpClient') as mock_http_cls:
            mock_http = MagicMock()
            mock_http_cls.return_value = mock_http
            mock_http.get_json.return_value = {"id": 999}

            client = TvmazeClient(logger=MagicMock())
            result = client.lookup_show("tt9999999")

        assert result == 999
        # Cache should not exceed max size
        assert len(_show_cache) <= _TVMAZE_CACHE_MAX_SHOWS
        # The first entry should have been evicted
        assert first_key not in _show_cache
        # The new entry should exist
        assert "tt9999999" in _show_cache


# ---------------------------------------------------------------------------
# Tests for _strip_html
# ---------------------------------------------------------------------------

class TestStripHtml:

    def _make_client(self):
        with patch('tvmaze_client.HttpClient'):
            return TvmazeClient(logger=MagicMock())

    def test_strip_html_tags(self):
        client = self._make_client()
        assert client._strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_strip_html_empty(self):
        client = self._make_client()
        assert client._strip_html("") == ""

    def test_strip_html_no_tags(self):
        client = self._make_client()
        assert client._strip_html("no tags") == "no tags"

    def test_strip_html_with_extra_spaces(self):
        client = self._make_client()
        assert client._strip_html("<p>  spaced  </p>") == "spaced"
