"""Tests for Collections / Sagas feature (KOD-7, Phase 2.1)."""

from unittest.mock import patch, MagicMock

import pytest

from kinopoisk_api import KinopoiskClient
from http_client import HttpError
from logger import Logger
from settings_manager import SettingsManager
from models import MovieDetails, DataSource
from utils import extract_franchise_name, _longest_common_prefix
from scraper import _handle_getdetails, _apply_movie_details_to_listitem
import xbmc
import xbmcgui
import xbmcplugin
import scraper as scraper_module


# ---------------------------------------------------------------------------
# Autouse fixture: reset all Kodi mocks between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_kodi_mocks():
    xbmc.reset_mock()
    xbmcgui.reset_mock()
    xbmcplugin.reset_mock()
    scraper_module._kp_unavailable = False
    scraper_module._kp_unavailable_notified = False
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kp_client():
    logger = MagicMock(spec=Logger)
    return KinopoiskClient("test-api-key", logger), logger


def _mock_settings(enable_collections=True, api_key="test-key"):
    s = MagicMock(spec=SettingsManager)
    s.kinopoisk_api_key = api_key
    s.enable_collections = enable_collections
    s.show_ratings_in_plot = False
    s.omdb_api_key = ""
    s.fetch_actor_photos = False
    s.preferred_rating_source = DataSource.KINOPOISK
    return s


def _mock_logger():
    return MagicMock(spec=Logger)


# ---------------------------------------------------------------------------
# get_sequels() tests
# ---------------------------------------------------------------------------

class TestGetSequels:
    @patch("kinopoisk_api._kp_global_limiter")
    def test_returns_list_of_dicts(self, _limiter):
        client, _ = _make_kp_client()
        payload = [
            {"filmId": 2, "nameRu": "Матрица: Перезагрузка", "relationType": "SEQUEL"},
            {"filmId": 3, "nameRu": "Матрица: Революция", "relationType": "SEQUEL"},
        ]
        with patch.object(client._http, "get_json", return_value=payload):
            result = client.get_sequels(301)
        assert result == payload

    @patch("kinopoisk_api._kp_global_limiter")
    def test_404_returns_empty_list(self, _limiter):
        client, logger = _make_kp_client()
        with patch.object(
            client._http, "get_json",
            side_effect=HttpError(404, "Not Found", "url"),
        ):
            result = client.get_sequels(999)
        assert result == []
        # 404 should be logged as info, not error
        logger.info.assert_called()
        logger.error.assert_not_called()

    @patch("kinopoisk_api._kp_global_limiter")
    def test_http_error_non_404_returns_empty_and_logs_error(self, _limiter):
        client, logger = _make_kp_client()
        with patch.object(
            client._http, "get_json",
            side_effect=HttpError(500, "Server Error", "url"),
        ):
            result = client.get_sequels(301)
        assert result == []
        logger.error.assert_called()

    @patch("kinopoisk_api._kp_global_limiter")
    def test_unexpected_response_type_returns_empty(self, _limiter):
        client, logger = _make_kp_client()
        with patch.object(client._http, "get_json", return_value={"message": "unexpected"}):
            result = client.get_sequels(301)
        assert result == []
        logger.warning.assert_called()

    @patch("kinopoisk_api._kp_global_limiter")
    def test_uses_v21_endpoint(self, _limiter):
        client, _ = _make_kp_client()
        with patch.object(client._http, "get_json", return_value=[]) as mock_get:
            client.get_sequels(301)
        call_path = mock_get.call_args[0][0]
        assert "v2.1" in call_path
        assert "sequels_and_prequels" in call_path

    @patch("kinopoisk_api._kp_global_limiter")
    def test_empty_list_response(self, _limiter):
        client, _ = _make_kp_client()
        with patch.object(client._http, "get_json", return_value=[]):
            result = client.get_sequels(301)
        assert result == []


# ---------------------------------------------------------------------------
# _longest_common_prefix() tests
# ---------------------------------------------------------------------------

class TestLongestCommonPrefix:
    def test_empty_list(self):
        assert _longest_common_prefix([]) == ""

    def test_single_element(self):
        assert _longest_common_prefix(["Матрица"]) == "Матрица"

    def test_all_identical(self):
        assert _longest_common_prefix(["Foo", "Foo", "Foo"]) == "Foo"

    def test_no_common_prefix(self):
        assert _longest_common_prefix(["ABC", "XYZ"]) == ""

    def test_partial_prefix(self):
        assert _longest_common_prefix(["Матрица", "Матрица: Перезагрузка"]) == "Матрица"

    def test_single_char_common(self):
        assert _longest_common_prefix(["Аа", "Аб"]) == "А"

    def test_strings_with_spaces(self):
        assert _longest_common_prefix(["The Matrix", "The Matrix Reloaded"]) == "The Matrix"

    def test_empty_string_in_list(self):
        assert _longest_common_prefix(["", "Foo"]) == ""


