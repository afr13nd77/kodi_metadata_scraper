from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from tvmaze_client import (
    TvmazeClient, _show_cache, _episodes_cache, _crew_cache,
    _tvdb_cache, _status_cache, _show_data_cache,
    _TVMAZE_CACHE_MAX_SHOWS,
)
import tvmaze_client
from http_client import HttpError


@pytest.fixture(autouse=True)
def clear_tvmaze_cache():
    """Clear module-level TVMaze caches and circuit breaker between tests."""
    _show_cache.clear()
    _episodes_cache.clear()
    _crew_cache.clear()
    _tvdb_cache.clear()
    _status_cache.clear()
    _show_data_cache.clear()
    tvmaze_client._circuit_failures = 0
    tvmaze_client._circuit_open = False
    yield
    _show_cache.clear()
    _episodes_cache.clear()
    _crew_cache.clear()
    _tvdb_cache.clear()
    _status_cache.clear()
    _show_data_cache.clear()
    tvmaze_client._circuit_failures = 0
    tvmaze_client._circuit_open = False


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
        mock_http.get_json.return_value = {"id": 82, "externals": {"thetvdb": 121361}}

        client = TvmazeClient(logger=MagicMock())
        r1 = client.get_tvdb_id("tt0944947")
        r2 = client.get_tvdb_id("tt0944947")

        assert r1 == r2 == 121361
        mock_http.get_json.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for get_show_status
# ---------------------------------------------------------------------------

