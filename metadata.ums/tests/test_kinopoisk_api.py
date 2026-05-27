import json
import os
from unittest.mock import patch, MagicMock
from kinopoisk_api import KinopoiskClient
from models import DataSource, ArtworkType
from logger import Logger


def _load_fixture(name):
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_client():
    logger = MagicMock(spec=Logger)
    return KinopoiskClient("test-api-key", logger), logger


class TestSearch:
    @patch("kinopoisk_api._kp_global_limiter")
    def test_search_returns_results(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_search_matrix.json")

        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Matrix")
            assert len(results) == 2
            assert results[0].title_ru == "Матрица"
            assert results[0].kinopoisk_id == 301
            assert results[0].year == 1999

    @patch("kinopoisk_api._kp_global_limiter")
    def test_search_sorts_by_year(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_search_matrix.json")

        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Matrix", "1999")
            assert results[0].year == 1999
            assert results[1].year == 2003

    @patch("kinopoisk_api._kp_global_limiter")
    def test_search_empty_response(self, mock_limiter):
        client, logger = _make_client()

        with patch.object(client._http, "get_json", return_value={"films": []}):
            results = client.search("NonExistentMovie")
            assert results == []

    @patch("kinopoisk_api._kp_global_limiter")
    def test_search_http_error(self, mock_limiter):
        from http_client import HttpError
        client, logger = _make_client()

        with patch.object(client._http, "get_json", side_effect=HttpError(500, "Error", "url")):
            results = client.search("Matrix")
            assert results == []


class TestGetDetails:
    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_details_success(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_details_301.json")

        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(301)
            assert details is not None
            assert details.kinopoisk_id == 301
            assert details.title_ru == "Матрица"
            assert details.title_original == "The Matrix"
            assert details.year == 1999
            assert details.runtime == 136
            assert details.mpaa == "R"
            assert "Фантастика" in details.genres
            assert "США" in details.countries
            assert details.imdb_id == "tt0133093"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_details_ratings(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_details_301.json")

        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(301)
            kp_ratings = [r for r in details.ratings if r.source == DataSource.KINOPOISK]
            imdb_ratings = [r for r in details.ratings if r.source == DataSource.IMDB]
            assert len(kp_ratings) == 1
            assert kp_ratings[0].value == 8.5
            assert len(imdb_ratings) == 1
            assert imdb_ratings[0].value == 8.7

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_details_poster(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_details_301.json")

        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(301)
            posters = [a for a in details.artwork if a.artwork_type == ArtworkType.POSTER]
            assert len(posters) == 1
            assert "301.jpg" in posters[0].url

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_details_null_fields(self, mock_limiter):
        client, logger = _make_client()
        fixture = {
            "kinopoiskId": 999,
            "imdbId": None,
            "nameRu": None,
            "nameOriginal": "Test Movie",
            "year": 2020,
            "description": None,
            "slogan": None,
            "filmLength": None,
            "ratingMpaa": None,
            "ratingKinopoisk": None,
            "ratingKinopoiskVoteCount": None,
            "ratingImdb": None,
            "ratingImdbVoteCount": None,
            "posterUrl": "",
            "posterUrlPreview": "",
            "genres": [],
            "countries": []
        }
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(999)
            assert details is not None
            assert details.title_ru == "Test Movie"
            assert details.imdb_id == ""
            assert details.plot == ""
            assert details.ratings == []
            assert details.artwork == []

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_details_http_error(self, mock_limiter):
        from http_client import HttpError
        client, logger = _make_client()

        with patch.object(client._http, "get_json", side_effect=HttpError(404, "Not found", "url")):
            details = client.get_details(301)
            assert details is None


class TestGetDetailsMpaaFallback:
    """Tests for ratingAgeLimits -> MPAA fallback when ratingMpaa is empty."""

    def _minimal_fixture(self, rating_mpaa=None, rating_age_limits=None):
        return {
            "kinopoiskId": 1,
            "imdbId": "tt0000001",
            "nameRu": "Test",
            "nameOriginal": "Test",
            "year": 2020,
            "description": "",
            "slogan": "",
            "filmLength": 90,
            "ratingMpaa": rating_mpaa,
            "ratingAgeLimits": rating_age_limits,
            "ratingKinopoisk": None,
            "ratingKinopoiskVoteCount": None,
            "ratingImdb": None,
            "ratingImdbVoteCount": None,
            "posterUrl": "",
            "posterUrlPreview": "",
            "genres": [],
            "countries": [],
        }

    @patch("kinopoisk_api._kp_global_limiter")
    def test_age16_maps_to_r(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="", rating_age_limits="age16")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == "R"
        logger.info.assert_called()

    @patch("kinopoisk_api._kp_global_limiter")
    def test_age12_maps_to_pg13(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="", rating_age_limits="age12")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == "PG-13"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_age6_maps_to_g(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="", rating_age_limits="age6")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == "G"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_age0_maps_to_g(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="", rating_age_limits="age0")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == "G"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_age18_maps_to_nc17(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="", rating_age_limits="age18")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == "NC-17"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_rating_mpaa_takes_priority_over_age_limits(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="PG", rating_age_limits="age12")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == "PG"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_both_empty_yields_empty_mpaa(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa="", rating_age_limits="")
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == ""

    @patch("kinopoisk_api._kp_global_limiter")
    def test_both_none_yields_empty_mpaa(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa=None, rating_age_limits=None)
        with patch.object(client._http, "get_json", return_value=fixture):
            details = client.get_details(1)
        assert details.mpaa == ""

    @patch("kinopoisk_api._kp_global_limiter")
    def test_fallback_logs_mapping(self, mock_limiter):
        client, logger = _make_client()
        fixture = self._minimal_fixture(rating_mpaa=None, rating_age_limits="age16")
        with patch.object(client._http, "get_json", return_value=fixture):
            client.get_details(1)
        info_calls = " ".join(str(c) for c in logger.info.call_args_list)
        assert "age16" in info_calls
        assert "R" in info_calls


class TestGetStaff:
    @patch("kinopoisk_api._kp_staff_limiter")
    def test_get_staff_success(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_staff_301.json")

        with patch.object(client._http_staff, "get_json", return_value=fixture):
            directors, writers, cast = client.get_staff(301)
            assert len(directors) == 1
            assert directors[0].name_ru == "Лана Вачовски"
            assert len(writers) == 1
            assert writers[0].name_ru == "Лилли Вачовски"
            assert len(cast) == 3
            assert cast[0].name_ru == "Киану Ривз"
            assert cast[0].role == "Neo"

    @patch("kinopoisk_api._kp_staff_limiter")
    def test_get_staff_http_error(self, mock_limiter):
        from http_client import HttpError
        client, logger = _make_client()

        with patch.object(client._http_staff, "get_json", side_effect=HttpError(500, "Err", "url")):
            directors, writers, cast = client.get_staff(301)
            assert directors == []
            assert writers == []
            assert cast == []


class TestGetImages:
    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_images_success(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_images_301.json")

        with patch.object(client._http, "get_json", return_value=fixture):
            artworks = client.get_images(301, ["STILL"])
            assert len(artworks) == 2
            assert artworks[0].artwork_type == ArtworkType.FANART
            assert "301_1.jpg" in artworks[0].url

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_images_empty(self, mock_limiter):
        client, logger = _make_client()

        with patch.object(client._http, "get_json", return_value={"items": []}):
            artworks = client.get_images(301, ["POSTER"])
            assert artworks == []


class TestSearchWithTypeFilter:
    """Tests for search() with the type_filter parameter."""

    @patch("kinopoisk_api._kp_global_limiter")
    def test_film_filter_excludes_tv_series(self, mock_limiter):
        """With type_filter=["FILM"], TV_SERIES items should be filtered out."""
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Film Item", "year": "2020",
                 "type": "FILM", "rating": "7.0"},
                {"filmId": 2, "nameRu": "TV Series Item", "year": "2020",
                 "type": "TV_SERIES", "rating": "8.0"},
                {"filmId": 3, "nameRu": "Mini Series Item", "year": "2019",
                 "type": "MINI_SERIES", "rating": "6.0"},
            ]
        }

        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Test", type_filter=["FILM"])
            assert len(results) == 1
            assert results[0].title_ru == "Film Item"
            assert results[0].kinopoisk_id == 1

    @patch("kinopoisk_api._kp_global_limiter")
    def test_tv_filter_excludes_film(self, mock_limiter):
        """With type_filter=["TV_SERIES","MINI_SERIES","TV_SHOW"], FILM filtered out."""
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Film Item", "year": "2020",
                 "type": "FILM", "rating": "7.0"},
                {"filmId": 2, "nameRu": "TV Series Item", "year": "2020",
                 "type": "TV_SERIES", "rating": "8.0"},
                {"filmId": 3, "nameRu": "Mini Series Item", "year": "2019",
                 "type": "MINI_SERIES", "rating": "6.0"},
                {"filmId": 4, "nameRu": "TV Show Item", "year": "2021",
                 "type": "TV_SHOW", "rating": "5.5"},
            ]
        }
        tv_filter = ["TV_SERIES", "MINI_SERIES", "TV_SHOW"]

        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Test", type_filter=tv_filter)
            assert len(results) == 3
            titles = [r.title_ru for r in results]
            assert "Film Item" not in titles
            assert "TV Series Item" in titles
            assert "Mini Series Item" in titles
            assert "TV Show Item" in titles

    @patch("kinopoisk_api._kp_global_limiter")
    def test_no_type_filter_returns_all(self, mock_limiter):
        """With type_filter=None, all results should be returned (backward compat)."""
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Film", "year": "2020",
                 "type": "FILM", "rating": "7.0"},
                {"filmId": 2, "nameRu": "Series", "year": "2020",
                 "type": "TV_SERIES", "rating": "8.0"},
            ]
        }

        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Test", type_filter=None)
            assert len(results) == 2

    @patch("kinopoisk_api._kp_global_limiter")
    def test_type_filter_logs_filtered_count(self, mock_limiter):
        """When items are filtered, the count should be logged."""
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Film", "year": "2020",
                 "type": "FILM", "rating": "7.0"},
                {"filmId": 2, "nameRu": "Series", "year": "2020",
                 "type": "TV_SERIES", "rating": "8.0"},
            ]
        }

        with patch.object(client._http, "get_json", return_value=fixture):
            client.search("Test", type_filter=["FILM"])
            # Logger should mention filtered count
            info_calls = [str(c) for c in logger.info.call_args_list]
            assert any("filtered" in c for c in info_calls)