# ---------------------------------------------------------------------------
# extract_franchise_name() tests (AC-03, AC-06, AC-07, AC-08)
# ---------------------------------------------------------------------------

class TestExtractFranchiseName:
    def test_matrix_lcp(self):
        # AC-08: "Матрица: Перезагрузка" → "Матрица"
        result = extract_franchise_name(
            "Матрица",
            ["Матрица: Перезагрузка", "Матрица: Революция"],
        )
        assert result == "Матрица"

    def test_terminator_fallback(self):
        # AC-08: "Терминатор 2: Судный день" → "Терминатор"
        result = extract_franchise_name(
            "Терминатор 2: Судный день",
            ["Терминатор 3: Восстание машин"],
        )
        assert result == "Терминатор"

    def test_subtitle_only_fallback(self):
        result = extract_franchise_name(
            "Матрица: Перезагрузка",
            ["Хоббит: Нежданное путешествие"],
        )
        assert result == "Матрица"

    def test_cross_franchise_lotr_hobbit_fallback(self):
        # AC-03: LCP of "Властелин колец: Братство кольца" and "Хоббит: Нежданное путешествие"
        # LCP is empty → fallback to current title stripping
        result = extract_franchise_name(
            "Властелин колец: Братство кольца",
            ["Хоббит: Нежданное путешествие"],
        )
        assert result == "Властелин колец"

    def test_lcp_too_short_uses_fallback(self):
        result = extract_franchise_name("АБ: Субтитр", ["Вг: Другой"])
        # LCP = "" (< 2) → fallback strips ": Субтитр"
        assert result == "АБ"

    def test_no_related_titles_fallback_applied(self):
        # When related_titles is empty, all_titles = [current_title]
        # LCP = current_title → may be ≥ 2 chars → returned as-is if no trailing punctuation
        result = extract_franchise_name("Матрица", [])
        assert result == "Матрица"

    def test_remake_entries_excluded_in_caller(self):
        # REMAKE filtering happens in scraper, not in extract_franchise_name.
        # Test that if only SEQUEL titles are passed, they're used correctly.
        result = extract_franchise_name(
            "Матрица",
            ["Матрица: Перезагрузка"],
        )
        assert result == "Матрица"

    def test_trailing_colon_stripped_from_lcp(self):
        # If LCP ends with "Матрица:" — trailing chars stripped
        result = extract_franchise_name(
            "Матрица: Перезагрузка",
            ["Матрица: Революция"],
        )
        assert not result.endswith(":")
        assert result == "Матрица"

    def test_trailing_dash_stripped(self):
        result = extract_franchise_name("Форсаж - Drift", ["Форсаж - Tokyo"])
        # LCP = "Форсаж " or "Форсаж", stripped of trailing " -"
        assert result.startswith("Форсаж")
        assert not result.endswith(" ")

    def test_number_in_title_stripped(self):
        result = extract_franchise_name(
            "Терминатор 3: Восстание машин",
            ["Терминатор 2: Судный день"],
        )
        assert result == "Терминатор"

    def test_nameoriginal_fallback_title(self):
        # AC-06: prefer nameRu, fallback to nameOriginal — this is handled in scraper,
        # but ensure extract_franchise_name works with Latin titles too
        result = extract_franchise_name(
            "The Matrix",
            ["The Matrix Reloaded", "The Matrix Revolutions"],
        )
        assert result == "The Matrix"


# ---------------------------------------------------------------------------
# Scraper integration tests for collections logic
# ---------------------------------------------------------------------------

