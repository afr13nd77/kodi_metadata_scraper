import sys
import json
import urllib.parse
import pytest
from unittest.mock import patch, MagicMock, call
import xbmc
import xbmcgui
import xbmcplugin
from scraper import (
    run, _handle_find, _handle_getdetails,
    _handle_nfo, _handle_getartwork, _apply_movie_details_to_listitem,
    _enrich_with_omdb,
)
from utils import (
    get_params, extract_kinopoisk_id, extract_imdb_id,
    clean_title, _decode_value, transliterate_to_cyrillic,
)
from models import (
    MovieSearchResult, MovieDetails, Rating, Person, Artwork,
    DataSource, ArtworkType, ProfessionType
)
from logger import Logger
from settings_manager import SettingsManager
from omdb_client import OmdbRatings
import scraper as scraper_module


@pytest.fixture(autouse=True)
def reset_kodi_mocks():
    """Reset all Kodi module-level MagicMocks between tests."""
    xbmc.reset_mock()
    xbmcgui.reset_mock()
    xbmcplugin.reset_mock()
    # Reset module-level globals in scraper
    scraper_module._kp_unavailable = False
    scraper_module._kp_unavailable_notified = False
    yield


def _mock_settings(api_key="test-key", preferred_rating=DataSource.KINOPOISK,
                   fetch_photos=True, debug=False, auto_select_exact_match=True,
                   enable_dual_search=True, omdb_api_key="",
                   show_ratings_in_plot=False, enable_collections=False,
                   enable_award_tags=True, genre_language="ru"):
    settings = MagicMock(spec=SettingsManager)
    settings.kinopoisk_api_key = api_key
    settings.preferred_rating_source = preferred_rating
    settings.fetch_actor_photos = fetch_photos
    settings.debug_logging = debug
    settings.auto_select_exact_match = auto_select_exact_match
    settings.enable_dual_search = enable_dual_search
    settings.omdb_api_key = omdb_api_key
    settings.show_ratings_in_plot = show_ratings_in_plot
    settings.enable_collections = enable_collections
    settings.enable_award_tags = enable_award_tags
    settings.genre_language = genre_language
    return settings


def _mock_logger():
    return MagicMock(spec=Logger)


class TestGetParams:
    def test_parse_query_string(self):
        with patch.object(sys, "argv", ["plugin://", "1", "?action=find&title=Matrix"]):
            params = get_params()
            assert params["handle"] == 1
            assert params["action"] == "find"
            assert params["title"] == "Matrix"

    def test_parse_query_no_question_mark(self):
        with patch.object(sys, "argv", ["plugin://", "2", "action=getdetails&url=test"]):
            params = get_params()
            assert params["handle"] == 2
            assert params["action"] == "getdetails"
            assert params["url"] == "test"

    def test_handle_only(self):
        with patch.object(sys, "argv", ["plugin://", "1"]):
            params = get_params()
            assert params == {"handle": 1}

    def test_empty_query_string(self):
        with patch.object(sys, "argv", ["plugin://", "1", ""]):
            params = get_params()
            assert params == {"handle": 1}

    def test_cyrillic_title_utf8_percent_encoded(self):
        """Kodi passes Cyrillic titles as UTF-8 percent-encoded strings."""
        cyrillic_title = "Терминатор"
        encoded_title = urllib.parse.quote(cyrillic_title, safe="")
        qs = f"?action=find&title={encoded_title}"
        with patch.object(sys, "argv", ["plugin://", "1", qs]):
            params = get_params()
            assert params["handle"] == 1
            assert params["action"] == "find"
            assert params["title"] == cyrillic_title

    def test_cyrillic_title_cp1251_percent_encoded(self):
        """Kodi on Russian Windows encodes Cyrillic with cp1251 percent-encoding.

        This is the confirmed production case: title=%d2%e5%f0%ec%e8%ed%e0%f2%ee%f0
        is 'Терминатор' encoded in cp1251.
        """
        # Build cp1251 percent-encoded query string
        qs = "?action=find&title=%d2%e5%f0%ec%e8%ed%e0%f2%ee%f0&year=0"
        with patch.object(sys, "argv", ["plugin://", "1", qs]):
            params = get_params()
            assert params["handle"] == 1
            assert params["action"] == "find"
            assert params["title"] == "Терминатор"
            assert params["year"] == "0"

    def test_cyrillic_title_cp1251_mixed_with_ascii(self):
        """cp1251-encoded Cyrillic mixed with ASCII params."""
        # "Матрица" in cp1251: М=cc, а=e0, т=f2, р=f0, и=e8, ц=f6, а=e0
        qs = "?action=find&title=%cc%e0%f2%f0%e8%f6%e0&year=1999"
        with patch.object(sys, "argv", ["plugin://", "1", qs]):
            params = get_params()
            assert params["title"] == "Матрица"
            assert params["year"] == "1999"

    def test_cyrillic_title_unencoded(self):
        """Title already contains proper Cyrillic characters (no encoding needed).

        With latin-1 parsing, raw Cyrillic chars that are within the
        latin-1 range get passed through and then decoded as cp1251.
        Direct Cyrillic in the query string is unusual but should not crash.
        """
        # Note: Cyrillic chars U+0400+ are NOT representable in latin-1,
        # so parse_qsl with encoding='latin-1' would fail on raw Cyrillic.
        # This scenario is unlikely in production (Kodi always percent-encodes),
        # but we test that already-percent-encoded UTF-8 still works.
        cyrillic_title = "Терминатор"
        encoded_title = urllib.parse.quote(cyrillic_title, safe="")
        with patch.object(sys, "argv", ["plugin://", "1", f"?action=find&title={encoded_title}"]):
            params = get_params()
            assert params["title"] == "Терминатор"

    def test_pathsettings_json_preserved(self):
        """pathSettings JSON should be decoded correctly (pure ASCII after percent-decode)."""
        qs = (
            "?action=find"
            "&pathSettings=%7b%22debug_logging%22%3afalse%2c%22kinopoisk_api_key%22%3a%22test-key%22%7d"
            "&title=%d2%e5%f0%ec%e8%ed%e0%f2%ee%f0"
            "&year=0"
        )
        with patch.object(sys, "argv", ["plugin://", "1", qs]):
            params = get_params()
            assert params["title"] == "Терминатор"
            # pathSettings is JSON (pure ASCII after percent-decode)
            assert "debug_logging" in params["pathSettings"]


