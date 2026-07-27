from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from tvmaze_client import (
    TvmazeClient, _show_cache, _episodes_cache, _crew_cache, _tvdb_cache, _TVMAZE_CACHE_MAX_SHOWS,
)
from http_client import HttpError


@pytest.fixture(autouse=True)
def clear_tvmaze_cache():
    """Clear module-level TVMaze caches between tests."""
    _show_cache.clear()
    _episodes_cache.clear()
    _crew_cache.clear()
    _tvdb_cache.clear()
    yield
    _show_cache.clear()
    _episodes_cache.clear()
    _crew_cache.clear()
    _tvdb_cache.clear()


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
# Tests for get_episode_crew
# ---------------------------------------------------------------------------

class TestGetEpisodeCrew:

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_success(self, mock_http_cls):
        """Directors + Writers возвращаются корректно."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": "ep1"}],
            [
                {"guestCrewType": "Director", "person": {"name": "David Nutter"}},
                {"guestCrewType": "Writer", "person": {"name": "David Benioff"}},
                {"guestCrewType": "Writer", "person": {"name": "D.B. Weiss"}},
            ],
        ]
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == ["David Nutter"]
        assert writers == ["David Benioff", "D.B. Weiss"]

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_only_writers(self, mock_http_cls):
        """Crew без Directors — directors пуст."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
            [{"guestCrewType": "Writer", "person": {"name": "Jane Goldman"}}],
        ]
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == []
        assert writers == ["Jane Goldman"]

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_only_directors(self, mock_http_cls):
        """Crew без Writers — writers пуст."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
            [{"guestCrewType": "Director", "person": {"name": "Tim Van Patten"}}],
        ]
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == ["Tim Van Patten"]
        assert writers == []

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_empty_array(self, mock_http_cls):
        """Crew = пустой массив — обе списка пусты, info лог."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
            [],
        ]
        logger = MagicMock()
        client = TvmazeClient(logger=logger)
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == []
        assert writers == []
        logger.info.assert_called()

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_http_error(self, mock_http_cls):
        """HttpError на /crew — ([], []) + warning лог."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        responses = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
        ]
        call_count = [0]
        def side_effect(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx < 2:
                return responses[idx]
            raise HttpError(500, "Server Error", "url")
        mock_http.get_json.side_effect = side_effect

        logger = MagicMock()
        client = TvmazeClient(logger=logger)
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == []
        assert writers == []
        logger.warning.assert_called()

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_no_ids(self, mock_http_cls):
        """Пустой imdb_id и title_original — ([], []) без HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("", 1, 1)
        assert directors == []
        assert writers == []
        mock_http.get_json.assert_not_called()

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_episode_not_found(self, mock_http_cls):
        """Season/number не найден — ([], [])."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 5, "id": 5005, "summary": "other ep"}],
        ]
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == []
        assert writers == []

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_cache_hit(self, mock_http_cls):
        """Второй вызов с тем же episode — кэш hit, нет HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
            [{"guestCrewType": "Director", "person": {"name": "Alan Taylor"}}],
        ]
        client = TvmazeClient(logger=MagicMock())
        d1, w1 = client.get_episode_crew("tt1234567", 1, 1)
        assert d1 == ["Alan Taylor"]
        assert mock_http.get_json.call_count == 3

        d2, w2 = client.get_episode_crew("tt1234567", 1, 1)
        assert d2 == ["Alan Taylor"]
        assert mock_http.get_json.call_count == 3

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_multiple_directors(self, mock_http_cls):
        """3 Directors — все 3 в списке, порядок API."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 2, "number": 3, "id": 5023, "summary": ""}],
            [
                {"guestCrewType": "Director", "person": {"name": "Director A"}},
                {"guestCrewType": "Director", "person": {"name": "Director B"}},
                {"guestCrewType": "Director", "person": {"name": "Director C"}},
            ],
        ]
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("tt1234567", 2, 3)
        assert directors == ["Director A", "Director B", "Director C"]
        assert writers == []

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_filters_other_types(self, mock_http_cls):
        """Crew с Director, Writer, Producer, Creator — только Director и Writer."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
            [
                {"guestCrewType": "Director", "person": {"name": "Dir1"}},
                {"guestCrewType": "Writer", "person": {"name": "Wr1"}},
                {"guestCrewType": "Producer", "person": {"name": "Prod1"}},
                {"guestCrewType": "Creator", "person": {"name": "Cr1"}},
            ],
        ]
        client = TvmazeClient(logger=MagicMock())
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == ["Dir1"]
        assert writers == ["Wr1"]

    @patch('tvmaze_client.HttpClient')
    def test_get_episode_crew_missing_person_name(self, mock_http_cls):
        """Crew entry без person.name — пропускается с warning."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "id": 5001, "summary": ""}],
            [
                {"guestCrewType": "Director", "person": {"name": ""}},
                {"guestCrewType": "Director", "person": {"name": "Good Director"}},
                {"guestCrewType": "Writer", "person": {}},
            ],
        ]
        logger = MagicMock()
        client = TvmazeClient(logger=logger)
        directors, writers = client.get_episode_crew("tt1234567", 1, 1)
        assert directors == ["Good Director"]
        assert writers == []
        assert logger.warning.call_count >= 2


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


# ---------------------------------------------------------------------------
# Tests for get_tvdb_id
# ---------------------------------------------------------------------------

class TestGetTvdbId:

    @patch('tvmaze_client.HttpClient')
    def test_get_tvdb_id_success(self, mock_http_cls):
        """IMDB lookup returns valid thetvdb ID."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {
            "id": 82,
            "name": "Game of Thrones",
            "externals": {"tvrage": 24493, "thetvdb": 121361, "imdb": "tt0944947"},
        }

        client = TvmazeClient(logger=MagicMock())
        result = client.get_tvdb_id("tt0944947")

        assert result == 121361
        mock_http.get_json.assert_called_once_with("/lookup/shows", {"imdb": "tt0944947"})

    @patch('tvmaze_client.HttpClient')
    def test_get_tvdb_id_null_thetvdb(self, mock_http_cls):
        """externals.thetvdb is None -> result is None."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {
            "id": 100,
            "externals": {"tvrage": None, "thetvdb": None, "imdb": "tt1234567"},
        }

        client = TvmazeClient(logger=MagicMock())
        result = client.get_tvdb_id("tt1234567")

        assert result is None

    @patch('tvmaze_client.HttpClient')
    def test_get_tvdb_id_no_externals(self, mock_http_cls):
        """Response without externals field -> result is None."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 100}

        client = TvmazeClient(logger=MagicMock())
        result = client.get_tvdb_id("tt1234567")

        assert result is None

    @patch('tvmaze_client.HttpClient')
    def test_get_tvdb_id_fallback_to_search(self, mock_http_cls):
        """IMDB lookup 404 -> fallback to singlesearch by title_original."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            HttpError(404, "Not Found", "url"),  # IMDB lookup fails
            {"id": 82, "externals": {"thetvdb": 121361, "imdb": "tt0944947"}},  # singlesearch succeeds
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_tvdb_id("tt0000000", title_original="Game of Thrones")

        assert result == 121361
        assert mock_http.get_json.call_count == 2

    @patch('tvmaze_client.HttpClient')
    def test_get_tvdb_id_cache_hit(self, mock_http_cls):
        """Second call with same IMDB ID -> served from cache, no extra HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"externals": {"thetvdb": 121361}}

        client = TvmazeClient(logger=MagicMock())
        r1 = client.get_tvdb_id("tt0944947")
        r2 = client.get_tvdb_id("tt0944947")

        assert r1 == r2 == 121361
        mock_http.get_json.assert_called_once()
