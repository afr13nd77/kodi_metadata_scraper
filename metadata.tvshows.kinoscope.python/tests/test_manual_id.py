from __future__ import annotations

from unittest.mock import MagicMock, patch

from utils import parse_manual_id_input, ManualIdInput, resolve_manual_id
from models import MovieDetails, Rating, DataSource

TV_TYPES = ["TV_SERIES", "MINI_SERIES", "TV_SHOW"]


def _make_client(content_type: str) -> MagicMock:
    client = MagicMock()
    client.fetch_details_raw.return_value = {"type": content_type}
    client.parse_details.return_value = MovieDetails(
        kinopoisk_id=77044,
        imdb_id="tt0903747",
        title_ru="Во все тяжкие",
        title_original="Breaking Bad",
        year=2008,
        ratings=[Rating(source=DataSource.KINOPOISK, value=8.9, votes=100)],
    )
    return client


class TestTvManualId:
    def test_tv_series_by_kp_id(self):
        client = _make_client("TV_SERIES")
        result = resolve_manual_id(
            ManualIdInput("kp", "77044"), client, MagicMock(), MagicMock(), TV_TYPES
        )
        assert len(result) == 1
        assert result[0].kinopoisk_id == 77044
        assert result[0].rating == 8.9

    def test_mini_series_by_kp_id(self):
        client = _make_client("MINI_SERIES")
        result = resolve_manual_id(
            ManualIdInput("kp", "77044"), client, MagicMock(), MagicMock(), TV_TYPES
        )
        assert len(result) == 1

    def test_film_rejected(self):
        client = _make_client("FILM")
        result = resolve_manual_id(
            ManualIdInput("kp", "77044"), client, MagicMock(), MagicMock(), TV_TYPES
        )
        assert result == []
        client.parse_details.assert_not_called()

    def test_imdb_id_for_series(self):
        client = _make_client("TV_SERIES")
        with patch("utils.search_kp_by_imdb", return_value=77044) as m:
            result = resolve_manual_id(
                ManualIdInput("imdb", "tt0903747"), client, MagicMock(), MagicMock(), TV_TYPES
            )
        m.assert_called_once()
        client.fetch_details_raw.assert_called_once_with(77044)
        assert len(result) == 1

    def test_parse_manual_id_input_basic(self):
        logger = MagicMock()
        assert parse_manual_id_input("kp77044", logger) == ManualIdInput("kp", "77044")
        assert parse_manual_id_input("tt0903747", logger) == ManualIdInput("imdb", "tt0903747")
        assert parse_manual_id_input("Breaking Bad", logger) is None