class TestGetShowStatus:

    @patch('tvmaze_client.HttpClient')
    def test_status_ended(self, mock_http_cls):
        """TVMaze status='Ended' -> 'Ended'."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 169, "status": "Ended"}

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("tt0903747")
        assert result == "Ended"

    @patch('tvmaze_client.HttpClient')
    def test_status_running(self, mock_http_cls):
        """TVMaze status='Running' -> 'Returning Series'."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 100, "status": "Running"}

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("tt1234567")
        assert result == "Returning Series"

    @patch('tvmaze_client.HttpClient')
    def test_status_tbd(self, mock_http_cls):
        """TVMaze status='To Be Determined' -> 'Returning Series'."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 100, "status": "To Be Determined"}

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("tt1234567")
        assert result == "Returning Series"

    @patch('tvmaze_client.HttpClient')
    def test_status_in_development(self, mock_http_cls):
        """TVMaze status='In Development' -> 'In Production'."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 100, "status": "In Development"}

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("tt1234567")
        assert result == "In Production"

    @patch('tvmaze_client.HttpClient')
    def test_status_unknown(self, mock_http_cls):
        """Unknown TVMaze status -> '' + warning."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 100, "status": "Hiatus"}

        logger = MagicMock()
        client = TvmazeClient(logger=logger)
        result = client.get_show_status("tt1234567")
        assert result == ""
        logger.warning.assert_called()

    @patch('tvmaze_client.HttpClient')
    def test_status_show_not_found(self, mock_http_cls):
        """404 from TVMaze -> ''."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = HttpError(404, "Not Found", "url")

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("tt0000000")
        assert result == ""

    @patch('tvmaze_client.HttpClient')
    def test_status_http_error(self, mock_http_cls):
        """HTTP error -> ''."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = HttpError(500, "Server Error", "url")

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("tt1234567")
        assert result == ""

    @patch('tvmaze_client.HttpClient')
    def test_status_title_fallback(self, mock_http_cls):
        """No imdb_id, title fallback -> singlesearch used."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 169, "status": "Ended"}

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("", title_original="Breaking Bad")
        assert result == "Ended"
        mock_http.get_json.assert_called_once_with("/singlesearch/shows", {"q": "Breaking Bad"})

    @patch('tvmaze_client.HttpClient')
    def test_status_no_ids(self, mock_http_cls):
        """No imdb_id and no title -> ''."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = TvmazeClient(logger=MagicMock())
        result = client.get_show_status("", title_original="")
        assert result == ""
        mock_http.get_json.assert_not_called()

    @patch('tvmaze_client.HttpClient')
    def test_status_cache_hit(self, mock_http_cls):
        """Second call -> cached, no extra HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 169, "status": "Ended"}

        client = TvmazeClient(logger=MagicMock())
        r1 = client.get_show_status("tt0903747")
        r2 = client.get_show_status("tt0903747")
        assert r1 == r2 == "Ended"
        mock_http.get_json.assert_called_once()

    @patch('tvmaze_client.HttpClient')
    def test_status_populates_show_cache(self, mock_http_cls):
        """get_show_status populates _show_cache as side effect."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 169, "status": "Ended"}

        client = TvmazeClient(logger=MagicMock())
        client.get_show_status("tt0903747")
        assert _show_cache.get("tt0903747") == 169


# ---------------------------------------------------------------------------
# Tests for get_episode_image
# ---------------------------------------------------------------------------

class TestGetEpisodeImage:

    @patch('tvmaze_client.HttpClient')
    def test_episode_with_image(self, mock_http_cls):
        """Episode has both original and medium image URLs."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},  # lookup
            [{"season": 1, "number": 1, "image": {
                "original": "https://img/original.jpg",
                "medium": "https://img/medium.jpg",
            }}],  # episodes
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt1234567", 1, 1)
        assert result == ("https://img/original.jpg", "https://img/medium.jpg")

    @patch('tvmaze_client.HttpClient')
    def test_episode_image_null(self, mock_http_cls):
        """Episode image is null -> ("", "")."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "image": None}],
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt1234567", 1, 1)
        assert result == ("", "")

    @patch('tvmaze_client.HttpClient')
    def test_episode_no_image_key(self, mock_http_cls):
        """Episode has no 'image' key at all -> ("", "")."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1}],
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt1234567", 1, 1)
        assert result == ("", "")

    @patch('tvmaze_client.HttpClient')
    def test_episode_original_only(self, mock_http_cls):
        """Only original, no medium -> use original for both."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "image": {"original": "https://img/original.jpg"}}],
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt1234567", 1, 1)
        assert result == ("https://img/original.jpg", "https://img/original.jpg")

    @patch('tvmaze_client.HttpClient')
    def test_episode_medium_only(self, mock_http_cls):
        """Only medium, no original -> use medium for both."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "image": {"medium": "https://img/medium.jpg"}}],
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt1234567", 1, 1)
        assert result == ("https://img/medium.jpg", "https://img/medium.jpg")

    @patch('tvmaze_client.HttpClient')
    def test_episode_not_found(self, mock_http_cls):
        """Season/episode mismatch -> ("", "")."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},
            [{"season": 1, "number": 1, "image": {"original": "https://img.jpg"}}],
        ]

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt1234567", 2, 5)
        assert result == ("", "")

    @patch('tvmaze_client.HttpClient')
    def test_show_not_found(self, mock_http_cls):
        """Show not found -> ("", "")."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = HttpError(404, "Not Found", "url")

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("tt0000000", 1, 1)
        assert result == ("", "")

    @patch('tvmaze_client.HttpClient')
    def test_no_ids(self, mock_http_cls):
        """No imdb_id and no title -> ("", "")."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        client = TvmazeClient(logger=MagicMock())
        result = client.get_episode_image("", 1, 1, title_original="")
        assert result == ("", "")
        mock_http.get_json.assert_not_called()

    @patch('tvmaze_client.HttpClient')
    def test_cache_hit(self, mock_http_cls):
        """Second call for same show -> episodes from _episodes_cache, no extra HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = [
            {"id": 100},  # lookup
            [{"season": 1, "number": 1, "image": {"original": "https://img.jpg", "medium": "https://med.jpg"}}],
        ]

        client = TvmazeClient(logger=MagicMock())
        r1 = client.get_episode_image("tt1234567", 1, 1)
        r2 = client.get_episode_image("tt1234567", 1, 1)
        assert r1 == r2
        # lookup + episodes = 2 calls for first invocation, 0 for second (cached)
        assert mock_http.get_json.call_count == 2


