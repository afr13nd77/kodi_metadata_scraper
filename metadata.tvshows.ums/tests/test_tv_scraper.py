import sys
import json
import pytest
from unittest.mock import patch, MagicMock
import xbmc
import xbmcgui
import xbmcplugin
from tv_scraper import (
    run, _handle_find, _handle_getdetails, _handle_getepisodelist,
    _handle_getepisodedetails,
    _handle_nfo, _apply_tvshow_details_to_listitem, _apply_episode_to_listitem,
    _enrich_tvshow_with_omdb, _find_episode, _cache_get, _cache_put,
    _fallback_seasons_search,
)
from models import (
    MovieSearchResult, MovieDetails, TVShowDetails, Season, Episode,
    Rating, Person, Artwork, DataSource, ArtworkType, ProfessionType
)
from omdb_client import OmdbRatings
from logger import Logger
from settings_manager import SettingsManager
from kinopoisk_api import KinopoiskClient
from cache import FileCache
import tv_scraper as tv_scraper_module


@pytest.fixture(autouse=True)
def reset_kodi_mocks():
    """Reset all Kodi module-level MagicMocks between tests."""
    xbmc.reset_mock()
    xbmcgui.reset_mock()
    xbmcplugin.reset_mock()
    # Reset module-level globals in tv_scraper
    tv_scraper_module._kp_unavailable = False
    tv_scraper_module._kp_unavailable_notified = False
    tv_scraper_module._stale_cache_notified = False
    tv_scraper_module._nfo_fallback_notified = False
    tv_scraper_module._wikidata_errors = 0
    tv_scraper_module._wikidata_degraded_notified = False
    # Clear season cache between tests
    tv_scraper_module._season_cache.clear()
    tv_scraper_module._cache_access_counter = 0
    yield


def _mock_settings(api_key="test-key", omdb_key="omdb-key",
                   preferred_rating=DataSource.KINOPOISK,
                   fetch_photos=True, debug=False,
                   show_ratings_in_plot=True, use_tvmaze=False,
                   auto_select_exact_match=True,
                   enable_dual_search=False,
                   enable_award_tags=False,
                   genre_language="ru",
                   clear_cache=False,
                   enable_trailers=True,
                   use_wikidata_fallback=False):
    settings = MagicMock(spec=SettingsManager)
    settings.kinopoisk_api_key = api_key
    settings.omdb_api_key = omdb_key
    settings.preferred_rating_source = preferred_rating
    settings.fetch_actor_photos = fetch_photos
    settings.debug_logging = debug
    settings.show_ratings_in_plot = show_ratings_in_plot
    settings.use_tvmaze = use_tvmaze
    settings.auto_select_exact_match = auto_select_exact_match
    settings.enable_dual_search = enable_dual_search
    settings.enable_award_tags = enable_award_tags
    settings.genre_language = genre_language
    settings.clear_cache = clear_cache
    settings.enable_trailers = enable_trailers
    settings.use_wikidata_fallback = use_wikidata_fallback
    return settings


def _mock_logger():
    return MagicMock(spec=Logger)


def _make_seasons():
    """Create sample seasons data for tests."""
    return [
        Season(number=1, episodes=[
            Episode(season_number=1, episode_number=1, title_ru="Пилот",
                    title_en="Pilot", synopsis="First episode", release_date="2008-01-20"),
            Episode(season_number=1, episode_number=2, title_ru="Кот в мешке",
                    title_en="Cat's in the Bag...", synopsis="Second episode",
                    release_date="2008-01-27"),
        ]),
        Season(number=2, episodes=[
            Episode(season_number=2, episode_number=1, title_ru="Семь-тридцать семь",
                    title_en="Seven Thirty-Seven", synopsis="Season 2 premiere",
                    release_date="2009-03-08"),
        ]),
    ]


def _make_tvshow_details():
    """Create sample TVShowDetails for tests."""
    return TVShowDetails(
        kinopoisk_id=462682,
        imdb_id="tt0903747",
        title_ru="Во все тяжкие",
        title_original="Breaking Bad",
        tagline="All bad things must come to an end",
        year=2008,
        plot="Школьный учитель химии",
        runtime=47,
        mpaa="TV-MA",
        genres=["Драма", "Триллер"],
        countries=["США"],
        studios=["High Bridge Productions"],
        ratings=[
            Rating(DataSource.KINOPOISK, 9.1, 500000),
            Rating(DataSource.IMDB, 9.5, 2000000),
        ],
        artwork=[
            Artwork(url="https://poster.jpg", artwork_type=ArtworkType.POSTER),
            Artwork(url="https://fanart.jpg", preview_url="https://fanart_sm.jpg",
                    artwork_type=ArtworkType.FANART),
        ],
    )


# ---------------------------------------------------------------------------
# Tests for _find_episode
# ---------------------------------------------------------------------------

class TestFindEpisode:
    def test_find_existing_episode(self):
        seasons = _make_seasons()
        ep = _find_episode(seasons, 1, 2)
        assert ep is not None
        assert ep.title_ru == "Кот в мешке"
        assert ep.episode_number == 2

    def test_find_first_episode(self):
        seasons = _make_seasons()
        ep = _find_episode(seasons, 1, 1)
        assert ep is not None
        assert ep.title_en == "Pilot"

    def test_find_episode_season2(self):
        seasons = _make_seasons()
        ep = _find_episode(seasons, 2, 1)
        assert ep is not None
        assert ep.title_en == "Seven Thirty-Seven"

    def test_find_nonexistent_episode(self):
        seasons = _make_seasons()
        ep = _find_episode(seasons, 1, 99)
        assert ep is None

    def test_find_nonexistent_season(self):
        seasons = _make_seasons()
        ep = _find_episode(seasons, 99, 1)
        assert ep is None

    def test_find_in_empty_list(self):
        ep = _find_episode([], 1, 1)
        assert ep is None


# ---------------------------------------------------------------------------
# Tests for season cache
# ---------------------------------------------------------------------------

class TestSeasonCache:
    def test_cache_miss(self):
        logger = _mock_logger()
        result = _cache_get(12345, logger)
        assert result is None

    def test_cache_put_and_get(self):
        logger = _mock_logger()
        seasons = _make_seasons()
        _cache_put(12345, seasons, logger)
        result = _cache_get(12345, logger)
        assert result is not None
        assert len(result) == 2

    def test_cache_eviction(self):
        logger = _mock_logger()
        seasons = _make_seasons()
        # Fill cache beyond max size
        for i in range(tv_scraper_module._CACHE_MAX_SIZE + 3):
            _cache_put(i, seasons, logger)
        # Cache should not exceed max size
        assert len(tv_scraper_module._season_cache) <= tv_scraper_module._CACHE_MAX_SIZE

    def test_cache_lru_eviction(self):
        logger = _mock_logger()
        seasons = _make_seasons()
        # Fill cache to max
        for i in range(tv_scraper_module._CACHE_MAX_SIZE):
            _cache_put(i, seasons, logger)
        # Access first entry to make it recent
        _cache_get(0, logger)
        # Add one more to trigger eviction
        _cache_put(999, seasons, logger)
        # Entry 0 should still be present (was accessed recently)
        assert _cache_get(0, logger) is not None
        # Entry 1 should have been evicted (oldest access)
        assert _cache_get(1, logger) is None


# ---------------------------------------------------------------------------
# Tests for _handle_find
# ---------------------------------------------------------------------------