class TestGetSeasons:
    """Tests for get_seasons() method."""

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_seasons_success(self, mock_limiter):
        """Parsed Season/Episode objects from a typical API response."""
        client, logger = _make_client()
        fixture = {
            "total": 2,
            "items": [
                {
                    "number": 1,
                    "episodes": [
                        {
                            "seasonNumber": 1,
                            "episodeNumber": 1,
                            "nameRu": "Пилот",
                            "nameEn": "Pilot",
                            "synopsis": "First episode",
                            "releaseDate": "2008-01-20",
                        },
                        {
                            "seasonNumber": 1,
                            "episodeNumber": 2,
                            "nameRu": "Кот в мешке",
                            "nameEn": "Cat's in the Bag...",
                            "synopsis": "Second episode",
                            "releaseDate": "2008-01-27",
                        },
                    ],
                },
                {
                    "number": 2,
                    "episodes": [
                        {
                            "seasonNumber": 2,
                            "episodeNumber": 1,
                            "nameRu": "Семь-тридцать семь",
                            "nameEn": "Seven Thirty-Seven",
                            "synopsis": "Season 2 premiere",
                            "releaseDate": "2009-03-08",
                        },
                    ],
                },
            ],
        }

        with patch.object(client._http, "get_json", return_value=fixture):
            seasons = client.get_seasons(462682)

        assert len(seasons) == 2
        assert seasons[0].number == 1
        assert len(seasons[0].episodes) == 2
        assert seasons[0].episodes[0].title_ru == "Пилот"
        assert seasons[0].episodes[0].title_en == "Pilot"
        assert seasons[0].episodes[0].season_number == 1
        assert seasons[0].episodes[0].episode_number == 1
        assert seasons[0].episodes[0].synopsis == "First episode"
        assert seasons[0].episodes[0].release_date == "2008-01-20"
        assert seasons[0].episodes[1].episode_number == 2
        assert seasons[1].number == 2
        assert len(seasons[1].episodes) == 1
        assert seasons[1].episodes[0].title_en == "Seven Thirty-Seven"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_seasons_empty_items(self, mock_limiter):
        """Empty items list should return []."""
        client, logger = _make_client()

        with patch.object(client._http, "get_json", return_value={"items": []}):
            seasons = client.get_seasons(462682)

        assert seasons == []
        logger.warning.assert_called()

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_seasons_http_error(self, mock_limiter):
        """HttpError should return [] and log error."""
        from http_client import HttpError
        client, logger = _make_client()

        with patch.object(
            client._http, "get_json",
            side_effect=HttpError(500, "Internal Server Error", "url")
        ):
            seasons = client.get_seasons(462682)

        assert seasons == []
        logger.error.assert_called()

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_seasons_missing_episode_fields(self, mock_limiter):
        """Missing fields in episode data should use defaults."""
        client, logger = _make_client()
        fixture = {
            "items": [
                {
                    "number": 1,
                    "episodes": [
                        {
                            "seasonNumber": 1,
                            "episodeNumber": 1,
                            # nameRu, nameEn, synopsis, releaseDate all missing
                        },
                        {
                            "episodeNumber": 2,
                            # seasonNumber also missing
                            "nameRu": None,
                            "nameEn": "Some Title",
                            "synopsis": None,
                            "releaseDate": None,
                        },
                    ],
                },
            ],
        }

        with patch.object(client._http, "get_json", return_value=fixture):
            seasons = client.get_seasons(999)

        assert len(seasons) == 1
        ep1 = seasons[0].episodes[0]
        assert ep1.title_ru == ""
        assert ep1.title_en == ""
        assert ep1.synopsis == ""
        assert ep1.release_date == ""

        ep2 = seasons[0].episodes[1]
        assert ep2.season_number == 0  # missing -> default 0
        assert ep2.title_ru == "Some Title"  # fallback from nameEn
        assert ep2.title_en == "Some Title"
        assert ep2.synopsis == ""  # None -> ""
        assert ep2.release_date == ""  # None -> ""

    @patch("kinopoisk_api._kp_global_limiter")
    def test_get_seasons_no_items_key(self, mock_limiter):
        """Response without items key should return []."""
        client, logger = _make_client()

        with patch.object(client._http, "get_json", return_value={}):
            seasons = client.get_seasons(462682)

        assert seasons == []


