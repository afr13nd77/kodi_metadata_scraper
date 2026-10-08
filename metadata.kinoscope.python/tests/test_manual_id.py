from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from utils import parse_manual_id_input, ManualIdInput, details_to_search_result, resolve_manual_id
from models import MovieDetails, MovieSearchResult, Rating, Artwork, DataSource, ArtworkType, Person


class TestParseManualIdInput:
    @pytest.mark.parametrize("text,expected", [
        ("kp12345", ManualIdInput("kp", "12345")),
        ("KP12345", ManualIdInput("kp", "12345")),
        ("kp:12345", ManualIdInput("kp", "12345")),
        ("tt1234567", ManualIdInput("imdb", "tt1234567")),
        ("TT1234567", ManualIdInput("imdb", "tt1234567")),
        ("https://www.kinopoisk.ru/film/12345/", ManualIdInput("kp", "12345")),
        ("https://www.kinopoisk.ru/series/12345/", ManualIdInput("kp", "12345")),
        ("kinopoisk.ru/film/12345/", ManualIdInput("kp", "12345")),
        ("https://www.imdb.com/title/tt1234567/", ManualIdInput("imdb", "tt1234567")),
        ("https://www.imdb.com/title/tt1234567/?ref_=fn_al", ManualIdInput("imdb", "tt1234567")),
        ("kpabc", None),
        ("ttXYZ", None),
        ("Интерстеллар", None),
        ("12345", None),
        ("", None),
        ("  kp12345  ", ManualIdInput("kp", "12345")),
        ("kp0", ManualIdInput("kp", "0")),
        ("tt123", None),
        ("tt12345678", ManualIdInput("imdb", "tt12345678")),
    ])
    def test_parse(self, text, expected):
        assert parse_manual_id_input(text, MagicMock()) == expected


def _make_details(**kwargs) -> MovieDetails:
    base = dict(
        kinopoisk_id=12345,
        imdb_id="tt0816692",
        title_ru="Интерстеллар",
        title_original="Interstellar",
        year=2014,
        ratings=[Rating(DataSource.IMDB, 8.6, 100), Rating(DataSource.KINOPOISK, 8.7, 200)],
        artwork=[Artwork(url="http://full.jpg", preview_url="http://prev.jpg",
                         artwork_type=ArtworkType.POSTER)],
        directors=[Person(name_ru="Нолан")],
    )
    base.update(kwargs)
    return MovieDetails(**base)


class TestDetailsToSearchResult:
    def test_full_data(self):
        res = details_to_search_result(_make_details())
        assert isinstance(res, MovieSearchResult)
        assert res.title_ru == "Интерстеллар"
        assert res.title_original == "Interstellar"
        assert res.year == 2014
        assert res.kinopoisk_id == 12345
        assert res.imdb_id == "tt0816692"
        assert res.poster_url == "http://prev.jpg"
        assert res.rating == 8.7
        assert res.source == DataSource.KINOPOISK

    def test_no_artwork(self):
        assert details_to_search_result(_make_details(artwork=[])).poster_url == ""

    def test_no_ratings(self):
        assert details_to_search_result(_make_details(ratings=[])).rating == 0.0

    def test_imdb_id_passed(self):
        assert details_to_search_result(_make_details(imdb_id="tt0816692")).imdb_id == "tt0816692"


class TestResolveManualId:
    def _client(self, raw, details=None):
        client = MagicMock()
        client.fetch_details_raw.return_value = raw
        client.parse_details.return_value = details if details is not None else _make_details()
        return client

    def test_kp_success(self):
        client = self._client({"type": "FILM"})
        res = resolve_manual_id(ManualIdInput("kp", "12345"), client, MagicMock(), MagicMock(), ["FILM"])
        assert len(res) == 1
        assert res[0].kinopoisk_id == 12345
        client.fetch_details_raw.assert_called_once_with(12345)

    def test_kp_type_mismatch(self):
        client = self._client({"type": "TV_SERIES"})
        res = resolve_manual_id(ManualIdInput("kp", "12345"), client, MagicMock(), MagicMock(), ["FILM"])
        assert res == []
        client.parse_details.assert_not_called()

    def test_kp_api_error(self):
        client = self._client(None)
        res = resolve_manual_id(ManualIdInput("kp", "12345"), client, MagicMock(), MagicMock(), ["FILM"])
        assert res == []

    def test_imdb_success(self):
        client = self._client({"type": "FILM"})
        with patch("utils.search_kp_by_imdb", return_value=12345):
            res = resolve_manual_id(ManualIdInput("imdb", "tt0816692"), client, MagicMock(), MagicMock(), ["FILM"])
        assert len(res) == 1
        client.fetch_details_raw.assert_called_once_with(12345)

    def test_imdb_not_resolved(self):
        client = self._client({"type": "FILM"})
        with patch("utils.search_kp_by_imdb", return_value=0):
            res = resolve_manual_id(ManualIdInput("imdb", "tt0816692"), client, MagicMock(), MagicMock(), ["FILM"])
        assert res == []
        client.fetch_details_raw.assert_not_called()