# ---------------------------------------------------------------------------
# Tests for circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    @patch('tvmaze_client.HttpClient')
    def test_circuit_breaker_trips_after_threshold(self, mock_http_cls):
        """2 consecutive failures -> circuit open -> subsequent calls return fallback."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = Exception("Connection timed out")

        client = TvmazeClient(logger=MagicMock())

        # First failure
        r1 = client.lookup_show("tt1111111")
        assert r1 is None
        assert tvmaze_client._circuit_open is False

        # Second failure -> circuit trips
        r2 = client.lookup_show("tt2222222")
        assert r2 is None
        assert tvmaze_client._circuit_open is True

        # Third call -> circuit open, no HTTP
        mock_http.get_json.reset_mock()
        r3 = client.lookup_show("tt3333333")
        assert r3 is None
        mock_http.get_json.assert_not_called()

    @patch('tvmaze_client.HttpClient')
    def test_circuit_breaker_resets_on_success(self, mock_http_cls):
        """Success after failure -> circuit stays closed."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        # First call fails
        mock_http.get_json.side_effect = Exception("timeout")
        client = TvmazeClient(logger=MagicMock())
        client.lookup_show("tt1111111")
        assert tvmaze_client._circuit_failures == 1
        assert tvmaze_client._circuit_open is False

        # Second call succeeds -> reset
        mock_http.get_json.side_effect = None
        mock_http.get_json.return_value = {"id": 100}
        client.lookup_show("tt2222222")
        assert tvmaze_client._circuit_failures == 0
        assert tvmaze_client._circuit_open is False

    @patch('tvmaze_client.HttpClient')
    def test_circuit_breaker_404_is_not_failure(self, mock_http_cls):
        """404 means API is healthy -> records success, not failure."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = HttpError(404, "Not Found", "url")

        client = TvmazeClient(logger=MagicMock())
        client.lookup_show("tt1111111")
        client.lookup_show("tt2222222")
        assert tvmaze_client._circuit_failures == 0
        assert tvmaze_client._circuit_open is False

    @patch('tvmaze_client.HttpClient')
    def test_circuit_breaker_all_methods_return_fallback(self, mock_http_cls):
        """When circuit is open, all methods return their fallback values."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http

        # Force circuit open
        tvmaze_client._circuit_open = True
        tvmaze_client._circuit_failures = 2

        client = TvmazeClient(logger=MagicMock())

        assert client.lookup_show("tt1234567") is None
        assert client.search_show("Test") is None
        assert client.search_imdb_id("Test") is None
        assert client.get_episodes(100) is None
        assert client.get_seasons(100) is None
        assert client.get_show_status("tt1234567") == ""
        assert client.get_tvdb_id("tt1234567") is None
        assert client.get_episode_plot("tt1234567", 1, 1) is None
        assert client.get_episode_crew("tt1234567", 1, 1) == ([], [])
        assert client.get_episode_image("tt1234567", 1, 1) == ("", "")

        # No HTTP calls should have been made
        mock_http.get_json.assert_not_called()

    @patch('tvmaze_client.HttpClient')
    def test_get_show_status_uses_lookup_cache(self, mock_http_cls):
        """lookup_show populates _show_data_cache, get_show_status uses it -> 0 extra HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 169, "status": "Ended"}

        client = TvmazeClient(logger=MagicMock())

        # lookup_show first
        show_id = client.lookup_show("tt0903747")
        assert show_id == 169
        assert mock_http.get_json.call_count == 1

        # get_show_status uses _show_data_cache -> no extra HTTP
        status = client.get_show_status("tt0903747")
        assert status == "Ended"
        assert mock_http.get_json.call_count == 1  # still 1

    @patch('tvmaze_client.HttpClient')
    def test_get_tvdb_id_uses_lookup_cache(self, mock_http_cls):
        """lookup_show populates _show_data_cache, get_tvdb_id uses it -> 0 extra HTTP."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.return_value = {"id": 82, "externals": {"thetvdb": 121361}}

        client = TvmazeClient(logger=MagicMock())

        # lookup_show first
        show_id = client.lookup_show("tt0944947")
        assert show_id == 82
        assert mock_http.get_json.call_count == 1

        # get_tvdb_id uses _show_data_cache -> no extra HTTP
        tvdb_id = client.get_tvdb_id("tt0944947")
        assert tvdb_id == 121361
        assert mock_http.get_json.call_count == 1  # still 1

    @patch('tvmaze_client.HttpClient')
    def test_circuit_breaker_logs_warning_once(self, mock_http_cls):
        """Circuit breaker logs WARNING only on transition, not on every skipped call."""
        mock_http = MagicMock()
        mock_http_cls.return_value = mock_http
        mock_http.get_json.side_effect = Exception("timeout")

        logger = MagicMock()
        client = TvmazeClient(logger=logger)

        client.lookup_show("tt1111111")  # failure 1
        client.lookup_show("tt2222222")  # failure 2 -> trips

        # Count warning calls that contain "circuit breaker tripped"
        trip_warnings = [
            call for call in logger.warning.call_args_list
            if "circuit breaker tripped" in str(call)
        ]
        assert len(trip_warnings) == 1

        # More calls -> no additional trip warnings
        client.lookup_show("tt3333333")
        client.search_show("Test")
        trip_warnings = [
            call for call in logger.warning.call_args_list
            if "circuit breaker tripped" in str(call)
        ]
        assert len(trip_warnings) == 1  # still 1