class TestHandleFind:
    @patch("tv_scraper.KinopoiskClient")
    def test_find_with_results(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            MovieSearchResult(
                title_ru="Во все тяжкие",
                title_original="Breaking Bad",
                year=2008,
                kinopoisk_id=462682,
                imdb_id="tt0903747",
                poster_url="https://poster.url/462682.jpg"
            )
        ]
        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        # Verify search was called with TV type filter
        mock_client.search.assert_called_once_with(
            "Breaking Bad", "2008",
            type_filter=["TV_SERIES", "MINI_SERIES", "TV_SHOW"]
        )
        xbmcplugin.addDirectoryItem.assert_called_once()
        call_kwargs = xbmcplugin.addDirectoryItem.call_args
        url_arg = call_kwargs[1]["url"] if "url" in call_kwargs[1] else call_kwargs[0][1]
        parsed = json.loads(url_arg)
        assert parsed["kinopoisk"] == "462682"
        assert parsed["imdb"] == "tt0903747"

    @patch("tv_scraper.KinopoiskClient")
    def test_find_fallback_without_year(self, MockClient):
        mock_client = MockClient.return_value
        # First call with year returns nothing
        # Second call without year returns results
        mock_client.search.side_effect = [
            [],
            [MovieSearchResult(title_ru="Во все тяжкие", year=2008, kinopoisk_id=462682)]
        ]
        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 2
        # Second call should be without year but with type filter
        second_call = mock_client.search.call_args_list[1]
        assert second_call[0][1] is None  # year=None
        assert second_call[1]["type_filter"] == ["TV_SERIES", "MINI_SERIES", "TV_SHOW"]
        xbmcplugin.addDirectoryItem.assert_called_once()

    def test_find_empty_title(self):
        settings = _mock_settings()
        logger = _mock_logger()

        _handle_find({"title": ""}, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()

    def test_find_no_api_key(self):
        settings = _mock_settings(api_key="")
        logger = _mock_logger()

        _handle_find({"title": "Breaking Bad"}, 1, settings, logger)

        xbmc.executebuiltin.assert_called_once()
        notification_call = xbmc.executebuiltin.call_args[0][0]
        assert "Ultimate Movie Scraper" in notification_call


# ---------------------------------------------------------------------------
# Tests for auto-select in _handle_find (AC-01..AC-06)
# ---------------------------------------------------------------------------

class TestAutoSelectExactMatch:
    """Tests for auto-select behavior in TV scraper _handle_find (AC-06)."""

    def _make_result(self, title_ru="Чернобыль", year=2019, kp_id=1127866):
        return MovieSearchResult(
            title_ru=title_ru,
            title_original="Chernobyl",
            year=year,
            kinopoisk_id=kp_id,
        )

    @patch("tv_scraper.KinopoiskClient")
    def test_auto_select_exact_match_logs(self, MockClient):
        """AC-06: TV scraper — 1 result + exact title + year + setting on → log auto-selected."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result()]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Чернобыль", "year": "2019"}

        _handle_find(params, 1, settings, logger)

        logger.info.assert_any_call(
            "_handle_find: auto-selected exact match: kp_id=1127866"
        )
        xbmcplugin.addDirectoryItem.assert_called_once()

    @patch("tv_scraper.KinopoiskClient")
    def test_auto_select_multiple_results_no_autoselect(self, MockClient):
        """Multiple results → all added, no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result("Чернобыль", 2019, 1),
            self._make_result("Чернобыль. Зона отчуждения", 2014, 2),
        ]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Чернобыль", "year": "2019"}

        _handle_find(params, 1, settings, logger)

        assert xbmcplugin.addDirectoryItem.call_count == 2
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("tv_scraper.KinopoiskClient")
    def test_auto_select_disabled_no_log(self, MockClient):
        """Setting disabled → result added normally, no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result()]

        settings = _mock_settings(auto_select_exact_match=False)
        logger = _mock_logger()
        params = {"title": "Чернобыль", "year": "2019"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("tv_scraper.KinopoiskClient")
    def test_auto_select_no_year_no_log(self, MockClient):
        """Year not provided → no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [self._make_result()]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Чернобыль"}  # no year

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)

    @patch("tv_scraper.KinopoiskClient")
    def test_auto_select_title_mismatch_no_log(self, MockClient):
        """1 result with different title → no auto-select log."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result("Чернобыль. Зона отчуждения", 2019, 999)
        ]

        settings = _mock_settings(auto_select_exact_match=True)
        logger = _mock_logger()
        params = {"title": "Чернобыль", "year": "2019"}

        _handle_find(params, 1, settings, logger)

        for call_args in logger.info.call_args_list:
            assert "auto-selected exact match" not in str(call_args)


# ---------------------------------------------------------------------------
# Tests for _handle_getdetails
# ---------------------------------------------------------------------------

class TestHandleGetdetails:
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_success(self, MockClient, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # cache miss
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Школьный учитель химии",
            ratings=[Rating(DataSource.KINOPOISK, 9.1, 500000)]
        )
        mock_client.fetch_staff_raw.return_value = [{"staffId": 1}]
        mock_client.parse_staff.return_value = (
            [Person(name_ru="Винс Гиллиган", profession=ProfessionType.DIRECTOR)],
            [],
            [Person(name_ru="Брайан Крэнстон", role="Walter White", profession=ProfessionType.ACTOR)]
        )

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][0] == 1
        assert args[0][1] is True

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_sets_episodeguide(self, MockClient, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, imdb_id="tt0903747",
            title_ru="Во все тяжкие", title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        _handle_getdetails(params, 1, settings, logger)

        # Verify setEpisodeGuide was called on the infotag
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setEpisodeGuide.assert_called_once()
        guide_json = infotag_instance.setEpisodeGuide.call_args[0][0]
        guide = json.loads(guide_json)
        assert guide["kinopoisk_id"] == 462682
        assert guide["imdb_id"] == "tt0903747"

    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_no_id(self, MockClient):
        settings = _mock_settings()
        logger = _mock_logger()

        result = _handle_getdetails({}, 1, settings, logger)

        assert result is False
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is False

    @patch("tv_scraper._try_nfo_fallback_tvshow", return_value=None)
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_api_failure(self, MockClient, MockCache, mock_nfo):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_cache.get_stale.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is False
        xbmc.executebuiltin.assert_called_once()
        notification_call = xbmc.executebuiltin.call_args[0][0]
        assert "Кинопоиск недоступен" in notification_call

    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_no_api_key(self, MockClient):
        settings = _mock_settings(api_key="")
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is False

    @patch("tv_scraper._try_nfo_fallback_tvshow", return_value=None)
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_kp_unavailable_notified_once(self, MockClient, MockCache, mock_nfo):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_cache.get_stale.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None
        mock_client.fetch_details_raw_degraded.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        _handle_getdetails(params, 1, settings, logger)
        _handle_getdetails(params, 1, settings, logger)

        # Notification should only appear once
        assert xbmc.executebuiltin.call_count == 1


# ---------------------------------------------------------------------------
# Tests for _handle_getepisodedetails
# ---------------------------------------------------------------------------

class TestHandleGetepisodedetails:
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    @patch("tv_scraper.OmdbClient")
    def test_episode_success(self, MockOmdb, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()
        mock_omdb = MockOmdb.return_value
        mock_omdb.get_episode_rating.return_value = 9.8

        settings = _mock_settings()
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747", "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is True

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_episode_not_found(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "", "season": 1, "episode": 99})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is False

    def test_episode_invalid_json(self):
        settings = _mock_settings()
        logger = _mock_logger()
        params = {"url": "not-json", "season": "1", "episode": "1"}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is False

    def test_episode_no_kp_id(self):
        settings = _mock_settings()
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 0, "imdb_id": "tt0903747", "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is False

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_episode_uses_memory_cache(self, MockKp, MockCache):
        """Second call for same kp_id uses in-memory season cache, no API/FileCache needed."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        seasons = _make_seasons()
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = seasons

        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()

        # First call fills cache
        guide1 = json.dumps({"kinopoisk_id": 462682, "imdb_id": "", "season": 1, "episode": 1})
        params1 = {"url": guide1}
        _handle_getepisodedetails(params1, 1, settings, logger)
        assert mock_kp.fetch_seasons_raw.call_count == 1

        # Second call uses in-memory cache
        guide2 = json.dumps({"kinopoisk_id": 462682, "imdb_id": "", "season": 1, "episode": 2})
        params2 = {"url": guide2}
        _handle_getepisodedetails(params2, 1, settings, logger)
        assert mock_kp.fetch_seasons_raw.call_count == 1  # Not called again

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    @patch("tv_scraper.OmdbClient")
    def test_episode_omdb_error_does_not_block(self, MockOmdb, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()
        mock_omdb = MockOmdb.return_value
        mock_omdb.get_episode_rating.side_effect = Exception("OMDb timeout")

        settings = _mock_settings()
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747", "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True  # Success despite OMDb failure

    @patch("tv_scraper.KinopoiskClient")
    def test_episode_no_api_key(self, MockKp):
        settings = _mock_settings(api_key="")
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "", "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is False

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_episode_without_omdb_key(self, MockKp, MockCache):
        """When no OMDb key, episode details still work without episode rating."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747", "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True


# ---------------------------------------------------------------------------
# Tests for legacy episodeguide format (plain kp_id)
# ---------------------------------------------------------------------------

class TestGetepisodelistLegacyFormat:
    """Tests that _handle_getepisodelist handles legacy plain kp_id URLs."""

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_plain_number_string(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"url": "60574"}

        _handle_getepisodelist(params, 1, settings, logger)

        mock_kp.fetch_seasons_raw.assert_called_once_with(60574)
        assert xbmcplugin.addDirectoryItem.call_count == 3

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_json_object_format(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings()
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747", "title_original": "Breaking Bad"})
        params = {"url": guide}

        _handle_getepisodelist(params, 1, settings, logger)

        mock_kp.fetch_seasons_raw.assert_called_once_with(462682)
        assert xbmcplugin.addDirectoryItem.call_count == 3

    def test_invalid_url_returns_early(self):
        settings = _mock_settings()
        logger = _mock_logger()
        params = {"url": "not-a-number-or-json"}

        _handle_getepisodelist(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()
        logger.error.assert_called()

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_json_number_literal(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"url": "60574"}

        _handle_getepisodelist(params, 1, settings, logger)

        logger.info.assert_any_call("_handle_getepisodelist: legacy episodeguide, kp_id=60574")


class TestGetepisodedetailsLegacyFormat:
    """Tests that _handle_getepisodedetails handles legacy plain kp_id URLs."""

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_plain_number_string(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()
        params = {"url": "462682"}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is False
        logger.info.assert_any_call("_handle_getepisodedetails: legacy episodeguide, kp_id=462682")

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_json_object_format(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "", "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True

    def test_invalid_url_returns_false(self):
        settings = _mock_settings()
        logger = _mock_logger()
        params = {"url": "not-a-number-or-json"}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is False
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is False

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_json_number_literal_parsed(self, MockKp, MockCache):
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_kp = MockKp.return_value
        mock_kp.fetch_seasons_raw.return_value = {"items": []}
        mock_kp.parse_seasons.return_value = _make_seasons()

        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()
        params = {"url": "462682"}

        _handle_getepisodedetails(params, 1, settings, logger)

        logger.info.assert_any_call("_handle_getepisodedetails: legacy episodeguide, kp_id=462682")


# ---------------------------------------------------------------------------
# Tests for _handle_nfo
# ---------------------------------------------------------------------------

class TestHandleNfo:
    def test_nfo_with_kp_id(self):
        logger = _mock_logger()
        params = {"nfo": "https://www.kinopoisk.ru/series/462682/"}

        _handle_nfo(params, 1, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        call_kwargs = xbmcplugin.addDirectoryItem.call_args
        url_arg = call_kwargs[1]["url"] if "url" in call_kwargs[1] else call_kwargs[0][1]
        parsed = json.loads(url_arg)
        assert parsed["kinopoisk"] == "462682"

    def test_nfo_with_imdb_id(self):
        logger = _mock_logger()
        params = {"nfo": '<uniqueid type="imdb">tt0903747</uniqueid>'}

        _handle_nfo(params, 1, logger)

        xbmcplugin.addDirectoryItem.assert_called_once()
        call_kwargs = xbmcplugin.addDirectoryItem.call_args
        url_arg = call_kwargs[1]["url"] if "url" in call_kwargs[1] else call_kwargs[0][1]
        parsed = json.loads(url_arg)
        assert parsed["imdb"] == "tt0903747"

    def test_nfo_empty(self):
        logger = _mock_logger()

        _handle_nfo({"nfo": ""}, 1, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()

    def test_nfo_no_ids(self):
        logger = _mock_logger()

        _handle_nfo({"nfo": "random garbage content"}, 1, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _apply_tvshow_details_to_listitem
# ---------------------------------------------------------------------------

class TestApplyTvshowDetailsToListitem:
    def test_maps_all_fields(self):
        details = _make_tvshow_details()
        details.directors = [Person(name_ru="Винс Гиллиган")]
        details.writers = [Person(name_ru="Питер Гулд")]
        details.cast = [
            Person(name_ru="Брайан Крэнстон", role="Walter White",
                   order=0, photo_url="https://photo.jpg")
        ]

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setTitle.assert_called_once_with("Во все тяжкие")
        infotag.setOriginalTitle.assert_called_once_with("Breaking Bad")
        infotag.setPlot.assert_called_once_with("Школьный учитель химии")
        infotag.setTagLine.assert_called_once_with("All bad things must come to an end")
        infotag.setYear.assert_called_once_with(2008)
        infotag.setDuration.assert_called_once_with(47 * 60)
        infotag.setMpaa.assert_called_once_with("TV-MA")
        infotag.setGenres.assert_called_once_with(["Драма", "Триллер"])
        infotag.setCountries.assert_called_once_with(["США"])
        infotag.setStudios.assert_called_once_with(["High Bridge Productions"])
        infotag.setIMDBNumber.assert_called_once_with("tt0903747")
        infotag.setDirectors.assert_called_once_with(["Винс Гиллиган"])
        infotag.setWriters.assert_called_once_with(["Питер Гулд"])
        infotag.setCast.assert_called_once()

    def test_maps_uniqueids_with_default(self):
        details = _make_tvshow_details()
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setUniqueIDs.assert_called_once_with(
            {"kinopoisk": "462682", "imdb": "tt0903747"}, "kinopoisk"
        )

    def test_maps_artwork(self):
        details = _make_tvshow_details()
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.addAvailableArtwork.assert_called_once_with("https://poster.jpg", "poster")
        listitem.setAvailableFanart.assert_called_once_with([
            {"image": "https://fanart.jpg", "preview": "https://fanart_sm.jpg"}
        ])


# ---------------------------------------------------------------------------
# Tests for _apply_episode_to_listitem
# ---------------------------------------------------------------------------

class TestApplyEpisodeToListitem:
    def test_maps_episode_fields(self):
        episode = Episode(
            season_number=1, episode_number=3,
            title_ru="Третий", title_en="Third",
            synopsis="Plot of episode 3", release_date="2008-02-10"
        )
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_episode_to_listitem(episode, 1, 3, 8.5, listitem, settings, logger)

        infotag.setTitle.assert_called_once_with("Третий")
        infotag.setSeason.assert_called_once_with(1)
        infotag.setEpisode.assert_called_once_with(3)
        infotag.setPlot.assert_called_once_with("Plot of episode 3")
        infotag.setFirstAired.assert_called_once_with("2008-02-10")
        infotag.setRating.assert_called_once_with(8.5)

    def test_fallback_to_english_title(self):
        episode = Episode(
            season_number=1, episode_number=1,
            title_ru="", title_en="Pilot",
        )
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_episode_to_listitem(episode, 1, 1, None, listitem, settings, logger)

        infotag.setTitle.assert_called_once_with("Pilot")
        infotag.setRating.assert_not_called()

    def test_fallback_to_episode_number(self):
        episode = Episode(
            season_number=1, episode_number=5,
            title_ru="", title_en="",
        )
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_episode_to_listitem(episode, 1, 5, None, listitem, settings, logger)

        infotag.setTitle.assert_called_once_with("Episode 5")

    def test_no_imdb_rating(self):
        episode = Episode(
            season_number=1, episode_number=1,
            title_ru="Пилот",
        )
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_episode_to_listitem(episode, 1, 1, None, listitem, settings, logger)

        infotag.setRating.assert_not_called()

    def test_no_synopsis_or_date(self):
        episode = Episode(
            season_number=1, episode_number=1,
            title_ru="Пилот",
            synopsis="", release_date=""
        )
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_episode_to_listitem(episode, 1, 1, None, listitem, settings, logger)

        infotag.setPlot.assert_not_called()
        infotag.setFirstAired.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for _enrich_tvshow_with_omdb
# ---------------------------------------------------------------------------

class TestEnrichTvshowWithOmdb:
    @patch("tv_scraper.OmdbClient")
    def test_enriches_plot_with_ratings(self, MockOmdb):
        from omdb_client import OmdbRatings
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.5", imdb_votes="2000000",
            rotten_tomatoes="96%", metacritic="87"
        )

        details = _make_tvshow_details()
        settings = _mock_settings()
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        assert "KP: 9.1" in details.plot
        assert "IMDb: 9.5" in details.plot
        assert "RT: 96%" in details.plot
        assert "MC: 87" in details.plot

    def test_skip_when_disabled(self):
        details = _make_tvshow_details()
        original_plot = details.plot
        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        assert details.plot == original_plot

    def test_kp_only_ratings_without_omdb_key(self):
        details = _make_tvshow_details()
        settings = _mock_settings(omdb_key="")
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        assert "KP: 9.1" in details.plot
        assert "IMDb: 9.5" in details.plot

    @patch("tv_scraper.OmdbClient")
    def test_omdb_error_does_not_block(self, MockOmdb):
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.side_effect = Exception("Connection refused")

        details = _make_tvshow_details()
        settings = _mock_settings()
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        # Should still have KP and IMDb ratings from details
        assert "KP: 9.1" in details.plot
        assert "IMDb: 9.5" in details.plot


# ---------------------------------------------------------------------------
# Tests for _enrich_tvshow_with_omdb — Rating objects in details.ratings
# ---------------------------------------------------------------------------

class TestEnrichTvshowWithOmdbRatings:
    """Tests that verify RT/MC Rating objects are added to details.ratings."""

    def _make_details(self):
        """Create TVShowDetails with initial KP+IMDb ratings."""
        return TVShowDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            plot="Учитель химии начинает варить метамфетамин.",
            ratings=[
                Rating(DataSource.KINOPOISK, 9.0, 500000),
                Rating(DataSource.IMDB, 9.5, 2000000),
            ]
        )

    @patch("tv_scraper.OmdbClient")
    def test_rt_mc_added_to_ratings(self, MockOmdb):
        """OMDb returns RT='96%', MC='87' -> details.ratings has RT and MC Rating objects."""
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.5", imdb_votes="2000000",
            rotten_tomatoes="96%", metacritic="87"
        )

        details = self._make_details()
        settings = _mock_settings(show_ratings_in_plot=True)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        sources = {r.source: r for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert sources[DataSource.ROTTEN_TOMATOES].value == 96.0
        assert sources[DataSource.ROTTEN_TOMATOES].votes == 0

        assert DataSource.METACRITIC in sources
        assert sources[DataSource.METACRITIC].value == 87.0
        assert sources[DataSource.METACRITIC].votes == 0

        # Original ratings still present
        assert DataSource.KINOPOISK in sources
        assert DataSource.IMDB in sources

    @patch("tv_scraper.OmdbClient")
    def test_ratings_added_when_plot_disabled(self, MockOmdb):
        """show_ratings_in_plot=False -> details.ratings still gets RT/MC, but plot unchanged."""
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.5", imdb_votes="2000000",
            rotten_tomatoes="96%", metacritic="87"
        )

        details = self._make_details()
        original_plot = details.plot
        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        # Plot must remain unchanged
        assert details.plot == original_plot

        # But ratings must have RT and MC
        sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert DataSource.METACRITIC in sources

    def test_no_omdb_key_no_ratings_added(self):
        """omdb_api_key='' -> details.ratings unchanged (no RT/MC added)."""
        details = self._make_details()
        original_ratings_count = len(details.ratings)
        settings = _mock_settings(omdb_key="", show_ratings_in_plot=True)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        # No new rating sources should be added
        current_sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES not in current_sources
        assert DataSource.METACRITIC not in current_sources
        assert len(details.ratings) == original_ratings_count

    @patch("tv_scraper.OmdbClient")
    def test_omdb_error_ratings_unchanged(self, MockOmdb):
        """OMDb raises exception -> details.ratings unchanged (no RT/MC added)."""
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.side_effect = Exception("Connection refused")

        details = self._make_details()
        original_ratings_count = len(details.ratings)
        settings = _mock_settings(show_ratings_in_plot=True)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        # No new rating sources should be added
        current_sources = {r.source for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES not in current_sources
        assert DataSource.METACRITIC not in current_sources
        assert len(details.ratings) == original_ratings_count

    @patch("tv_scraper.OmdbClient")
    def test_rt_only_no_mc(self, MockOmdb):
        """OMDb returns RT='96%', MC='' -> only RT in ratings, no MC."""
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.5", imdb_votes="2000000",
            rotten_tomatoes="96%", metacritic=""
        )

        details = self._make_details()
        settings = _mock_settings(show_ratings_in_plot=True)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger)

        sources = {r.source: r for r in details.ratings}
        assert DataSource.ROTTEN_TOMATOES in sources
        assert sources[DataSource.ROTTEN_TOMATOES].value == 96.0

        assert DataSource.METACRITIC not in sources


# ---------------------------------------------------------------------------
# Tests for run() entry point
# ---------------------------------------------------------------------------

class TestRunEndOfDirectory:
    @patch("tv_scraper.SettingsManager")
    @patch("tv_scraper.Logger")
    def test_find_calls_endofdirectory(self, MockLogger, MockSettings):
        MockSettings.return_value = _mock_settings()
        with patch.object(sys, "argv", ["plugin://", "1", "?action=find&title="]):
            run()
            xbmcplugin.endOfDirectory.assert_called_once_with(1)

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.SettingsManager")
    @patch("tv_scraper.Logger")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_success_no_endofdirectory(self, MockClient, MockLogger, MockSettings, MockCache):
        MockSettings.return_value = _mock_settings(show_ratings_in_plot=False)
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        url_encoded = "%7B%22kinopoisk%22%3A%22462682%22%7D"
        with patch.object(sys, "argv", ["plugin://", "1", f"?action=getdetails&url={url_encoded}"]):
            run()
            xbmcplugin.endOfDirectory.assert_not_called()

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.SettingsManager")
    @patch("tv_scraper.Logger")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_failure_calls_endofdirectory(self, MockClient, MockLogger, MockSettings, MockCache):
        MockSettings.return_value = _mock_settings()
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None
        url_encoded = "%7B%22kinopoisk%22%3A%22462682%22%7D"
        with patch.object(sys, "argv", ["plugin://", "1", f"?action=getdetails&url={url_encoded}"]):
            run()
            xbmcplugin.endOfDirectory.assert_called_once_with(1)

    @patch("tv_scraper.SettingsManager")
    @patch("tv_scraper.Logger")
    def test_nfo_calls_endofdirectory(self, MockLogger, MockSettings):
        MockSettings.return_value = _mock_settings()
        with patch.object(sys, "argv", ["plugin://", "1", "?action=NfoUrl&nfo="]):
            run()
            xbmcplugin.endOfDirectory.assert_called_once_with(1)

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.SettingsManager")
    @patch("tv_scraper.Logger")
    @patch("tv_scraper.KinopoiskClient")
    def test_getepisodedetails_success_no_endofdirectory(self, MockClient, MockLogger, MockSettings, MockCache):
        MockSettings.return_value = _mock_settings(omdb_key="")
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None
        mock_client = MockClient.return_value
        mock_client.fetch_seasons_raw.return_value = {"items": []}
        mock_client.parse_seasons.return_value = _make_seasons()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "", "season": 1, "episode": 1})
        url_encoded = guide.replace("{", "%7B").replace("}", "%7D").replace('"', "%22").replace(":", "%3A").replace(",", "%2C").replace(" ", "%20")
        with patch.object(sys, "argv", ["plugin://", "1", f"?action=getepisodedetails&url={url_encoded}"]):
            run()
            xbmcplugin.endOfDirectory.assert_not_called()

    @patch("tv_scraper.SettingsManager")
    @patch("tv_scraper.Logger")
    def test_unknown_action_calls_endofdirectory(self, MockLogger, MockSettings):
        MockSettings.return_value = _mock_settings()
        with patch.object(sys, "argv", ["plugin://", "1", "?action=unknown"]):
            run()
            xbmcplugin.endOfDirectory.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# Tests for TVMaze integration in _handle_getepisodedetails
# ---------------------------------------------------------------------------

class TestGetepisodedetailsTvmaze:

    def _setup_cached_seasons(self, synopsis=""):
        """Put seasons with a single episode into the season cache."""
        seasons = [
            Season(number=1, episodes=[
                Episode(season_number=1, episode_number=1, title_ru="Пилот",
                        title_en="Pilot", synopsis=synopsis, release_date="2008-01-20"),
            ]),
        ]
        _cache_put(462682, seasons, _mock_logger())
        return seasons

    @patch("tv_scraper.TvmazeClient")
    def test_getepisodedetails_with_tvmaze_plot(self, mock_tvmaze_cls):
        """When KP synopsis is empty and TVMaze is enabled, TVMaze plot is used."""
        mock_tvmaze = MagicMock()
        mock_tvmaze_cls.return_value = mock_tvmaze
        mock_tvmaze.get_episode_plot.return_value = "TVMaze plot text"

        self._setup_cached_seasons(synopsis="")

        settings = _mock_settings(omdb_key="", use_tvmaze=True)
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747",
                            "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True
        # Verify setPlot was called with the TVMaze plot
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setPlot.assert_called_once_with("TVMaze plot text")

    @patch("tv_scraper.TvmazeClient")
    def test_getepisodedetails_kp_synopsis_priority(self, mock_tvmaze_cls):
        """When KP synopsis exists, TVMaze should not be consulted even if enabled."""
        self._setup_cached_seasons(synopsis="KP description")

        settings = _mock_settings(omdb_key="", use_tvmaze=True)
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747",
                            "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True
        # TvmazeClient should NOT have been instantiated
        mock_tvmaze_cls.assert_not_called()
        # Verify KP synopsis was used
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setPlot.assert_called_once_with("KP description")

    @patch("tv_scraper.TvmazeClient")
    def test_getepisodedetails_tvmaze_disabled(self, mock_tvmaze_cls):
        """When use_tvmaze=False (default), TVMaze should not be consulted."""
        self._setup_cached_seasons(synopsis="")

        settings = _mock_settings(omdb_key="", use_tvmaze=False)
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747",
                            "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True
        mock_tvmaze_cls.assert_not_called()

    @patch("tv_scraper.TvmazeClient")
    def test_getepisodedetails_tvmaze_error(self, mock_tvmaze_cls):
        """When TVMaze raises an error, episode details should still succeed."""
        mock_tvmaze = MagicMock()
        mock_tvmaze_cls.return_value = mock_tvmaze
        mock_tvmaze.get_episode_plot.side_effect = RuntimeError("API down")

        self._setup_cached_seasons(synopsis="")

        settings = _mock_settings(omdb_key="", use_tvmaze=True)
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "tt0903747",
                            "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True
        # Warning should have been logged
        logger.warning.assert_called()
        # setResolvedUrl should have been called with True (success)
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][1] is True

    @patch("tv_scraper.TvmazeClient")
    def test_getepisodedetails_no_imdb_id_skips_tvmaze(self, mock_tvmaze_cls):
        """When episode guide has empty imdb_id, TVMaze should not be consulted."""
        self._setup_cached_seasons(synopsis="")

        settings = _mock_settings(omdb_key="", use_tvmaze=True)
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 462682, "imdb_id": "",
                            "season": 1, "episode": 1})
        params = {"url": guide}

        result = _handle_getepisodedetails(params, 1, settings, logger)

        assert result is True
        mock_tvmaze_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for dual title search in _handle_find (BL-03)
# ---------------------------------------------------------------------------

class TestDualSearch:
    """Tests for dual title search in TV scraper _handle_find (BL-03)."""

    def _make_result(self, title_ru="Во все тяжкие", title_original="Breaking Bad",
                     year=2008, kp_id=462682, rating=9.0):
        return MovieSearchResult(
            title_ru=title_ru, title_original=title_original,
            year=year, kinopoisk_id=kp_id, rating=rating,
        )

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_latin_query_triggers_second_search(self, MockClient):
        """Latin query -> primary result with Cyrillic title_ru -> dual search fires.

        _handle_find calls _perform_dual_search twice (after main loop and after
        no-year-fallback guard), so we need 3 search side_effects.
        """
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682)]
        secondary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462683)]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count >= 2
        second_call = mock_client.search.call_args_list[1]
        assert second_call[0][0] == "Во все тяжкие"
        assert xbmcplugin.addDirectoryItem.call_count == 2

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_cyrillic_query_triggers_second_search(self, MockClient):
        """Cyrillic query -> primary result with Latin title_original -> dual search fires."""
        mock_client = MockClient.return_value
        primary = [self._make_result(
            title_ru="Чернобыль", title_original="Chernobyl", kp_id=1127866,
        )]
        secondary = [self._make_result(
            title_ru="Чернобыль", title_original="Chernobyl", kp_id=1127867,
        )]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Чернобыль"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count >= 2
        second_call = mock_client.search.call_args_list[1]
        assert second_call[0][0] == "Chernobyl"

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_deduplicates_by_kp_id(self, MockClient):
        """Same kp_id in primary and secondary -> deduplicated to 1 result."""
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682)]
        secondary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682)]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert xbmcplugin.addDirectoryItem.call_count == 1

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_disabled_by_settings(self, MockClient):
        """enable_dual_search=False (TV default) -> only one search call."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682)
        ]

        settings = _mock_settings(enable_dual_search=False)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 1

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_skipped_alt_matches_query(self, MockClient):
        """Latin query 'Avatar', result title_ru='Avatar' -> alt matches query -> skip."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result(title_ru="Avatar", title_original="Avatar", kp_id=100)
        ]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Avatar", "year": "2009"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 1

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_skipped_no_alt_title(self, MockClient):
        """Latin query, result title_ru is empty -> no alt_title -> skip."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = [
            self._make_result(title_ru="", title_original="Breaking Bad", kp_id=462682)
        ]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 1

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_skipped_no_results(self, MockClient):
        """Primary search returns [] -> no dual search -> nothing added."""
        mock_client = MockClient.return_value
        mock_client.search.return_value = []

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Nonexistent Show"}

        _handle_find(params, 1, settings, logger)

        xbmcplugin.addDirectoryItem.assert_not_called()

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_after_no_year_fallback(self, MockClient):
        """Year fallback: search with year -> 0, without year -> results -> dual search fires."""
        mock_client = MockClient.return_value
        primary_result = self._make_result(
            title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682,
        )
        secondary_result = self._make_result(
            title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462683,
        )
        mock_client.search.side_effect = [
            [],                      # search("Breaking Bad", "2008", type_filter=tv) -> empty
            [primary_result],        # search("Breaking Bad", None, type_filter=tv) -> found
            [secondary_result],      # dual search("Во все тяжкие", "2008", type_filter=tv)
        ]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count == 3

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_enabled_by_settings(self, MockClient):
        """With enable_dual_search=True (non-default for TV), dual search runs."""
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682)]
        secondary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462683)]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        assert mock_client.search.call_count >= 2

    @patch("tv_scraper.KinopoiskClient")
    def test_dual_search_preserves_tv_type_filter(self, MockClient):
        """Dual search must use TV type_filter, not FILM."""
        mock_client = MockClient.return_value
        primary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462682)]
        secondary = [self._make_result(title_ru="Во все тяжкие", title_original="Breaking Bad", kp_id=462683)]
        # Call 1: primary, Call 2: dual #1, Call 3: dual #2
        mock_client.search.side_effect = [primary, secondary, []]

        settings = _mock_settings(enable_dual_search=True)
        logger = _mock_logger()
        params = {"title": "Breaking Bad", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        expected_tv_filter = ["TV_SERIES", "MINI_SERIES", "TV_SHOW"]
        # All search calls must use TV type filter
        for call_args in mock_client.search.call_args_list:
            assert call_args[1]["type_filter"] == expected_tv_filter


# ---------------------------------------------------------------------------
# BL-10: Award tags in _enrich_tvshow_with_omdb and _apply_tvshow_details_to_listitem
# ---------------------------------------------------------------------------

class TestAwardTags:
    """Tests for BL-10: Award tags feature in TV scraper."""

    def _make_details_for_awards(self):
        """Create TVShowDetails with imdb_id for OMDb lookup."""
        return TVShowDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            plot="Учитель химии.",
            ratings=[
                Rating(DataSource.KINOPOISK, 9.0, 500000),
                Rating(DataSource.IMDB, 9.5, 2000000),
            ],
        )

    @patch("tv_scraper.OmdbClient")
    def test_award_tags_enabled_with_awards(self, MockOmdb):
        """enable_award_tags=True + awards='Won 4 Oscars.' -> details.tags contains award tag."""
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.5", imdb_votes="2000000",
            rotten_tomatoes="96%", metacritic="87",
            awards="Won 4 Oscars."
        )

        details = self._make_details_for_awards()
        settings = _mock_settings(enable_award_tags=True)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger, cache=None)

        assert "Оскар" in details.tags

    @patch("tv_scraper.OmdbClient")
    def test_award_tags_disabled(self, MockOmdb):
        """enable_award_tags=False + awards present -> details.tags stays empty."""
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.5", imdb_votes="2000000",
            rotten_tomatoes="96%", metacritic="87",
            awards="Won 4 Oscars."
        )

        details = self._make_details_for_awards()
        settings = _mock_settings(enable_award_tags=False)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger, cache=None)

        assert details.tags == []

    def test_award_tags_no_omdb(self):
        """No OMDb key -> no OMDb ratings -> details.tags stays empty."""
        details = self._make_details_for_awards()
        settings = _mock_settings(omdb_key="", enable_award_tags=True)
        logger = _mock_logger()

        _enrich_tvshow_with_omdb(details, settings, logger, cache=None)

        assert details.tags == []

    def test_setTags_called(self):
        """_apply_tvshow_details_to_listitem calls setTags when details.tags is non-empty."""
        details = _make_tvshow_details()
        details.tags = ["Оскар"]

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setTags.assert_called_once_with(["Оскар"])

    def test_setTags_not_called_when_empty(self):
        """_apply_tvshow_details_to_listitem does NOT call setTags when details.tags is empty."""
        details = _make_tvshow_details()
        details.tags = []

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setTags.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for fallback chain in _handle_getdetails and _handle_find
# ---------------------------------------------------------------------------