class TestDecodeValue:
    """Tests for _decode_value helper that decodes latin-1 parsed values."""

    def test_ascii_unchanged(self):
        assert _decode_value("hello world") == "hello world"

    def test_empty_string(self):
        assert _decode_value("") == ""

    def test_json_ascii_unchanged(self):
        """JSON strings (after percent-decode) are pure ASCII."""
        json_str = '{"debug_logging":false,"kinopoisk_api_key":"test"}'
        assert _decode_value(json_str) == json_str

    def test_utf8_bytes_decoded(self):
        """UTF-8 bytes stored as latin-1 chars should decode to Cyrillic."""
        # Simulate: parse_qsl with latin-1 decoded UTF-8 percent-encoding
        # "Терминатор" UTF-8 bytes passed through latin-1
        original = "Терминатор"
        latin1_str = original.encode("utf-8").decode("latin-1")
        assert _decode_value(latin1_str) == original

    def test_cp1251_bytes_decoded(self):
        """cp1251 bytes stored as latin-1 chars should decode to Cyrillic.

        This is the confirmed production case from Kodi on Russian Windows.
        """
        # "Терминатор" in cp1251 bytes, interpreted as latin-1 characters
        original = "Терминатор"
        cp1251_bytes = original.encode("cp1251")
        latin1_str = cp1251_bytes.decode("latin-1")
        assert _decode_value(latin1_str) == original

    def test_cp1251_matrix_decoded(self):
        """'Матрица' encoded as cp1251 should decode correctly."""
        original = "Матрица"
        latin1_str = original.encode("cp1251").decode("latin-1")
        assert _decode_value(latin1_str) == original

    def test_utf8_preferred_over_cp1251(self):
        """When bytes are valid UTF-8, UTF-8 decoding should win."""
        original = "Терминатор"
        # UTF-8 encoding
        latin1_str = original.encode("utf-8").decode("latin-1")
        result = _decode_value(latin1_str)
        assert result == original

    def test_numeric_string(self):
        """Numeric strings are ASCII and returned as-is."""
        assert _decode_value("1999") == "1999"
        assert _decode_value("0") == "0"


class TestExtractKinopoiskId:
    def test_from_uniqueids_dict(self):
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_from_uniqueIDs_camelcase(self):
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_from_params_direct(self):
        logger = _mock_logger()
        params = {"kinopoisk": "301"}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_from_uniqueids_string(self):
        logger = _mock_logger()
        params = {"uniqueids": '{"kinopoisk": "301"}'}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_from_url_param_json(self):
        logger = _mock_logger()
        params = {"url": '{"kinopoisk": "301", "imdb": "tt0133093"}'}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_no_id(self):
        logger = _mock_logger()
        assert extract_kinopoisk_id({}, logger) == 0


