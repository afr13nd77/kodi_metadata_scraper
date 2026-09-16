"""BL-66: original_language tests for TV scraper.

Tests cover:
- _apply_tvshow_details_to_listitem sets originalLanguage on InfoTag
- NFO roundtrip: _build_tvshow_xml writes <language>, NfoParser reads it back
"""
from __future__ import annotations

from unittest.mock import MagicMock

from models import TVShowDetails, DataSource
from nfo_writer import _build_tvshow_xml
from nfo_parser import NfoParser
from tv_scraper import _apply_tvshow_details_to_listitem
from logger import Logger
from settings_manager import SettingsManager


def _mock_settings():
    settings = MagicMock(spec=SettingsManager)
    settings.preferred_rating_source = DataSource.KINOPOISK
    settings.actor_name_language = "ru"
    return settings


def _mock_logger():
    return MagicMock(spec=Logger)


class TestApplyTVShowOriginalLanguage:
    """Tests for original_language handling in _apply_tvshow_details_to_listitem."""

    def _call_apply(self, details):
        listitem = MagicMock()
        infotag = MagicMock()
        listitem.getVideoInfoTag.return_value = infotag
        settings = _mock_settings()
        logger = _mock_logger()
        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)
        return infotag

    def test_set_original_language_called(self):
        """When original_language is set, setOriginalLanguage must be called."""
        details = TVShowDetails(
            kinopoisk_id=100,
            title_ru="Test Show",
            year=2024,
            original_language="ko",
        )
        infotag = self._call_apply(details)
        infotag.setOriginalLanguage.assert_called_once_with("ko")

    def test_set_original_language_empty_not_called(self):
        """When original_language is empty, setOriginalLanguage must NOT be called."""
        details = TVShowDetails(
            kinopoisk_id=101,
            title_ru="Test Show 2",
            year=2024,
            original_language="",
        )
        infotag = self._call_apply(details)
        infotag.setOriginalLanguage.assert_not_called()

    def test_set_original_language_attribute_error(self):
        """When setOriginalLanguage raises AttributeError (Kodi < v22), no exception propagates."""
        details = TVShowDetails(
            kinopoisk_id=102,
            title_ru="Test Show 3",
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
        _apply_tvshow_details_to_listitem(details, listitem, settings, logger)


class TestNfoRoundtripTVOriginalLanguage:
    """Tests for original_language NFO write/read roundtrip (TV)."""

    def test_nfo_roundtrip_tvshow_original_language(self):
        """original_language='ko' must survive write -> parse roundtrip."""
        details = TVShowDetails(
            kinopoisk_id=1,
            title_ru="Test",
            year=2024,
            original_language="ko",
        )
        xml = _build_tvshow_xml(details)
        assert "<language>ko</language>" in xml

        parser = NfoParser(logger=_mock_logger())
        parsed = parser.parse_full_tvshow(xml)
        assert parsed is not None
        assert parsed.original_language == "ko"

    def test_nfo_tvshow_no_language_when_empty(self):
        """When original_language is empty, <language> element must be absent."""
        details = TVShowDetails(
            kinopoisk_id=2,
            title_ru="Test2",
            year=2024,
            original_language="",
        )
        xml = _build_tvshow_xml(details)
        assert "<language>" not in xml