class TestFallbackChain:
    """Tests for the fallback chain: fresh cache -> API -> stale cache -> NFO -> hard fail."""

    @patch("tv_scraper._try_nfo_fallback_tvshow", return_value=None)
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_stale_cache_fallback(self, MockClient, MockCache, mock_nfo):
        """Stale cache fallback: cache miss, API fail, stale cache returns valid raw data.
        Assert: parse_details called with stale data, setResolvedUrl(handle, True, ...),
        notification about stale cache shown."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # fresh cache miss
        mock_cache.get_stale.return_value = {"id": 462682, "stale": True}  # stale hit
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None  # API fail
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Школьный учитель химии",
            ratings=[Rating(DataSource.KINOPOISK, 9.1, 500000)],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        # parse_details should have been called with stale data
        mock_client.parse_details.assert_called_once_with(
            {"id": 462682, "stale": True}, genre_language="ru"
        )
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][0] == 1
        assert args[0][1] is True
        # Notification about stale cache
        xbmc.executebuiltin.assert_called()
        notification_call = xbmc.executebuiltin.call_args[0][0]
        assert "кэша" in notification_call.lower() or "кэш" in notification_call.lower()
        # NFO fallback should NOT have been attempted
        mock_nfo.assert_not_called()

    @patch("tv_scraper._try_nfo_fallback_tvshow")
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_nfo_fallback(self, MockClient, MockCache, mock_nfo):
        """NFO fallback: cache miss, API fail, stale cache miss, NFO returns TVShowDetails.
        Assert: setResolvedUrl(handle, True, ...), notification about NFO shown.
        Verify the TVShowDetails from NFO is used directly (no MovieDetails->TVShowDetails mapping)."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # fresh cache miss
        mock_cache.get_stale.return_value = None  # stale cache miss
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None  # API fail

        # NFO returns a TVShowDetails directly
        nfo_details = TVShowDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие (NFO)",
            title_original="Breaking Bad",
            year=2008,
            plot="From NFO file",
            ratings=[Rating(DataSource.KINOPOISK, 9.0, 400000)],
            directors=[Person(name_ru="Винс Гиллиган", profession=ProfessionType.DIRECTOR)],
        )
        mock_nfo.return_value = nfo_details

        # parse_staff should not be called for NFO path since directors come from NFO
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][0] == 1
        assert args[0][1] is True
        # Notification about NFO
        xbmc.executebuiltin.assert_called()
        notification_call = xbmc.executebuiltin.call_args[0][0]
        assert "NFO" in notification_call
        # parse_details should NOT have been called (NFO returns TVShowDetails directly)
        mock_client.parse_details.assert_not_called()

    @patch("tv_scraper._try_nfo_fallback_tvshow", return_value=None)
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_hard_fail(self, MockClient, MockCache, mock_nfo):
        """Hard fail: all fallbacks return None.
        Assert: setResolvedUrl(handle, False, ...), notification about unavailability shown."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # fresh cache miss
        mock_cache.get_stale.return_value = None  # stale cache miss
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None  # API fail
        mock_client.fetch_details_raw_degraded.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is False
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][0] == 1
        assert args[0][1] is False
        # Notification about KP being unavailable
        xbmc.executebuiltin.assert_called()
        notification_call = xbmc.executebuiltin.call_args[0][0]
        assert "недоступен" in notification_call

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_api_recovery(self, MockClient, MockCache):
        """API recovery: _kp_unavailable=True, cache miss, fetch_details_raw_degraded returns valid data.
        Assert: _kp_unavailable reset to False."""
        # Pre-set _kp_unavailable to True
        tv_scraper_module._kp_unavailable = True

        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # cache miss
        mock_client = MockClient.return_value
        # fetch_details_raw_degraded is used when _kp_unavailable=True
        mock_client.fetch_details_raw_degraded.return_value = {"id": 462682, "type": "TV_SERIES"}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Школьный учитель химии",
            ratings=[Rating(DataSource.KINOPOISK, 9.1, 500000)],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        # _kp_unavailable should be reset to False after successful degraded fetch
        assert tv_scraper_module._kp_unavailable is False
        # fetch_details_raw_degraded (not fetch_details_raw) should have been called
        mock_client.fetch_details_raw_degraded.assert_called_once_with(462682)
        mock_client.fetch_details_raw.assert_not_called()

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_getdetails_fresh_cache_unchanged(self, MockClient, MockCache):
        """Fresh cache hit: cache returns valid data, no API call made.
        AC-10 backward compatibility: setResolvedUrl(handle, True, ...), no notifications."""
        cached_data = {"id": 462682, "type": "TV_SERIES"}
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = cached_data  # fresh cache HIT
        mock_client = MockClient.return_value
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Школьный учитель химии",
            ratings=[Rating(DataSource.KINOPOISK, 9.1, 500000)],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        xbmcplugin.setResolvedUrl.assert_called_once()
        args = xbmcplugin.setResolvedUrl.call_args
        assert args[0][0] == 1
        assert args[0][1] is True
        # No API call should have been made
        mock_client.fetch_details_raw.assert_not_called()
        mock_client.fetch_details_raw_degraded.assert_not_called()
        # No notifications should have been shown (no fallback)
        xbmc.executebuiltin.assert_not_called()

    @patch("tv_scraper.KinopoiskClient")
    def test_find_notification_on_api_fail(self, MockClient):
        """Find notification: _kp_unavailable=True, search returns [].
        Assert: notification about search being impossible is shown."""
        # Pre-set _kp_unavailable to True
        tv_scraper_module._kp_unavailable = True

        mock_client = MockClient.return_value
        mock_client.search.return_value = []

        settings = _mock_settings()
        logger = _mock_logger()
        params = {"title": "Во все тяжкие", "year": "2008"}

        _handle_find(params, 1, settings, logger)

        xbmc.executebuiltin.assert_called()
        notification_call = xbmc.executebuiltin.call_args[0][0]
        assert "поиск невозможен" in notification_call
        """_apply_tvshow_details_to_listitem does NOT call setTags when details.tags is empty."""
        details = _make_tvshow_details()
        details.tags = []

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setTags.assert_not_called()


# ---------------------------------------------------------------------------
# BL-11: Genre language passed through correctly
# ---------------------------------------------------------------------------

class TestGenreLanguage:
    """Tests for BL-11: genre_language is forwarded to parse_details."""

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_genre_language_passed_to_parse_details(self, MockClient, MockCache):
        """_handle_getdetails passes settings.genre_language to parse_details."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # cache miss -> fetch from API
        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Описание",
            ratings=[],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(genre_language="en", show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        _handle_getdetails(params, 1, settings, logger)

        mock_client.parse_details.assert_called_once_with(
            {"id": 462682}, genre_language="en"
        )

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_genre_language_passed_from_cache(self, MockClient, MockCache):
        """_handle_getdetails passes genre_language to parse_details even when using cached raw data."""
        cached_data = {"id": 462682, "cached": True}
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = cached_data  # cache hit
        mock_client = MockClient.return_value
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Описание",
            ratings=[],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(genre_language="ru", show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        _handle_getdetails(params, 1, settings, logger)

        mock_client.parse_details.assert_called_once_with(
            cached_data, genre_language="ru"
        )


# ---------------------------------------------------------------------------
# Tests for _fallback_seasons_search
# ---------------------------------------------------------------------------

class TestFallbackSeasonsSearch:

    def _make_fallback_seasons(self):
        return [
            Season(number=1, episodes=[
                Episode(season_number=1, episode_number=1, title_ru="Пилот",
                        title_en="Pilot", synopsis="First", release_date="2013-09-12"),
            ]),
        ]

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_title_search_success(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 60574, "title_original": "Peaky Blinders", "imdb_id": ""}
        kp_client = MagicMock(spec=KinopoiskClient)
        kp_client.search.return_value = [
            MovieSearchResult(title_ru="Острые козырьки", kinopoisk_id=777000)
        ]
        fallback_seasons = self._make_fallback_seasons()
        kp_client.fetch_seasons_raw.return_value = {"items": []}
        kp_client.parse_seasons.return_value = fallback_seasons

        settings = _mock_settings()
        logger = _mock_logger()
        cache = MagicMock(spec=FileCache)

        new_kp_id, seasons = _fallback_seasons_search(
            60574, guide, kp_client, settings, logger, cache
        )

        assert new_kp_id == 777000
        assert len(seasons) == 1
        kp_client.search.assert_called_once_with(
            "Peaky Blinders", None, type_filter=["TV_SERIES", "MINI_SERIES", "TV_SHOW"]
        )
        kp_client.fetch_seasons_raw.assert_called_once_with(777000)
        cache.put.assert_called_once_with("kp_seasons_777000", {"items": []})
        logger.info.assert_any_call(
            "_fallback_seasons_search: strategy=title_search, "
            "title='Peaky Blinders', found kp_id=777000"
        )

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_imdb_lookup_success(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 60574, "title_original": "", "imdb_id": "tt2442560"}
        kp_client = MagicMock(spec=KinopoiskClient)
        mock_search_imdb.return_value = 888000
        fallback_seasons = self._make_fallback_seasons()
        kp_client.fetch_seasons_raw.return_value = {"items": []}
        kp_client.parse_seasons.return_value = fallback_seasons

        settings = _mock_settings()
        logger = _mock_logger()
        cache = MagicMock(spec=FileCache)

        new_kp_id, seasons = _fallback_seasons_search(
            60574, guide, kp_client, settings, logger, cache
        )

        assert new_kp_id == 888000
        assert len(seasons) == 1
        mock_search_imdb.assert_called_once_with("tt2442560", settings, logger)
        kp_client.fetch_seasons_raw.assert_called_once_with(888000)
        cache.put.assert_called_once_with("kp_seasons_888000", {"items": []})
        logger.info.assert_any_call(
            "_fallback_seasons_search: strategy=imdb_lookup, "
            "imdb_id='tt2442560', found kp_id=888000"
        )

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_legacy_not_tv_series(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 60574}
        kp_client = MagicMock(spec=KinopoiskClient)
        kp_client.fetch_details_raw.return_value = {"type": "FILM", "id": 60574}

        settings = _mock_settings()
        logger = _mock_logger()

        new_kp_id, seasons = _fallback_seasons_search(
            60574, guide, kp_client, settings, logger, None
        )

        assert new_kp_id == 60574
        assert seasons == []
        kp_client.fetch_details_raw.assert_called_once_with(60574)
        logger.warning.assert_any_call(
            "_fallback_seasons_search: kp_id=60574 is type='FILM', "
            "not a TV series. Rescan required."
        )
        mock_xbmc.executebuiltin.assert_called_once()
        notification_arg = mock_xbmc.executebuiltin.call_args[0][0]
        assert "60574" in notification_arg
        assert "не сериал" in notification_arg

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_legacy_tv_series_no_seasons(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 99999}
        kp_client = MagicMock(spec=KinopoiskClient)
        kp_client.fetch_details_raw.return_value = {"type": "TV_SERIES", "id": 99999}

        settings = _mock_settings()
        logger = _mock_logger()

        new_kp_id, seasons = _fallback_seasons_search(
            99999, guide, kp_client, settings, logger, None
        )

        assert new_kp_id == 99999
        assert seasons == []
        logger.info.assert_any_call(
            "_fallback_seasons_search: kp_id=99999 is type='TV_SERIES' "
            "but API has no season data"
        )
        mock_xbmc.executebuiltin.assert_not_called()

    def test_fallback_no_api_key(self):
        settings = _mock_settings(api_key="")
        logger = _mock_logger()
        guide = json.dumps({"kinopoisk_id": 60574})
        params = {"url": guide}

        _cache_put(60574, [], logger)

        _handle_getepisodelist(params, 1, settings, logger)

        assert xbmcplugin.addDirectoryItem.call_count == 0

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_title_search_same_kp_id(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 60574, "title_original": "Some Title", "imdb_id": ""}
        kp_client = MagicMock(spec=KinopoiskClient)
        kp_client.search.return_value = [
            MovieSearchResult(title_ru="Some Title", kinopoisk_id=60574)
        ]
        kp_client.fetch_details_raw.return_value = {"type": "TV_SERIES", "id": 60574}

        settings = _mock_settings()
        logger = _mock_logger()

        new_kp_id, seasons = _fallback_seasons_search(
            60574, guide, kp_client, settings, logger, None
        )

        assert new_kp_id == 60574
        assert seasons == []
        kp_client.fetch_seasons_raw.assert_not_called()

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_legacy_type_cached(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 123}
        kp_client = MagicMock(spec=KinopoiskClient)
        cache = MagicMock(spec=FileCache)
        cache.get.return_value = {"type": "FILM"}

        settings = _mock_settings()
        logger = _mock_logger()

        new_kp_id, seasons = _fallback_seasons_search(
            123, guide, kp_client, settings, logger, cache
        )

        assert new_kp_id == 123
        assert seasons == []
        cache.get.assert_called_once_with("kp_type_123")
        kp_client.fetch_details_raw.assert_not_called()
        mock_xbmc.executebuiltin.assert_not_called()

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_legacy_caches_type(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 123}
        kp_client = MagicMock(spec=KinopoiskClient)
        kp_client.fetch_details_raw.return_value = {"type": "FILM", "id": 123}
        cache = MagicMock(spec=FileCache)
        cache.get.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()

        new_kp_id, seasons = _fallback_seasons_search(
            123, guide, kp_client, settings, logger, cache
        )

        assert new_kp_id == 123
        assert seasons == []
        kp_client.fetch_details_raw.assert_called_once_with(123)
        cache.put.assert_any_call("kp_type_123", {"type": "FILM"})

    @patch("tv_scraper.xbmc")
    @patch("tv_scraper.search_kp_by_imdb")
    def test_fallback_legacy_deletes_stale_seasons(self, mock_search_imdb, mock_xbmc):
        guide = {"kinopoisk_id": 123}
        kp_client = MagicMock(spec=KinopoiskClient)
        kp_client.fetch_details_raw.return_value = {"type": "FILM", "id": 123}
        cache = MagicMock(spec=FileCache)
        cache.get.return_value = None

        settings = _mock_settings()
        logger = _mock_logger()

        _fallback_seasons_search(123, guide, kp_client, settings, logger, cache)

        cache.delete.assert_called_once_with("kp_seasons_123")


# ---------------------------------------------------------------------------
# BL-18: Mini-series detection in _handle_getdetails
# ---------------------------------------------------------------------------

class TestMiniSeriesDetection:
    """Tests for BL-18: Mini-series detection (AC-18..AC-21)."""

    def _setup_mocks(self, MockClient, MockCache, content_type="MINI_SERIES"):
        """Set up standard KP client and cache mocks for getdetails."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None  # cache miss

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {
            "id": 462682,
            "type": content_type,
        }
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Чернобыль",
            title_original="Chernobyl",
            year=2019,
            plot="Сериал о катастрофе на ЧАЭС.",
            ratings=[Rating(DataSource.KINOPOISK, 8.9, 300000)],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])
        return mock_client, mock_cache

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_mini_series_tag_ru(self, MockClient, MockCache):
        """AC-18: type=MINI_SERIES + genre_language=ru -> is_miniseries=True, tag 'Мини-сериал'."""
        self._setup_mocks(MockClient, MockCache, content_type="MINI_SERIES")

        settings = _mock_settings(genre_language="ru", show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        # setTags must have been called with a list containing the mini-series tag
        infotag_instance.setTags.assert_called_once()
        tags_arg = infotag_instance.setTags.call_args[0][0]
        assert "Мини-сериал" in tags_arg

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_mini_series_tag_en(self, MockClient, MockCache):
        """AC-19: type=MINI_SERIES + genre_language=en -> is_miniseries=True, tag 'Mini-Series'."""
        self._setup_mocks(MockClient, MockCache, content_type="MINI_SERIES")

        settings = _mock_settings(genre_language="en", show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setTags.assert_called_once()
        tags_arg = infotag_instance.setTags.call_args[0][0]
        assert "Mini-Series" in tags_arg

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_tv_series_not_mini(self, MockClient, MockCache):
        """AC-20: type=TV_SERIES -> is_miniseries=False, no mini-series tag."""
        self._setup_mocks(MockClient, MockCache, content_type="TV_SERIES")

        settings = _mock_settings(genre_language="ru", show_ratings_in_plot=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        # setTags should NOT be called (no tags at all)
        infotag_instance.setTags.assert_not_called()

    @patch("tv_scraper.OmdbClient")
    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_tags_preserved_with_awards(self, MockClient, MockCache, MockOmdb):
        """AC-21: type=MINI_SERIES + OMDb awards -> both mini-series and award tags present."""
        self._setup_mocks(MockClient, MockCache, content_type="MINI_SERIES")

        # Set up OMDb to return awards
        mock_omdb = MockOmdb.return_value
        mock_omdb.fetch_ratings_raw.return_value = {"Response": "True"}
        mock_omdb.parse_ratings.return_value = OmdbRatings(
            imdb_rating="9.4", imdb_votes="800000",
            rotten_tomatoes="96%", metacritic="83",
            awards="Won 2 Primetime Emmy Awards."
        )

        settings = _mock_settings(
            genre_language="ru",
            show_ratings_in_plot=False,
            enable_award_tags=True,
        )
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setTags.assert_called_once()
        tags_arg = infotag_instance.setTags.call_args[0][0]
        # Mini-series tag must be present
        assert "Мини-сериал" in tags_arg
        # Award tags must also be present (extend, not overwrite)
        assert len(tags_arg) >= 2


# ---------------------------------------------------------------------------
# BL-09: YouTube trailer integration in _handle_getdetails
# ---------------------------------------------------------------------------

class TestTrailerIntegration:
    """BL-09: Tests for YouTube trailer integration in TV scraper."""

    TRAILER_URL = "plugin://plugin.video.youtube/?action=play_video&videoid=dQw4w9WgXcQ"

    def _setup_mocks(self, MockClient, MockCache, videos_raw=None, trailer_url=""):
        """Set up standard KP client and cache mocks for getdetails with trailer support."""
        mock_cache = MockCache.return_value
        mock_cache.get.side_effect = lambda key: (
            None  # cache miss for details, staff, videos
        )
        mock_cache.get_stale.return_value = None

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {
            "id": 462682,
            "type": "TV_SERIES",
        }
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            plot="Школьный учитель химии",
            ratings=[Rating(DataSource.KINOPOISK, 9.1, 500000)],
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        mock_client.fetch_videos_raw.return_value = videos_raw
        mock_client.parse_trailer_url.return_value = trailer_url

        return mock_client, mock_cache

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_trailer_from_api(self, MockClient, MockCache):
        """AC-04: API returns YouTube trailer -> setTrailer called."""
        videos_raw = {"total": 1, "items": [{"url": "https://youtube.com/xxx", "site": "YOUTUBE"}]}
        mock_client, mock_cache = self._setup_mocks(
            MockClient, MockCache,
            videos_raw=videos_raw,
            trailer_url=self.TRAILER_URL,
        )

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=True)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        # fetch_videos_raw should have been called
        mock_client.fetch_videos_raw.assert_called_once_with(462682)
        # parse_trailer_url should have been called with the raw data
        mock_client.parse_trailer_url.assert_called_once_with(videos_raw)
        # setTrailer should have been called on the infotag
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setTrailer.assert_called_once_with(self.TRAILER_URL)

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_trailer_disabled(self, MockClient, MockCache):
        """AC-05: enable_trailers=False -> no API call for videos."""
        mock_client, mock_cache = self._setup_mocks(MockClient, MockCache)

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        # fetch_videos_raw should NOT have been called
        mock_client.fetch_videos_raw.assert_not_called()
        # setTrailer should NOT have been called (no trailer_url set)
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setTrailer.assert_not_called()

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_trailer_from_cache(self, MockClient, MockCache):
        """AC-09: cache hit for videos -> no API call, trailer set."""
        cached_videos = {"total": 1, "items": [{"url": "https://youtube.com/xxx", "site": "YOUTUBE"}]}
        mock_client, mock_cache = self._setup_mocks(
            MockClient, MockCache,
            trailer_url=self.TRAILER_URL,
        )
        # Override cache.get to return cached videos for the videos key
        def cache_get_side_effect(key):
            if key == "kp_videos_462682":
                return cached_videos
            return None
        mock_cache.get.side_effect = cache_get_side_effect

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=True)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        # fetch_videos_raw should NOT have been called (cache hit)
        mock_client.fetch_videos_raw.assert_not_called()
        # parse_trailer_url should have been called with cached data
        mock_client.parse_trailer_url.assert_called_once_with(cached_videos)
        # setTrailer should have been called
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setTrailer.assert_called_once_with(self.TRAILER_URL)

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_trailer_api_error_stale(self, MockClient, MockCache):
        """AC-10: API error for videos -> stale cache fallback used."""
        stale_videos = {"total": 1, "items": [{"url": "https://youtube.com/old", "site": "YOUTUBE"}]}
        mock_client, mock_cache = self._setup_mocks(
            MockClient, MockCache,
            videos_raw=None,  # API returns None (error)
            trailer_url=self.TRAILER_URL,
        )
        # Override cache.get_stale to return stale videos for the videos key
        def cache_get_stale_side_effect(key):
            if key == "kp_videos_462682":
                return stale_videos
            return None
        mock_cache.get_stale.side_effect = cache_get_stale_side_effect

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=True)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        # fetch_videos_raw returned None, so stale cache should be consulted
        mock_client.fetch_videos_raw.assert_called_once_with(462682)
        # parse_trailer_url should have been called with stale data
        mock_client.parse_trailer_url.assert_called_once_with(stale_videos)
        # setTrailer should have been called
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setTrailer.assert_called_once_with(self.TRAILER_URL)


# ---------------------------------------------------------------------------
# Tests for _resolve_imdb_via_wikidata in TV scraper
# ---------------------------------------------------------------------------

class TestWikidataFallbackTv:
    """Tests for _resolve_imdb_via_wikidata integration in TV scraper."""

    @patch("wikidata_client.WikidataClient")
    def test_wikidata_fallback_resolves_imdb_tv(self, MockWikidata):
        """Wikidata fallback resolves IMDB ID when cache miss and API returns a value."""
        mock_client = MagicMock()
        mock_client.get_imdb_id_by_kp_id.return_value = "tt0944947"
        MockWikidata.return_value = mock_client

        tvshow = TVShowDetails(kinopoisk_id=77269, imdb_id="")
        cache = MagicMock()
        cache.get.return_value = None
        cache.get_stale.return_value = None
        settings = MagicMock()
        settings.use_wikidata_fallback = True
        logger = MagicMock()

        tv_scraper_module._wikidata_errors = 0
        tv_scraper_module._wikidata_degraded_notified = False
        tv_scraper_module._resolve_imdb_via_wikidata(tvshow, 77269, cache, settings, logger)

        assert tvshow.imdb_id == "tt0944947"

    @patch("wikidata_client.WikidataClient")
    def test_wikidata_fallback_disabled_tv(self, MockWikidata):
        """Wikidata fallback skipped when use_wikidata_fallback=False."""
        tvshow = TVShowDetails(kinopoisk_id=77269, imdb_id="")
        cache = MagicMock()
        settings = MagicMock()
        settings.use_wikidata_fallback = False
        logger = MagicMock()

        tv_scraper_module._wikidata_errors = 0
        tv_scraper_module._wikidata_degraded_notified = False
        tv_scraper_module._resolve_imdb_via_wikidata(tvshow, 77269, cache, settings, logger)

        MockWikidata.assert_not_called()
        assert tvshow.imdb_id == ""


# ---------------------------------------------------------------------------
# BL-60: Premiere date from distributions in _handle_getdetails
# ---------------------------------------------------------------------------

class TestBL60PremiereDate:
    """Tests for BL-60: fetching premiere date via distributions API."""

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_distributions_fetched_and_premiere_set(self, MockClient, MockCache):
        """_handle_getdetails fetches distributions and sets premiere_date on TVShowDetails."""
        mock_cache = MockCache.return_value
        distributions_data = {"items": [{"type": {"value": "WORLD_PREMIER"}, "date": "2008-01-20"}]}

        def cache_get_side_effect(key):
            if key == "kp_distributions_462682":
                return None
            return None
        mock_cache.get.side_effect = cache_get_side_effect

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, imdb_id="tt0903747",
            title_ru="Во все тяжкие", title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])
        mock_client.fetch_distributions_raw.return_value = distributions_data
        mock_client.parse_premiere_date.return_value = "2008-01-20"

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        mock_client.fetch_distributions_raw.assert_called_once_with(462682)
        mock_cache.put.assert_any_call("kp_distributions_462682", distributions_data)
        mock_client.parse_premiere_date.assert_called_once_with(distributions_data)
        # setPremiered should be called via _apply_tvshow_details_to_listitem
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setPremiered.assert_called_once_with("2008-01-20")

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_distributions_from_cache(self, MockClient, MockCache):
        """_handle_getdetails uses cached distributions data."""
        mock_cache = MockCache.return_value
        cached_dist = {"items": [{"type": {"value": "WORLD_PREMIER"}, "date": "2008-01-20"}]}

        def cache_get_side_effect(key):
            if key == "kp_distributions_462682":
                return cached_dist
            return None
        mock_cache.get.side_effect = cache_get_side_effect

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, imdb_id="tt0903747",
            title_ru="Во все тяжкие", title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])
        mock_client.parse_premiere_date.return_value = "2008-01-20"

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        mock_client.fetch_distributions_raw.assert_not_called()
        mock_client.parse_premiere_date.assert_called_once_with(cached_dist)

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_distributions_error_graceful_degradation(self, MockClient, MockCache):
        """_handle_getdetails handles distributions error without breaking the flow."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, imdb_id="tt0903747",
            title_ru="Во все тяжкие", title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])
        mock_client.fetch_distributions_raw.side_effect = Exception("API timeout")

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        logger.warning.assert_any_call(
            "_handle_getdetails: distributions error for kp_id=462682: API timeout"
        )

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_distributions_empty_premiere_no_setPremiered(self, MockClient, MockCache):
        """When premiere_date is empty, setPremiered is not called."""
        mock_cache = MockCache.return_value
        mock_cache.get.return_value = None

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = {"id": 462682}
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, imdb_id="tt0903747",
            title_ru="Во все тяжкие", title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])
        mock_client.fetch_distributions_raw.return_value = {"items": []}
        mock_client.parse_premiere_date.return_value = ""

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        listitem_instance = xbmcgui.ListItem.return_value
        infotag_instance = listitem_instance.getVideoInfoTag.return_value
        infotag_instance.setPremiered.assert_not_called()

    @patch("tv_scraper.FileCache")
    @patch("tv_scraper.KinopoiskClient")
    def test_distributions_skipped_on_fallback(self, MockClient, MockCache):
        """Distributions are NOT fetched when serving from stale cache (from_fallback=True)."""
        mock_cache = MockCache.return_value

        def cache_get_side_effect(key):
            return None
        mock_cache.get.side_effect = cache_get_side_effect
        mock_cache.get_stale.return_value = {"id": 462682}

        mock_client = MockClient.return_value
        mock_client.fetch_details_raw.return_value = None
        mock_client.parse_details.return_value = MovieDetails(
            kinopoisk_id=462682, imdb_id="tt0903747",
            title_ru="Во все тяжкие", title_original="Breaking Bad",
            year=2008, plot="Описание", ratings=[]
        )
        mock_client.fetch_staff_raw.return_value = None
        mock_client.parse_staff.return_value = ([], [], [])

        settings = _mock_settings(show_ratings_in_plot=False, enable_trailers=False)
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "462682"}}

        result = _handle_getdetails(params, 1, settings, logger)

        assert result is True
        mock_client.fetch_distributions_raw.assert_not_called()