class TestExtractImdbId:
    def test_from_uniqueids_dict(self):
        logger = _mock_logger()
        params = {"uniqueids": {"imdb": "tt0133093"}}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_from_uniqueIDs_camelcase(self):
        logger = _mock_logger()
        params = {"uniqueIDs": {"imdb": "tt0133093"}}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_from_url_param_json(self):
        logger = _mock_logger()
        params = {"url": '{"imdb": "tt0133093"}'}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_from_params_direct(self):
        logger = _mock_logger()
        params = {"imdb": "tt0133093"}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_no_id(self):
        logger = _mock_logger()
        assert extract_imdb_id({}, logger) == ""


class TestHandleFind:
    @patch("scraper.KinopoiskClient")
    def test_find_with_results(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            MovieSearchResult(
                title_ru="Матрица",
                title_original="The Matrix",
                year=1999,
                kinopoisk_id=301,
                poster_url="https://poster.url/301.jpg"
            )
        ]
        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        # URL should be JSON, not urlencode
        call_kwargs = xbmcplugin.addDirectoryItem.call_args
        url_arg = call_kwargs[1]["url"] if "url" in call_kwargs[1] else call_kwargs[0][1]
        parsed = json.loads(url_arg)
        assert parsed["kinopoisk"] == "301"
        # endOfDirectory is now centralized in run(), not called here
        xbmcplugin.endOfDirectory.assert_not_called()

    def test_find_empty_title(self):
        settings = _mock_settings()
        logger = _mock_logger()

        _handle_find({"title": ""}, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()
        # endOfDirectory is now centralized in run()
        xbmcplugin.endOfDirectory.assert_not_called()

    def test_find_no_api_key(self):
        settings = _mock_settings(api_key="")
        logger = _mock_logger()

        _handle_find({"title": "Matrix"}, 1, settings, logger)

        xbmc.executebuiltin.assert_called_once()
        # endOfDirectory is now centralized in run()
        xbmcplugin.endOfDirectory.assert_not_called()


class TestAutoSelectExactMatch:
    """Tests for auto-select behavior in _handle_find (AC-01..AC-05)."""

    def _make_result(self, title_ru="Терминатор", year=1984, kp_id=301):
        return MovieSearchResult(
            title_ru=title_ru,
            title_original="The Terminator",
            year=year,
            kinopoisk_id=kp_id,
        )

    @patch("scraper.KinopoiskClient")
    def test_auto_select_exact_match_logs(self, MockClient):
        """AC-01: 1 result + exact title + year + setting on → log auto-selected."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result()]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Терминатор", "year": "1984"}

        _handle_find(params, 1, settings, logger)

        logger.info.assert_any_call(
            "_handle_find: auto-selected exact match: kp_id=301"
        )
        xbmcplugin.addDirectoryItem.assert_called_once()

    @patch("scraper.KinopoiskClient")
    def test_auto_select_multiple_results_no_autoselect(self, MockClient):
        """AC-02: 3 results → all added, no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result("Дюна", 2021, 1),
            self._make_result("Дюна", 1984, 2),
            self._make_result("Дюна: Часть вторая", 2024, 3),
        ]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Дюна"}

        _handle_find(params, 1, settings, logger)

        assert xbmcplugin.addDirectoryItem.call_count == 3
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("scraper.KinopoiskClient")
    def test_auto_select_disabled_no_log(self, MockClient):
        """AC-03: setting=false, 1 result with exact match → no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result()]

        settings = _mock_settings(auto_select_exact_match=False)
        logger = _mock_logger()
        params = {"title": "Терминатор", "year": "1984"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("scraper.KinopoiskClient")
    def test_auto_select_title_mismatch_no_log(self, MockClient):
        """AC-04: 1 result with title_ru='Терминатор 2' → no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result("Терминатор 2", 1991, 302)]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Терминатор", "year": "1984"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("scraper.KinopoiskClient")
    def test_auto_select_no_year_no_log(self, MockClient):
        """AC-05: year=None from Kodi → no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result()]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Терминатор"}  # no year

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("scraper.KinopoiskClient")
    def test_auto_select_case_insensitive(self, MockClient):
        """Auto-select works case-insensitively: 'терминатор' vs 'Терминатор'."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result("Терминатор", 1984)]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "терминатор", "year": "1984"}

        _handle_find(params, 1, settings, logger)

        logger.info.assert_any_call(
            "_handle_find: auto-selected exact match: kp_id=301"
        )

    @patch("scraper.KinopoiskClient")
    def test_auto_select_year_mismatch_no_log(self, MockClient):
        """1 result, title matches but year differs → no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result("Терминатор", 1991, 302)]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Терминатор", "year": "1984"}

        _handle_find(params, 1, settings, logger)

        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)


class TestHandleGetdetails:
    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_getdetails_success(self, MockClient, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"kinopoiskId": 301}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            title_original="The Matrix",
            year=1999,
            plot="Описание фильма",
            ratings=[Rating(DataSource.KINOPOISK, 8.5, 10000)]
        )
        mock_client.fetch_staff_raw.return_value = []
        mock_client.parse_staff.return_value = (
            [Person(name_ru="Лана Вачовски", profession=ProfessionType.DIRECTOR)],
            [],
            [Person(name_ru="Киану Ривз", role="Neo", profession=ProfessionType.ACTOR)]
        )

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}

        _handle_getdetails(params, 1, settings, logger)

        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][0] == 1
        assert args[0][1] is True

    @patch("scraper.KinopoiskClient")
    def test_getdetails_no_id(self, MockClient):
        settings = _mock_settings()
        logger = _mock_logger()

        _handle_getdetails({}, 1, settings, logger)

        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is False

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_getdetails_api_failure(self, MockClient, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}

        _handle_getdetails(params, 1, settings, logger)

        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is False


class TestHandleNfo:
    def test_nfo_with_kp_id(self):
        logger = _mock_logger()
        params = {"nfo": "https://www.kinopoisk.ru/film/301/"}

        _handle_nfo(params, 1, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        # URL should be JSON
        call_kwargs = xbmcplugin.addDirectoryItem.call_args
        url_arg = call_kwargs[1]["url"] if "url" in call_kwargs[1] else call_kwargs[0][1]
        parsed = json.loads(url_arg)
        assert parsed["kinopoisk"] == "301"
        # endOfDirectory is now centralized in run()
        xbmcplugin.endOfDirectory.assert_not_called()

    def test_nfo_with_imdb_id(self):
        logger = _mock_logger()
        params = {"nfo": '<uniqueid type="imdb">tt0133093</uniqueid>'}

        _handle_nfo(params, 1, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        # URL should be JSON
        call_kwargs = xbmcplugin.addDirectoryItem.call_args
        url_arg = call_kwargs[1]["url"] if "url" in call_kwargs[1] else call_kwargs[0][1]
        parsed = json.loads(url_arg)
        assert parsed["imdb"] == "tt0133093"
        # endOfDirectory is now centralized in run()
        xbmcplugin.endOfDirectory.assert_not_called()

    def test_nfo_empty(self):
        logger = _mock_logger()
        params = {"nfo": ""}

        _handle_nfo(params, 1, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()
        # endOfDirectory is now centralized in run()
        xbmcplugin.endOfDirectory.assert_not_called()

    def test_nfo_no_ids(self):
        logger = _mock_logger()
        params = {"nfo": "random garbage content"}

        _handle_nfo(params, 1, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()
        # endOfDirectory is now centralized in run()
        xbmcplugin.endOfDirectory.assert_not_called()


class TestGetdetailsReturnValue:
    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_returns_true_on_success(self, MockClient, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"kinopoiskId": 301}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=301, title_ru="Матрица", title_original="The Matrix",
            year=1999, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = []
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}

        result = _handle_getdetails(params, 1, settings, logger)
        assert result is True

    @patch("scraper.KinopoiskClient")
    def test_returns_false_on_no_id(self, MockClient):
        settings = _mock_settings()
        logger = _mock_logger()

        result = _handle_getdetails({}, 1, settings, logger)
        assert result is False

    @patch("scraper.FileCache")
    @patch("scraper.KinopoiskClient")
    def test_returns_false_on_api_failure(self, MockClient, MockCache):
        MockCache.return_value.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}

        result = _handle_getdetails(params, 1, settings, logger)
        assert result is False


class TestRunEndOfDirectory:
    @patch("scraper.SettingsManager")
    @patch("scraper.Logger")
    def test_find_calls_endofdirectory(self, MockLogger, MockSettings):
        MockSettings.return_value = _mock_settings()
        with patch.object(sys, "argv", ["plugin://", "1", "?action=find&title="]):
            run()
            xbmcplugin.endOfDirectory.assert_called_once_with(1)

    @patch("scraper.FileCache")
    @patch("scraper.SettingsManager")
    @patch("scraper.Logger")
    @patch("scraper.KinopoiskClient")
    def test_getdetails_success_no_endofdirectory(self, MockClient, MockLogger, MockSettings, MockCache):
        MockCache.return_value.get.return_value = None
        MockSettings.return_value = _mock_settings()
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"kinopoiskId": 301}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=301, title_ru="Матрица", title_original="The Matrix",
            year=1999, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = []
        mock_client.parse_staff.return_value = ([], [], [])
        with patch.object(sys, "argv", ["plugin://", "1", "?action=getdetails&url=%7B%22kinopoisk%22%3A%22301%22%7D"]):
            run()
            # getdetails success -> enddir = not True = False -> endOfDirectory NOT called
            xbmcplugin.endOfDirectory.assert_not_called()

    @patch("scraper.FileCache")
    @patch("scraper.SettingsManager")
    @patch("scraper.Logger")
    @patch("scraper.KinopoiskClient")
    def test_getdetails_failure_calls_endofdirectory(self, MockClient, MockLogger, MockSettings, MockCache):
        MockCache.return_value.get.return_value = None
        MockSettings.return_value = _mock_settings()
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None
        with patch.object(sys, "argv", ["plugin://", "1", "?action=getdetails&url=%7B%22kinopoisk%22%3A%22301%22%7D"]):
            run()
            # getdetails failure -> enddir = not False = True -> endOfDirectory IS called
            xbmcplugin.endOfDirectory.assert_called_once_with(1)

    @patch("scraper.SettingsManager")
    @patch("scraper.Logger")
    def test_nfo_calls_endofdirectory(self, MockLogger, MockSettings):
        MockSettings.return_value = _mock_settings()
        with patch.object(sys, "argv", ["plugin://", "1", "?action=NfoUrl&nfo="]):
            run()
            xbmcplugin.endOfDirectory.assert_called_once_with(1)


class TestHandleGetartwork:
    @patch("scraper.KinopoiskClient")
    def test_getartwork_success(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.get_images.return_value = [
            Artwork(url="https://poster.jpg", artwork_type=ArtworkType.POSTER),
            Artwork(url="https://still.jpg", preview_url="https://still_sm.jpg", artwork_type=ArtworkType.FANART),
        ]

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}

        _handle_getartwork(params, 1, settings, logger)

        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is True

    @patch("scraper.KinopoiskClient")
    def test_getartwork_no_id(self, MockClient):
        settings = _mock_settings()
        logger = _mock_logger()

        _handle_getartwork({}, 1, settings, logger)

        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is False


class TestCleanTitle:
    """Tests for clean_title covering all supported title formats."""

    def test_clean_title_with_year_in_parens_and_slash(self):
        """Format: 'Люди Икс 2 / X-Men 2 (2003) [Open Matte]'"""
        logger = _mock_logger()
        candidates, year = clean_title(
            "Люди Икс 2 / X-Men 2 (2003) [Open Matte]", logger
        )
        assert candidates == ["Люди Икс 2", "X-Men 2"]
        assert year == "2003"

    def test_dotted_filename_with_year(self):
        """Format: 'The.Chronicles.of.Riddick.2004.HDTVRip.Open.Matte.Deadmauvlad'"""
        logger = _mock_logger()
        candidates, year = clean_title(
            "The.Chronicles.of.Riddick.2004.HDTVRip.Open.Matte.Deadmauvlad", logger
        )
        assert candidates == ["The Chronicles of Riddick"]
        assert year == "2004"

    def test_dotted_filename_without_year(self):
        """Format: 'The.Matrix.BDRip'"""
        logger = _mock_logger()
        candidates, year = clean_title("The.Matrix.BDRip", logger)
        # Without a recognizable year, the whole thing becomes one candidate
        assert candidates == ["The Matrix BDRip"]
        assert year == ""

    def test_simple_clean_title(self):
        """Format: 'Inception'"""
        logger = _mock_logger()
        candidates, year = clean_title("Inception", logger)
        assert candidates == ["Inception"]
        assert year == ""

    def test_title_with_underscores_and_year(self):
        """Format: 'The_Matrix_1999_BDRip'"""
        logger = _mock_logger()
        candidates, year = clean_title("The_Matrix_1999_BDRip", logger)
        assert candidates == ["The Matrix"]
        assert year == "1999"

    def test_already_clean_with_year_in_parens(self):
        """Format: 'Inception (2010)'"""
        logger = _mock_logger()
        candidates, year = clean_title("Inception (2010)", logger)
        assert candidates == ["Inception"]
        assert year == "2010"

    def test_dotted_filename_with_year_and_extension(self):
        """Format: 'Inception.2010.BDRip.1080p.mkv'"""
        logger = _mock_logger()
        candidates, year = clean_title(
            "Inception.2010.BDRip.1080p.mkv", logger
        )
        assert candidates == ["Inception"]
        assert year == "2010"

    def test_brackets_removed(self):
        """Brackets with content inside should be stripped."""
        logger = _mock_logger()
        candidates, year = clean_title("Matrix [Remastered] (1999)", logger)
        assert candidates == ["Matrix"]
        assert year == "1999"

    def test_empty_string(self):
        """Empty input should return empty candidates and no year."""
        logger = _mock_logger()
        candidates, year = clean_title("", logger)
        assert candidates == []
        assert year == ""

    def test_year_only_matches_19xx_20xx(self):
        """4-digit numbers outside 1900-2099 should not be treated as years."""
        logger = _mock_logger()
        candidates, year = clean_title("Ocean.1234.quality", logger)
        assert year == ""
        assert candidates == ["Ocean 1234 quality"]

    def test_slash_split_with_dotted_format(self):
        """Slash titles with dots should still split into candidates."""
        logger = _mock_logger()
        candidates, year = clean_title(
            "Люди.Икс / X-Men (2000)", logger
        )
        assert "Люди Икс" in candidates
        assert "X-Men" in candidates
        assert year == "2000"

    def test_multiple_dots_collapsed_to_single_space(self):
        """Multiple consecutive dots should become a single space."""
        logger = _mock_logger()
        candidates, year = clean_title("The..Matrix..1999", logger)
        assert candidates == ["The Matrix"]
        assert year == "1999"


class TestEnrichWithOmdbRatings:
    """Tests for _enrich_with_omdb focusing on RT/MC ratings injection."""

    def _make_details(self):
        """Create MovieDetails with initial KP and IMDB ratings."""
        return MovieDetails(
            kinopoisk_id=326,
            imdb_id="tt0111161",
            title_ru="Побег из Шоушенка",
            plot="Бухгалтер попадает в тюрьму.",
            ratings=[
                Rating(DataSource.KINOPOISK, 9.1, 800000),
                Rating(DataSource.IMDB, 9.3, 2700000),
            ]
        )

    def _make_omdb_response(self, rt="91%", mc="82"):
        """Create a standard OmdbRatings response."""
        return OmdbRatings(
            imdb_rating="9.3",
            imdb_votes="2,700,000",
            rotten_tomatoes=rt,
            metacritic=mc,
        )

    def _make_settings(self, omdb_key="test-omdb-key", show_in_plot=False):
        """Create a mock SettingsManager with OMDb settings."""
        settings = MagicMock(spec=SettingsManager)
        settings.omdb_api_key = omdb_key
        settings.show_ratings_in_plot = show_in_plot
        return settings

    @patch("scraper.OmdbClient")
    def test_rt_mc_added_to_ratings(self, MockOmdbClient):
        """OMDb returns RT='91%', MC='82' -> both added to details.ratings."""
        mock_omdb = MockOmdbClient.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = self._make_omdb_response()

        details = self._make_details()
        settings = self._make_settings(show_in_plot=True)
        logger = MagicMock()

        _enrich_with_omdb(details, settings, logger)

        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert DataSource.METACRITIC in sources

        rt_rating = next(r for r in details.ratings if r.source == DataSource.ROTTEN_TOMATOES)
        assert rt_rating.value == 91.0
        assert rt_rating.votes == 0

        mc_rating = next(r for r in details.ratings if r.source == DataSource.METACRITIC)
        assert mc_rating.value == 82.0
        assert mc_rating.votes == 0

        # Original KP and IMDB ratings should still be present
        assert DataSource.KINOPOISK in sources
        assert DataSource.IMDB in sources
        assert len(details.ratings) == 4

    @patch("scraper.OmdbClient")
    def test_ratings_added_when_plot_disabled(self, MockOmdbClient):
        """show_ratings_in_plot=False: RT/MC still added to ratings, plot unchanged."""
        mock_omdb = MockOmdbClient.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = self._make_omdb_response()

        details = self._make_details()
        original_plot = details.plot
        settings = self._make_settings(show_in_plot=False)
        logger = MagicMock()

        _enrich_with_omdb(details, settings, logger)

        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert DataSource.METACRITIC in sources
        # Plot must remain unchanged
        assert details.plot == original_plot

    @patch("scraper.OmdbClient")
    def test_no_omdb_key_no_ratings_change(self, MockOmdbClient):
        """omdb_api_key='' -> OMDb not called, ratings unchanged (only KP/IMDB)."""
        details = self._make_details()
        original_ratings = list(details.ratings)
        settings = self._make_settings(omdb_key="")
        logger = MagicMock()

        _enrich_with_omdb(details, settings, logger)

        MockOmdbClient.assert_not_called()
        assert len(details.ratings) == len(original_ratings)
        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES not in sources
        assert DataSource.METACRITIC not in sources

    @patch("scraper.OmdbClient")
    def test_omdb_error_ratings_unchanged(self, MockOmdbClient):
        """OMDb raises exception -> ratings unchanged (only KP/IMDB)."""
        mock_omdb = MockOmdbClient.return_value
        mock_omdb.fetch_ratings_raw.side_effect = Exception("Network timeout")

        details = self._make_details()
        original_ratings_count = len(details.ratings)
        settings = self._make_settings()
        logger = MagicMock()

        _enrich_with_omdb(details, settings, logger)

        assert len(details.ratings) == original_ratings_count
        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES not in sources
        assert DataSource.METACRITIC not in sources

    @patch("scraper.OmdbClient")
    def test_rt_only_no_mc(self, MockOmdbClient):
        """OMDb returns RT='91%', MC='' -> only RT added to ratings."""
        mock_omdb = MockOmdbClient.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = self._make_omdb_response(rt="91%", mc="")

        details = self._make_details()
        settings = self._make_settings()
        logger = MagicMock()

        _enrich_with_omdb(details, settings, logger)

        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert DataSource.METACRITIC not in sources
        assert len(details.ratings) == 3  # KP + IMDB + RT

    @patch("scraper.OmdbClient")
    def test_plot_text_with_ratings(self, MockOmdbClient):
        """show_ratings_in_plot=True -> plot contains rating line AND ratings has RT/MC."""
        mock_omdb = MockOmdbClient.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = self._make_omdb_response()

        details = self._make_details()
        original_plot = details.plot
        settings = self._make_settings(show_in_plot=True)
        logger = MagicMock()

        _enrich_with_omdb(details, settings, logger)

        # Ratings objects should be present
        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert DataSource.METACRITIC in sources

        # Plot should contain the original text plus rating info
        assert original_plot in details.plot
        assert details.plot != original_plot  # plot was modified
        assert "RT:" in details.plot or "MC:" in details.plot


class TestHandleFindTransliterationFallback:
    """Tests for transliteration fallback in _handle_find (AC-01..AC-04)."""

    def _make_result(self, title_ru="Брат", year=1997, kp_id=535):
        return MovieSearchResult(
            title_ru=title_ru,
            title_original=None,
            year=year,
            kinopoisk_id=kp_id,
        )

    @patch("scraper.KinopoiskClient")
    def test_transliteration_fallback_triggered_ac01(self, MockClient):
        """AC-01: Latin title 'Brat' → 0 results → transliterate → found."""
        mock_client = MockClient.return_value
        mock_client.search.side_effect = [
            [],               # Brat + year
            [],               # Brat without year
            [self._make_result()],  # Брат + year (transliteration)
        ]

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Brat", "year": "1997"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        log_calls = [str(c) for c in logger.info.call_args_list]
        assert any("transliteration fallback" in c and "Brat" in c and "Брат" in c for c in log_calls)

    @patch("scraper.KinopoiskClient")
    def test_transliteration_fallback_tihaya_zona_ac02(self, MockClient):
        """AC-02: 'Tihaya zona' → 0 results → transliterate → found."""
        mock_client = MockClient.return_value
        mock_client.search.side_effect = [
            [],
            [],
            [MovieSearchResult(title_ru="Тихая зона", year=2024, kinopoisk_id=100)],
        ]

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Tihaya zona", "year": "2024"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        log_calls = [str(c) for c in logger.info.call_args_list]
        assert any("transliteration fallback" in c for c in log_calls)

    @patch("scraper.KinopoiskClient")
    def test_no_transliteration_when_results_found_ac03(self, MockClient):
        """AC-03: 'Matrix' → found on first search → transliteration NOT triggered."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            MovieSearchResult(title_ru="Матрица", year=1999, kinopoisk_id=301)
        ]

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        log_calls = [str(c) for c in logger.info.call_args_list]
        assert not any("transliteration fallback" in c for c in log_calls)

    @patch("scraper.KinopoiskClient")
    def test_no_transliteration_for_cyrillic_title_ac04(self, MockClient):
        """AC-04: Cyrillic title 'Брат' → no transliteration attempted."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = []

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Брат"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()
        log_calls = [str(c) for c in logger.info.call_args_list]
        assert not any("transliteration fallback" in c for c in log_calls)

    @patch("scraper.KinopoiskClient")
    def test_transliteration_fallback_no_year(self, MockClient):
        """Fallback without year: no search_year → skip year loop but still transliterate."""
        mock_client = MockClient.return_value
        mock_client.search.side_effect = [
            [],                            # Brat without year (no year given)
            [self._make_result()],         # Брат without year (transliteration)
        ]

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Brat"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        log_calls = [str(c) for c in logger.info.call_args_list]
        assert any("transliteration fallback" in c for c in log_calls)

    @patch("scraper.KinopoiskClient")
    def test_transliteration_fallback_all_zero(self, MockClient):
        """Transliteration runs but still no results → nothing added."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = []

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Brat", "year": "1997"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()


