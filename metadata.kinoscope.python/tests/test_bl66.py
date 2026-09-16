"""Tests for BL-66 (original_language).

Covers:
  - country_to_language: mapping countries to ISO 639-1 language codes
  - KinopoiskClient.parse_details: countries -> original_language
  - _apply_movie_details_to_listitem: setOriginalLanguage calls
  - NFO roundtrip: write -> read preserves original_language
"""
from __future__ import annotations

from unittest.mock import MagicMock

from kinopoisk_api import KinopoiskClient, country_to_language
from models import MovieDetails, DataSource
from nfo_writer import _build_movie_xml
from nfo_parser import NfoParser
from scraper import _apply_movie_details_to_listitem
from logger import Logger
from settings_manager import SettingsManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    logger = MagicMock(spec=Logger)
    return KinopoiskClient("test-api-key", logger), logger


def _mock_settings():
    settings = MagicMock(spec=SettingsManager)
    settings.preferred_rating_source = DataSource.KINOPOISK
    return settings


def _mock_logger():
    return MagicMock(spec=Logger)


# ===========================================================================
# 1. country_to_language: mapping countries to language codes
# ===========================================================================

class TestCountryToLanguage:
    """BL-66: country_to_language utility function."""

    def test_russia_to_ru(self):
        """Russia maps to 'ru'."""
        logger = _mock_logger()
        assert country_to_language(["Россия"], logger) == "ru"

    def test_usa_to_en(self):
        """USA maps to 'en'."""
        logger = _mock_logger()
        assert country_to_language(["США"], logger) == "en"

    def test_first_country_wins(self):
        """Only the first country in the list is used."""
        logger = _mock_logger()
        assert country_to_language(["США", "Великобритания"], logger) == "en"

    def test_japan_to_ja(self):
        """Japan maps to 'ja'."""
        logger = _mock_logger()
        assert country_to_language(["Япония"], logger) == "ja"

    def test_unknown_country_returns_empty(self):
        """Unmapped country returns empty string."""
        logger = _mock_logger()
        assert country_to_language(["Бутан"], logger) == ""

    def test_empty_countries_returns_empty(self):
        """Empty list returns empty string."""
        logger = _mock_logger()
        assert country_to_language([], logger) == ""

    def test_ussr_to_ru(self):
        """USSR maps to 'ru'."""
        logger = _mock_logger()
        assert country_to_language(["СССР"], logger) == "ru"


# ===========================================================================
# 2. KinopoiskClient.parse_details: countries -> original_language
# ===========================================================================

class TestParseDetailsOriginalLanguage:
    """BL-66: parse_details sets original_language from countries."""

    _BASE_DATA = {
        "kinopoiskId": 301,
        "nameRu": "Тест",
        "nameOriginal": "Test",
        "year": 2024,
        "description": "",
        "shortDescription": None,
        "filmLength": 90,
        "ratingMpaa": None,
        "ratingKinopoisk": None,
        "ratingKinopoiskVoteCount": None,
        "ratingImdb": None,
        "ratingImdbVoteCount": None,
        "posterUrl": "",
        "genres": [],
        "countries": [{"country": "Россия"}],
    }

    def _data_with_countries(self, countries):
        """Return a copy of base data with overridden countries."""
        data = dict(self._BASE_DATA)
        data["countries"] = countries
        return data

    def test_parse_details_original_language_russia(self):
        """countries=[Russia] -> original_language='ru'."""
        client, _ = _make_client()
        data = self._data_with_countries([{"country": "Россия"}])
        details = client.parse_details(data)
        assert details.original_language == "ru"

    def test_parse_details_original_language_empty_countries(self):
        """Empty countries list -> original_language=''."""
        client, _ = _make_client()
        data = self._data_with_countries([])
        details = client.parse_details(data)
        assert details.original_language == ""

    def test_parse_details_original_language_unknown(self):
        """Unmapped country -> original_language=''."""
        client, _ = _make_client()
        data = self._data_with_countries([{"country": "Бутан"}])
        details = client.parse_details(data)
        assert details.original_language == ""


# ===========================================================================
# 3. _apply_movie_details_to_listitem: setOriginalLanguage
# ===========================================================================

class TestApplyListitemOriginalLanguage:
    """BL-66: _apply_movie_details_to_listitem calls setOriginalLanguage."""

    def _call_apply(self, details):
        """Create mock listitem and call _apply_movie_details_to_listitem."""
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_movie_details_to_listitem(details, listitem, settings, logger)
        return infotag

    def test_set_original_language_called(self):
        """setOriginalLanguage called with 'ru' when original_language='ru'."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Тест",
            year=2024,
            original_language="ru",
        )
        infotag = self._call_apply(details)
        infotag.setOriginalLanguage.assert_called_once_with("ru")

    def test_set_original_language_empty_not_called(self):
        """setOriginalLanguage NOT called when original_language is empty."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Тест",
            year=2024,
            original_language="",
        )
        infotag = self._call_apply(details)
        infotag.setOriginalLanguage.assert_not_called()

    def test_set_original_language_attribute_error(self):
        """AttributeError from setOriginalLanguage is caught gracefully."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Тест",
            year=2024,
            original_language="en",
        )
        listitem = MagicMock()
        infotag = MagicMock()
        infotag.setOriginalLanguage.side_effect = AttributeError(
            "setOriginalLanguage not available"
        )
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        # Must not raise
        _apply_movie_details_to_listitem(details, listitem, settings, logger)


# ===========================================================================
# 4. NFO roundtrip: write -> read preserves original_language
# ===========================================================================

class TestNfoRoundtripOriginalLanguage:
    """BL-66: NFO write -> parse roundtrip for original_language."""

    def test_nfo_roundtrip_original_language(self):
        """_build_movie_xml -> NfoParser.parse_full_movie preserves language."""
        details = MovieDetails(
            kinopoisk_id=1,
            title_ru="Test",
            year=2024,
            original_language="ja",
        )
        xml = _build_movie_xml(details)
        assert "<language>ja</language>" in xml

        parser = NfoParser(logger=_mock_logger())
        parsed = parser.parse_full_movie(xml)
        assert parsed is not None
        assert parsed.original_language == "ja"

    def test_nfo_no_language_tag_when_empty(self):
        """No <language> tag emitted when original_language is empty."""
        details = MovieDetails(
            kinopoisk_id=2,
            title_ru="Test2",
            year=2024,
            original_language="",
        )
        xml = _build_movie_xml(details)
        assert "<language>" not in xml