# ---------------------------------------------------------------------------
# BL-61: setPlotOutline and setPremiered in _apply_tvshow_details_to_listitem
# ---------------------------------------------------------------------------

class TestBL61PlotOutlineAndPremiered:
    """Tests for BL-61: setPlotOutline and setPremiered in _apply_tvshow_details_to_listitem."""

    def test_setPlotOutline_called_when_present(self):
        """setPlotOutline is called when details.plot_outline is non-empty."""
        details = _make_tvshow_details()
        details.plot_outline = "Краткое описание сериала"

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setPlotOutline.assert_called_once_with("Краткое описание сериала")

    def test_setPlotOutline_not_called_when_empty(self):
        """setPlotOutline is NOT called when details.plot_outline is empty."""
        details = _make_tvshow_details()
        details.plot_outline = ""

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setPlotOutline.assert_not_called()

    def test_setPremiered_called_when_present(self):
        """setPremiered is called when details.premiere_date is non-empty."""
        details = _make_tvshow_details()
        details.premiere_date = "2008-01-20"

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setPremiered.assert_called_once_with("2008-01-20")

    def test_setPremiered_not_called_when_empty(self):
        """setPremiered is NOT called when details.premiere_date is empty."""
        details = _make_tvshow_details()
        details.premiere_date = ""

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setPremiered.assert_not_called()

    def test_both_plot_outline_and_premiere_set(self):
        """Both setPlotOutline and setPremiered are called when both fields are present."""
        details = _make_tvshow_details()
        details.plot_outline = "Краткое описание"
        details.premiere_date = "2008-01-20"

        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings(show_ratings_in_plot=False)
        logger = _mock_logger()

        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)

        infotag.setPlotOutline.assert_called_once_with("Краткое описание")
        infotag.setPremiered.assert_called_once_with("2008-01-20")