class TestSearchFuzzyRanking:
    """Tests for fuzzy-ranking in search() (BL-01 / KOD-7)."""

    @patch("kinopoisk_api._kp_global_limiter")
    def test_typo_ranks_correct_first(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_search_fuzzy.json")
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Interstllar", "2014")
        assert results[0].kinopoisk_id == 258687
        assert results[0].title_ru == "Интерстеллар"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_cyrillic_typo_ranking(self, mock_limiter):
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Бригадир", "nameEn": "", "year": "2005",
                 "rating": "6.0", "type": "FILM"},
                {"filmId": 2, "nameRu": "Бригада", "nameEn": "", "year": "2002",
                 "rating": "8.0", "type": "FILM"},
            ]
        }
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Бригата")
        assert results[0].title_ru == "Бригада"

    @patch("kinopoisk_api._kp_global_limiter")
    def test_exact_match_no_regression(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_search_matrix.json")
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("The Matrix", "1999")
        assert results[0].kinopoisk_id == 301
        assert results[0].year == 1999
        assert results[1].year == 2003

    @patch("kinopoisk_api._kp_global_limiter")
    def test_year_match_priority_over_score(self, mock_limiter):
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Interstellar Extra", "nameEn": "Interstellar Extra",
                 "year": "2020", "rating": "7.0", "type": "FILM"},
                {"filmId": 2, "nameRu": "Intrstllr", "nameEn": "Intrstllr",
                 "year": "2014", "rating": "6.0", "type": "FILM"},
            ]
        }
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Interstellar", "2014")
        assert results[0].year == 2014

    @patch("kinopoisk_api._kp_global_limiter")
    def test_same_score_same_year_sort_by_rating(self, mock_limiter):
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Матрица", "nameEn": "The Matrix",
                 "year": "1999", "rating": "7.0", "type": "FILM"},
                {"filmId": 2, "nameRu": "Матрица", "nameEn": "The Matrix",
                 "year": "1999", "rating": "9.0", "type": "FILM"},
            ]
        }
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("The Matrix", "1999")
        assert results[0].rating >= results[1].rating

    @patch("kinopoisk_api._kp_global_limiter")
    def test_empty_films_returns_empty(self, mock_limiter):
        client, logger = _make_client()
        with patch.object(client._http, "get_json", return_value={"films": []}):
            results = client.search("NonExistent")
        assert results == []

    @patch("kinopoisk_api._kp_global_limiter")
    def test_all_below_threshold_logs_warning(self, mock_limiter):
        client, logger = _make_client()
        fixture = {
            "films": [
                {"filmId": 1, "nameRu": "Абвгд", "nameEn": "Abcde",
                 "year": "2020", "rating": "5.0", "type": "FILM"},
            ]
        }
        with patch.object(client._http, "get_json", return_value=fixture):
            client.search("Xyztuvw")
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("similarity threshold" in c for c in warning_calls)

    @patch("kinopoisk_api._kp_global_limiter")
    def test_empty_names_score_zero_not_removed(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_search_fuzzy.json")
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Interstllar")
        assert len(results) == 4
        assert results[-1].kinopoisk_id == 300

    @patch("kinopoisk_api._kp_global_limiter")
    def test_no_year_sorts_by_score_then_rating(self, mock_limiter):
        client, logger = _make_client()
        fixture = _load_fixture("kp_search_fuzzy.json")
        with patch.object(client._http, "get_json", return_value=fixture):
            results = client.search("Interstellar")
        assert results[0].kinopoisk_id == 258687
