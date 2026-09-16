"""Tests for BL-60 (premiere date) and BL-61 (plot outline / shortDescription).

Covers:
  - KinopoiskClient.parse_details: shortDescription -> plot_outline
  - KinopoiskClient.parse_premiere_date: priority logic
  - _apply_movie_details_to_listitem: setPlotOutline / setPremiered calls
  - NFO roundtrip: write -> read preserves premiere_date and plot_outline
"""
from __future__ import annotations

from unittest.mock import MagicMock

from kinopoisk_api import KinopoiskClient
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
# 1-2. KinopoiskClient.parse_details: shortDescription -> plot_outline
# ===========================================================================

class TestParseDetailsPlotOutline:
    """BL-61: shortDescription parsed into plot_outline."""

    def test_parse_details_with_short_description(self):
        """shortDescription present -> plot_outline is set."""
        client, logger = _make_client()
        data = {
            "kinopoiskId": 301,
            "nameRu": "Матрица",
            "nameOriginal": "The Matrix",
            "year": 1999,
            "description": "Описание",
            "shortDescription": "Краткий текст...",
            "filmLength": 136,
            "ratingMpaa": "r",
            "ratingKinopoisk": 8.5,
            "ratingKinopoiskVoteCount": 665000,
            "ratingImdb": 8.7,
            "ratingImdbVoteCount": 1900000,
            "posterUrl": "",
            "genres": [],
            "countries": [],
        }
        details = client.parse_details(data)
        assert details.plot_outline == "Краткий текст..."

    def test_parse_details_without_short_description(self):
        """shortDescription is None -> plot_outline == ''."""
        client, logger = _make_client()
        data = {
            "kinopoiskId": 999,
            "nameRu": "Тест",
            "nameOriginal": "Test",
            "year": 2020,
            "description": "Описание",
            "shortDescription": None,
            "filmLength": 90,
            "ratingMpaa": None,
            "ratingKinopoisk": None,
            "ratingKinopoiskVoteCount": None,
            "ratingImdb": None,
            "ratingImdbVoteCount": None,
            "posterUrl": "",
            "genres": [],
            "countries": [],
        }
        details = client.parse_details(data)
        assert details.plot_outline == ""


# ===========================================================================
# 3-7. KinopoiskClient.parse_premiere_date: priority logic
# ===========================================================================

class TestParsePremiereDate:
    """BL-60: premiere date parsing priority and edge cases."""

    def test_parse_premiere_date_world_premier(self):
        """WORLD_PREMIER is selected first."""
        client, logger = _make_client()
        data = {
            "items": [
                {
                    "type": "WORLD_PREMIER",
                    "date": "1999-03-24",
                    "country": {"country": "США"},
                },
                {
                    "type": "COUNTRY_SPECIFIC",
                    "date": "1999-10-14",
                    "country": {"country": "Россия"},
                },
            ]
        }
        result = client.parse_premiere_date(data)
        assert result == "1999-03-24"

    def test_parse_premiere_date_country_specific_fallback(self):
        """No WORLD_PREMIER -> COUNTRY_SPECIFIC (Russia) used as fallback."""
        client, logger = _make_client()
        data = {
            "items": [
                {
                    "type": "COUNTRY_SPECIFIC",
                    "date": "1999-10-14",
                    "country": {"country": "Россия"},
                },
                {
                    "type": "PREMIERE",
                    "date": "1999-04-08",
                    "country": {"country": "Австралия"},
                },
            ]
        }
        result = client.parse_premiere_date(data)
        assert result == "1999-10-14"

    def test_parse_premiere_date_premiere_fallback(self):
        """No WORLD_PREMIER, no Russia -> min(PREMIERE dates)."""
        client, logger = _make_client()
        data = {
            "items": [
                {
                    "type": "PREMIERE",
                    "date": "1999-04-08",
                    "country": {"country": "Австралия"},
                },
                {
                    "type": "PREMIERE",
                    "date": "1999-03-31",
                    "country": {"country": "Канада"},
                },
            ]
        }
        result = client.parse_premiere_date(data)
        assert result == "1999-03-31"

    def test_parse_premiere_date_no_data(self):
        """Empty items -> empty string."""
        client, logger = _make_client()
        data = {"items": []}
        result = client.parse_premiere_date(data)
        assert result == ""

    def test_parse_premiere_date_null_dates(self):
        """Items with date=null are skipped; valid PREMIERE date used."""
        client, logger = _make_client()
        data = {
            "items": [
                {
                    "type": "WORLD_PREMIER",
                    "date": None,
                    "country": {"country": "США"},
                },
                {
                    "type": "PREMIERE",
                    "date": "2000-01-01",
                    "country": {"country": "UK"},
                },
            ]
        }
        result = client.parse_premiere_date(data)
        assert result == "2000-01-01"


# ===========================================================================
# 8-11. _apply_movie_details_to_listitem: setPlotOutline / setPremiered
# ===========================================================================

class TestApplyListitemBL60BL61:
    """Verify that _apply_movie_details_to_listitem calls setPlotOutline/setPremiered."""

    def _call_apply(self, details):
        """Create mock listitem and call _apply_movie_details_to_listitem."""
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag

        settings = _mock_settings()
        logger = _mock_logger()

        _apply_movie_details_to_listitem(details, listitem, settings, logger)
        return infotag

    def test_apply_listitem_plot_outline(self):
        """setPlotOutline called with correct value."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            year=1999,
            plot_outline="Краткий текст",
        )
        infotag = self._call_apply(details)
        infotag.setPlotOutline.assert_called_once_with("Краткий текст")

    def test_apply_listitem_premiered(self):
        """setPremiered called with correct value."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            year=1999,
            premiere_date="1999-03-24",
        )
        infotag = self._call_apply(details)
        infotag.setPremiered.assert_called_once_with("1999-03-24")

    def test_apply_listitem_no_premiere(self):
        """setPremiered NOT called when premiere_date is empty."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            year=1999,
            premiere_date="",
        )
        infotag = self._call_apply(details)
        infotag.setPremiered.assert_not_called()

    def test_apply_listitem_no_plot_outline(self):
        """setPlotOutline NOT called when plot_outline is empty."""
        details = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            year=1999,
            plot_outline="",
        )
        infotag = self._call_apply(details)
        infotag.setPlotOutline.assert_not_called()


# ===========================================================================
# 12. NFO roundtrip: write -> read preserves premiered and outline
# ===========================================================================

class TestNfoRoundtripBL60BL61:
    """NFO write -> parse roundtrip for premiere_date and plot_outline."""

    def test_nfo_roundtrip_premiered_outline(self):
        """_build_movie_xml -> NfoParser.parse_full_movie preserves values."""
        details = MovieDetails(
            kinopoisk_id=301,
            imdb_id="tt0133093",
            title_ru="Матрица",
            title_original="The Matrix",
            year=1999,
            premiere_date="1999-03-24",
            plot_outline="Краткий текст",
        )

        xml_content = _build_movie_xml(details)

        parser = NfoParser(logger=MagicMock())
        parsed = parser.parse_full_movie(xml_content)

        assert parsed is not None
        assert parsed.premiere_date == "1999-03-24"
        assert parsed.plot_outline == "Краткий текст"
