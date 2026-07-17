from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call

from models import SeasonArtInfo
from tv_scraper import _apply_season_art
from logger import Logger
from settings_manager import SettingsManager


def _mock_settings(use_tvmaze=True, use_season_art=True):
    settings = MagicMock(spec=SettingsManager)
    settings.use_tvmaze = use_tvmaze
    settings.use_season_art = use_season_art
    return settings


def _mock_logger():
    return MagicMock(spec=Logger)


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_success(mock_tvmaze_cls):
    mock_tvmaze = MagicMock()
    mock_tvmaze_cls.return_value = mock_tvmaze
    mock_tvmaze.lookup_show.return_value = 42
    mock_tvmaze.get_seasons.return_value = [
        SeasonArtInfo(1, "Season 1", "http://o1.jpg", "http://m1.jpg"),
        SeasonArtInfo(2, "Part Two", "http://o2.jpg", "http://m2.jpg"),
    ]

    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=True, use_season_art=True)
    logger = _mock_logger()

    _apply_season_art("tt1234567", infotag, settings, logger)

    mock_tvmaze.lookup_show.assert_called_once_with("tt1234567")
    mock_tvmaze.get_seasons.assert_called_once_with(42)
    assert infotag.addSeason.call_count == 2
    infotag.addSeason.assert_any_call(1, "Season 1")
    infotag.addSeason.assert_any_call(2, "Part Two")
    assert infotag.addAvailableArtwork.call_count == 2
    infotag.addAvailableArtwork.assert_any_call(
        "http://o1.jpg", arttype="poster", preview="http://m1.jpg", season=1
    )
    infotag.addAvailableArtwork.assert_any_call(
        "http://o2.jpg", arttype="poster", preview="http://m2.jpg", season=2
    )


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_tvmaze_disabled(mock_tvmaze_cls):
    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=False, use_season_art=True)
    logger = _mock_logger()

    _apply_season_art("tt1234567", infotag, settings, logger)

    mock_tvmaze_cls.assert_not_called()
    infotag.addSeason.assert_not_called()


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_season_art_disabled(mock_tvmaze_cls):
    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=True, use_season_art=False)
    logger = _mock_logger()

    _apply_season_art("tt1234567", infotag, settings, logger)

    mock_tvmaze_cls.assert_not_called()
    infotag.addSeason.assert_not_called()


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_no_imdb_id(mock_tvmaze_cls):
    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=True, use_season_art=True)
    logger = _mock_logger()

    _apply_season_art("", infotag, settings, logger)

    mock_tvmaze_cls.assert_not_called()


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_show_not_found(mock_tvmaze_cls):
    mock_tvmaze = MagicMock()
    mock_tvmaze_cls.return_value = mock_tvmaze
    mock_tvmaze.lookup_show.return_value = None

    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=True, use_season_art=True)
    logger = _mock_logger()

    _apply_season_art("tt1234567", infotag, settings, logger)

    mock_tvmaze.lookup_show.assert_called_once_with("tt1234567")
    mock_tvmaze.get_seasons.assert_not_called()
    infotag.addSeason.assert_not_called()


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_seasons_error(mock_tvmaze_cls):
    mock_tvmaze = MagicMock()
    mock_tvmaze_cls.return_value = mock_tvmaze
    mock_tvmaze.lookup_show.return_value = 42
    mock_tvmaze.get_seasons.return_value = None

    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=True, use_season_art=True)
    logger = _mock_logger()

    _apply_season_art("tt1234567", infotag, settings, logger)

    mock_tvmaze.get_seasons.assert_called_once_with(42)
    infotag.addSeason.assert_not_called()


@patch("tv_scraper.TvmazeClient")
def test_apply_season_art_season_without_poster(mock_tvmaze_cls):
    mock_tvmaze = MagicMock()
    mock_tvmaze_cls.return_value = mock_tvmaze
    mock_tvmaze.lookup_show.return_value = 42
    mock_tvmaze.get_seasons.return_value = [
        SeasonArtInfo(1, "Season 1", "", ""),
        SeasonArtInfo(2, "Season 2", "http://o2.jpg", "http://m2.jpg"),
    ]

    infotag = MagicMock()
    settings = _mock_settings(use_tvmaze=True, use_season_art=True)
    logger = _mock_logger()

    _apply_season_art("tt1234567", infotag, settings, logger)

    assert infotag.addSeason.call_count == 2
    infotag.addSeason.assert_any_call(1, "Season 1")
    infotag.addSeason.assert_any_call(2, "Season 2")
    assert infotag.addAvailableArtwork.call_count == 1
    infotag.addAvailableArtwork.assert_called_once_with(
        "http://o2.jpg", arttype="poster", preview="http://m2.jpg", season=2
    )