class TestHandleGetdetailsCollections:
    def _minimal_details(self):
        return MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            title_original="The Matrix",
            year=1999,
        )

    def _setup_client_with_details(self, mock_client, details):
        """Configure mock client for cache-miss flow (fetch_raw + parse)."""
        mock_client.fetch_details_raw.return_value = {"kinopoiskId": 301}
        mock_client.parse_details.return_value = details
        mock_client.fetch_staff_raw.return_value = []
        mock_client.parse_staff.return_value = ([], [], [])

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_ac01_sequels_set_franchise(self, MockKp, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockKp.return_value
        self._setup_client_with_details(mock_client, self._minimal_details())
        mock_client.get_sequels.return_value = [
            {"filmId": 2, "nameRu": "Матрица: Перезагрузка", "relationType": "SEQUEL"},
            {"filmId": 3, "nameRu": "Матрица: Революция", "relationType": "SEQUEL"},
        ]

        settings = _mock_settings(enable_collections=True)
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}, "handle": 1}

        _handle_getdetails(params, 1, settings, logger)

        mock_client.get_sequels.assert_called_once_with(301)
        set_call = xbmcplugin.setResolvedUrl.call_args
        listitem_arg = set_call[0][2]
        infotag = listitem_arg.getVideoInfoTag()
        infotag.setSet.assert_called_once_with("Матрица")

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_ac02_standalone_no_set_call(self, MockKp, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockKp.return_value
        self._setup_client_with_details(mock_client, self._minimal_details())
        mock_client.get_sequels.return_value = []

        settings = _mock_settings(enable_collections=True)
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}, "handle": 1}

        _handle_getdetails(params, 1, settings, logger)

        set_call = xbmcplugin.setResolvedUrl.call_args
        listitem_arg = set_call[0][2]
        infotag = listitem_arg.getVideoInfoTag()
        infotag.setSet.assert_not_called()

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_ac04_collections_disabled_no_api_call(self, MockKp, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockKp.return_value
        self._setup_client_with_details(mock_client, self._minimal_details())

        settings = _mock_settings(enable_collections=False)
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}, "handle": 1}

        _handle_getdetails(params, 1, settings, logger)

        mock_client.get_sequels.assert_not_called()

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_ac05_sequels_error_graceful_degradation(self, MockKp, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockKp.return_value
        self._setup_client_with_details(mock_client, self._minimal_details())
        mock_client.get_sequels.side_effect = Exception("network error")

        settings = _mock_settings(enable_collections=True)
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}, "handle": 1}

        # Should not raise, should still succeed
        result = _handle_getdetails(params, 1, settings, logger)
        assert result is True
        xbmcplugin.setResolvedUrl.assert_called_once()

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_ac07_remakes_excluded(self, MockKp, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockKp.return_value
        self._setup_client_with_details(mock_client, self._minimal_details())
        # Only REMAKE entries — should not trigger setSet
        mock_client.get_sequels.return_value = [
            {"filmId": 99, "nameRu": "Матрица (ремейк)", "relationType": "REMAKE"},
        ]

        settings = _mock_settings(enable_collections=True)
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}, "handle": 1}

        _handle_getdetails(params, 1, settings, logger)

        set_call = xbmcplugin.setResolvedUrl.call_args
        listitem_arg = set_call[0][2]
        infotag = listitem_arg.getVideoInfoTag()
        infotag.setSet.assert_not_called()

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_ac06_nameoriginal_fallback_when_nameru_empty(self, MockKp, MockCache):
        MockCache.return_value.get.return_value = None
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="The Matrix",
            title_original="The Matrix",
            year=1999,
        )
        mock_client = MockKp.return_value
        self._setup_client_with_details(mock_client, details)
        mock_client.get_sequels.return_value = [
            {"filmId": 2, "nameRu": "", "nameOriginal": "The Matrix Reloaded", "relationType": "SEQUEL"},
        ]

        settings = _mock_settings(enable_collections=True)
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}, "handle": 1}

        _handle_getdetails(params, 1, settings, logger)

        set_call = xbmcplugin.setResolvedUrl.call_args
        listitem_arg = set_call[0][2]
        infotag = listitem_arg.getVideoInfoTag()
        infotag.setSet.assert_called_once_with("The Matrix")


# ---------------------------------------------------------------------------
# _apply_movie_details_to_listitem with set_name
# ---------------------------------------------------------------------------

class TestApplyMovieDetailsSetName:
    def _make_listitem(self):
        return MagicMock()

    def test_set_name_calls_setset(self):
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            set_name="Матрица",
        )
        listitem = self._make_listitem()
        settings = _mock_settings()
        logger = _mock_logger()

        _apply_movie_details_to_listitem(details, listitem, settings, logger)

        infotag = listitem.getVideoInfoTag()
        infotag.setSet.assert_called_once_with("Матрица")

    def test_empty_set_name_no_setset_call(self):
        details = MovieDetails(kinopoisk_id=301, title_ru="Матрица", set_name="")
        listitem = self._make_listitem()
        settings = _mock_settings()
        logger = _mock_logger()

        _apply_movie_details_to_listitem(details, listitem, settings, logger)

        infotag = listitem.getVideoInfoTag()
        infotag.setSet.assert_not_called()