class TestTransliterateToCyrillicUnit:
    """Lightweight sanity checks for transliterate_to_cyrillic imported in scraper tests."""

    def test_brat(self):
        assert transliterate_to_cyrillic("Brat") == "Брат"

    def test_cyrillic_unchanged(self):
        assert transliterate_to_cyrillic("Брат") == "Брат"


class TestDualSearch:
    """Tests for dual title search in _handle_find (BL-03)."""

    def _make_result(self, title_ru="Матрица", title_original="The Matrix",
                     year=1999, kp_id=301, rating=8.0):
        return MovieSearchResult(
            title_ru=title_ru, title_original=title_original,
            year=year, kinopoisk_id=kp_id, rating=rating,
        )

    @patch("scraper.KinopoiskClient")
    def test_dual_search_latin_query_triggers_second_search(self, MockClient):
        """Latin query -> primary result with Cyrillic title_ru -> dual search fires.

        _handle_find calls _perform_dual_search twice (after main loop and after
        no-year-fallback guard), so we need 3 search side_effects.
        """
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=301)]
        secondary = [self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=302)]
        # Call 1: primary search, Call 2: dual search #1, Call 3: dual search #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "The Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count >= 2
        second_call = mock_client.search.call_args_list[1]
        assert second_call[0][0] == "Матрица"
        assert xbmcplugin.addDirectoryItem.call_count == 2

    @patch("scraper.KinopoiskClient")
    def test_dual_search_cyrillic_query_triggers_second_search(self, MockClient):
        """Cyrillic query -> primary result with Latin title_original -> dual search fires."""
        mock_client = MockClient.return_value
        primary = [self._make_result(
            title_ru="Побег из Шоушенка", title_original="The Shawshank Redemption",
            kp_id=326,
        )]
        secondary = [self._make_result(
            title_ru="Побег из Шоушенка", title_original="The Shawshank Redemption",
            kp_id=327,
        )]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Побег из Шоушенка"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count >= 2
        second_call = mock_client.search.call_args_list[1]
        assert second_call[0][0] == "The Shawshank Redemption"

    @patch("scraper.KinopoiskClient")
    def test_dual_search_deduplicates_by_kp_id(self, MockClient):
        """Same kp_id in primary and secondary -> deduplicated to 1 result."""
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=301)]
        secondary = [self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=301)]
        # Call 1: primary, Call 2: dual #1 (same ID), Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "The Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        assert xbmcplugin.addDirectoryItem.call_count == 1

    @patch("scraper.KinopoiskClient")
    def test_dual_search_disabled_by_settings(self, MockClient):
        """enable_dual_search=False -> only one search call."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=301)
        ]

        settings = _mock_settings(enable_dual_search=False)
        logger = _mock_logger()
        params = {"title": "The Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 1

    @patch("scraper.KinopoiskClient")
    def test_dual_search_skipped_alt_matches_query(self, MockClient):
        """Latin query 'Avatar', result title_ru='Avatar' -> alt matches query -> skip."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result(title_ru="Avatar", title_original="Avatar", kp_id=301)
        ]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Avatar", "year": "2009"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 1

    @patch("scraper.KinopoiskClient")
    def test_dual_search_skipped_no_alt_title(self, MockClient):
        """Latin query, result title_ru is empty -> no alt_title -> skip."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result(title_ru="", title_original="The Matrix", kp_id=301)
        ]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "The Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 1

    @patch("scraper.KinopoiskClient")
    def test_dual_search_skipped_no_results(self, MockClient):
        """Primary search returns [] -> no dual search -> nothing added."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = []

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Nonexistent Movie"}

        _handle_find(params, 1, settings, logger)

        # One call per candidate (only 1 candidate for simple title)
        xbmcplugin.addDirectoryItem.assert_not_called()

    @patch("scraper.KinopoiskClient")
    def test_dual_search_after_no_year_fallback(self, MockClient):
        """Year fallback: search with year -> 0, without year -> results -> dual search fires."""
        mock_client = MockClient.return_value
        primary_result = self._make_result(
            title_ru="Матрица", title_original="The Matrix", kp_id=301,
        )
        secondary_result = self._make_result(
            title_ru="Матрица", title_original="The Matrix", kp_id=302,
        )
        mock_client.search.side_effect = [
            [],                    # search("The Matrix", "1999", type_filter=["FILM"]) -> empty
            [primary_result],      # search("The Matrix", None, type_filter=["FILM"]) -> found
            [secondary_result],    # dual search("Матрица", "1999", type_filter=["FILM"])
        ]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "The Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 3

    @patch("scraper.KinopoiskClient")
    def test_dual_search_default_enabled(self, MockClient):
        """Default _mock_settings() has enable_dual_search=True -> dual search runs."""
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=301)]
        secondary = [self._make_result(title_ru="Матрица", title_original="The Matrix", kp_id=302)]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings()  # defaults: enable_dual_search=True
        logger = _mock_logger()
        params = {"title": "The Matrix", "year": "1999"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count >= 2
