from unittest.mock import patch, MagicMock

from utils import clean_title, extract_kinopoisk_id, extract_imdb_id, search_kp_by_imdb, transliterate_to_cyrillic, _has_cyrillic, extract_alt_title, deduplicate_results
from omdb_client import parse_award_tags
from kinopoisk_api import normalize_genres, _GENRE_RU_TO_EN
from logger import Logger
from settings_manager import SettingsManager
from models import MovieSearchResult


def _mock_logger():
    return MagicMock(spec=Logger)


# ---------------------------------------------------------------------------
# Tests for clean_title
# ---------------------------------------------------------------------------

class TestCleanTitleBracketsRemoval:
    def test_removes_single_brackets(self):
        logger = _mock_logger()
        candidates, year = clean_title("Matrix [Remastered]", logger)
        assert candidates == ["Matrix"]
        assert year == ""

    def test_removes_multiple_brackets(self):
        logger = _mock_logger()
        candidates, year = clean_title("Matrix [Remastered] [Open Matte]", logger)
        assert candidates == ["Matrix"]
        assert year == ""


class TestCleanTitleYearExtraction:
    def test_year_from_parentheses(self):
        logger = _mock_logger()
        candidates, year = clean_title("Inception (2010)", logger)
        assert year == "2010"
        assert candidates == ["Inception"]

    def test_bare_year_detection(self):
        logger = _mock_logger()
        candidates, year = clean_title("Inception.2010.BDRip", logger)
        assert year == "2010"
        assert candidates == ["Inception"]

    def test_no_year_in_title(self):
        logger = _mock_logger()
        candidates, year = clean_title("Inception", logger)
        assert year == ""
        assert candidates == ["Inception"]

    def test_non_year_four_digit_number(self):
        """4-digit numbers outside 19xx/20xx range should not be treated as years."""
        logger = _mock_logger()
        candidates, year = clean_title("Ocean.1234.quality", logger)
        assert year == ""


class TestCleanTitleDotReplacement:
    def test_dots_replaced_with_spaces(self):
        logger = _mock_logger()
        candidates, year = clean_title("The.Matrix", logger)
        assert candidates == ["The Matrix"]

    def test_underscores_replaced_with_spaces(self):
        logger = _mock_logger()
        candidates, year = clean_title("The_Matrix", logger)
        assert candidates == ["The Matrix"]

    def test_multiple_dots_collapsed(self):
        logger = _mock_logger()
        candidates, year = clean_title("The..Matrix..1999", logger)
        assert candidates == ["The Matrix"]
        assert year == "1999"


class TestCleanTitleSlashSplitting:
    def test_slash_splits_into_candidates(self):
        logger = _mock_logger()
        candidates, year = clean_title("Title RU / Title EN (2003)", logger)
        assert "Title RU" in candidates
        assert "Title EN" in candidates
        assert year == "2003"

    def test_no_slash_single_candidate(self):
        logger = _mock_logger()
        candidates, year = clean_title("Single Title", logger)
        assert candidates == ["Single Title"]


class TestCleanTitleCombinedCases:
    def test_brackets_year_slash_dots(self):
        logger = _mock_logger()
        candidates, year = clean_title(
            "Люди Икс 2 / X-Men 2 (2003) [Open Matte]", logger
        )
        assert candidates == ["Люди Икс 2", "X-Men 2"]
        assert year == "2003"

    def test_dotted_filename_with_year_and_junk(self):
        logger = _mock_logger()
        candidates, year = clean_title(
            "The.Chronicles.of.Riddick.2004.HDTVRip.Open.Matte", logger
        )
        assert candidates == ["The Chronicles of Riddick"]
        assert year == "2004"

    def test_empty_string(self):
        logger = _mock_logger()
        candidates, year = clean_title("", logger)
        assert candidates == []
        assert year == ""


# ---------------------------------------------------------------------------
# Tests for extract_kinopoisk_id
# ---------------------------------------------------------------------------

class TestExtractKinopoiskId:
    def test_from_json_uniqueids(self):
        logger = _mock_logger()
        params = {"uniqueIDs": '{"kinopoisk": "301"}'}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_from_dict_uniqueids(self):
        logger = _mock_logger()
        params = {"uniqueIDs": {"kinopoisk": "301"}}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_from_url_param(self):
        logger = _mock_logger()
        params = {"url": '{"kinopoisk": "555", "imdb": "tt0133093"}'}
        assert extract_kinopoisk_id(params, logger) == 555

    def test_from_direct_param(self):
        logger = _mock_logger()
        params = {"kinopoisk": "301"}
        assert extract_kinopoisk_id(params, logger) == 301

    def test_invalid_value(self):
        logger = _mock_logger()
        params = {"kinopoisk": "not_a_number"}
        assert extract_kinopoisk_id(params, logger) == 0
        logger.warning.assert_called()

    def test_no_id_present(self):
        logger = _mock_logger()
        assert extract_kinopoisk_id({}, logger) == 0

    def test_lowercase_uniqueids_key(self):
        logger = _mock_logger()
        params = {"uniqueids": {"kinopoisk": "301"}}
        assert extract_kinopoisk_id(params, logger) == 301


# ---------------------------------------------------------------------------
# Tests for extract_imdb_id
# ---------------------------------------------------------------------------

class TestExtractImdbId:
    def test_from_json_uniqueids(self):
        logger = _mock_logger()
        params = {"uniqueIDs": '{"imdb": "tt0133093"}'}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_from_dict_uniqueids(self):
        logger = _mock_logger()
        params = {"uniqueIDs": {"imdb": "tt0133093"}}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_from_url_param(self):
        logger = _mock_logger()
        params = {"url": '{"imdb": "tt0133093", "kinopoisk": "301"}'}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_from_direct_param(self):
        logger = _mock_logger()
        params = {"imdb": "tt0133093"}
        assert extract_imdb_id(params, logger) == "tt0133093"

    def test_no_id_present(self):
        logger = _mock_logger()
        assert extract_imdb_id({}, logger) == ""


# ---------------------------------------------------------------------------
# Tests for search_kp_by_imdb
# ---------------------------------------------------------------------------

class TestSearchKpByImdb:
    @patch("utils.KinopoiskClient")
    def test_found_result(self, MockKpClient):
        mock_client = MockKpClient.return_value
        mock_client.search.return_value = [
            MovieSearchResult(title_ru="Матрица", kinopoisk_id=301, year=1999)
        ]

        logger = _mock_logger()
        settings = MagicMock(spec=SettingsManager)
        settings.kinopoisk_api_key = "test-key"

        result = search_kp_by_imdb("tt0133093", settings, logger)

        assert result == 301
        mock_client.search.assert_called_once_with("tt0133093")

    @patch("utils.KinopoiskClient")
    def test_no_results(self, MockKpClient):
        mock_client = MockKpClient.return_value
        mock_client.search.return_value = []

        logger = _mock_logger()
        settings = MagicMock(spec=SettingsManager)
        settings.kinopoisk_api_key = "test-key"

        result = search_kp_by_imdb("tt9999999", settings, logger)

        assert result == 0
        logger.warning.assert_called()

    def test_no_api_key(self):
        logger = _mock_logger()
        settings = MagicMock(spec=SettingsManager)
        settings.kinopoisk_api_key = ""

        result = search_kp_by_imdb("tt0133093", settings, logger)

        assert result == 0
        logger.error.assert_called()


# ---------------------------------------------------------------------------
# Tests for transliterate_to_cyrillic
# ---------------------------------------------------------------------------

class TestTransliterateToCyrillic:
    def test_brat_ac01(self):
        assert transliterate_to_cyrillic("Brat") == "Брат"

    def test_tihaya_zona_ac02(self):
        assert transliterate_to_cyrillic("Tihaya zona") == "Тихая зона"

    def test_cyrillic_unchanged_ac04(self):
        assert transliterate_to_cyrillic("Брат") == "Брат"

    def test_cyrillic_not_called_ac04(self):
        result = transliterate_to_cyrillic("Матрица")
        assert result == "Матрица"

    def test_digraph_sh(self):
        assert transliterate_to_cyrillic("Shrek") == "Шрек"

    def test_digraph_ch(self):
        assert transliterate_to_cyrillic("Chernobyl") == "Чернобыл"

    def test_digraph_zh(self):
        assert transliterate_to_cyrillic("Zhizn") == "Жизн"

    def test_digraph_shch(self):
        assert transliterate_to_cyrillic("Borshch") == "Борщ"

    def test_digraph_ya(self):
        assert transliterate_to_cyrillic("Yabloko") == "Яблоко"

    def test_digraph_yu(self):
        assert transliterate_to_cyrillic("Yug") == "Юг"

    def test_digraph_ts(self):
        assert transliterate_to_cyrillic("Tsarstvo") == "Царство"

    def test_spaces_preserved(self):
        result = transliterate_to_cyrillic("Tihaya zona")
        assert " " in result

    def test_digits_and_punctuation_preserved(self):
        result = transliterate_to_cyrillic("Brat 1997")
        assert "1997" in result
        assert result.startswith("Брат")

    def test_mixed_cyrillic_unchanged(self):
        mixed = "Brat Брат"
        assert transliterate_to_cyrillic(mixed) == mixed

    def test_case_preserved_lowercase(self):
        assert transliterate_to_cyrillic("brat") == "брат"

    def test_case_preserved_uppercase(self):
        assert transliterate_to_cyrillic("BRAT") == "БРАТ"

    def test_greedy_shch_before_sh(self):
        assert transliterate_to_cyrillic("shchi") == "щи"

    def test_ironia_sudby_ac05(self):
        result = transliterate_to_cyrillic("Ironia sudby")
        assert result == "Ирониа судбы"


# ---------------------------------------------------------------------------
# Tests for _has_cyrillic
# ---------------------------------------------------------------------------

class TestHasCyrillic:
    def test_cyrillic_text_returns_true(self):
        assert _has_cyrillic("Матрица") is True

    def test_latin_text_returns_false(self):
        assert _has_cyrillic("The Matrix") is False

    def test_mixed_text_returns_true(self):
        assert _has_cyrillic("The Матрица") is True

    def test_empty_string_returns_false(self):
        assert _has_cyrillic("") is False

    def test_yo_letter(self):
        assert _has_cyrillic("Ёлка") is True


# ---------------------------------------------------------------------------
# Tests for extract_alt_title
# ---------------------------------------------------------------------------

class TestExtractAltTitle:
    def test_latin_query_returns_title_ru(self):
        result = MovieSearchResult(
            title_ru="Матрица", title_original="The Matrix", kinopoisk_id=301
        )
        alt = extract_alt_title(result, "The Matrix", _mock_logger())
        assert alt == "Матрица"

    def test_cyrillic_query_returns_title_original(self):
        result = MovieSearchResult(
            title_ru="Побег из Шоушенка",
            title_original="The Shawshank Redemption",
            kinopoisk_id=326
        )
        alt = extract_alt_title(result, "Побег из Шоушенка", _mock_logger())
        assert alt == "The Shawshank Redemption"

    def test_empty_alt_title_returns_empty(self):
        result = MovieSearchResult(
            title_ru="", title_original="The Matrix", kinopoisk_id=301
        )
        alt = extract_alt_title(result, "The Matrix", _mock_logger())
        assert alt == ""

    def test_none_alt_title_returns_empty(self):
        result = MovieSearchResult(
            title_ru="Матрица", title_original="The Matrix", kinopoisk_id=301
        )
        # Force title_ru to None to test the `or ""` branch
        result.title_ru = None
        alt = extract_alt_title(result, "The Matrix", _mock_logger())
        assert alt == ""

    def test_same_title_case_insensitive_returns_empty(self):
        result = MovieSearchResult(
            title_ru="avatar", title_original="Avatar", kinopoisk_id=100
        )
        alt = extract_alt_title(result, "Avatar", _mock_logger())
        assert alt == ""

    def test_same_script_latin_returns_empty(self):
        result = MovieSearchResult(
            title_ru="The Matrix", title_original="Matrix", kinopoisk_id=301
        )
        alt = extract_alt_title(result, "Matrix", _mock_logger())
        assert alt == ""

    def test_same_script_cyrillic_returns_empty(self):
        result = MovieSearchResult(
            title_ru="Матрица",
            title_original="Матрица: Перезагрузка",
            kinopoisk_id=301
        )
        alt = extract_alt_title(result, "Матрица", _mock_logger())
        assert alt == ""

    def test_whitespace_alt_title_returns_empty(self):
        result = MovieSearchResult(
            title_ru="  ", title_original="The Matrix", kinopoisk_id=301
        )
        alt = extract_alt_title(result, "The Matrix", _mock_logger())
        assert alt == ""

    def test_strips_whitespace_from_alt_title(self):
        result = MovieSearchResult(
            title_ru=" Матрица ", title_original="The Matrix", kinopoisk_id=301
        )
        alt = extract_alt_title(result, "The Matrix", _mock_logger())
        assert alt == "Матрица"


# ---------------------------------------------------------------------------
# Tests for deduplicate_results
# ---------------------------------------------------------------------------

class TestDeduplicateResults:
    def test_no_duplicates(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=301)]
        secondary = [MovieSearchResult(title_ru="B", kinopoisk_id=302)]
        merged = deduplicate_results(primary, secondary, None, _mock_logger())
        assert len(merged) == 2

    def test_removes_duplicate_from_secondary(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=301)]
        secondary = [MovieSearchResult(title_ru="A", kinopoisk_id=301)]
        merged = deduplicate_results(primary, secondary, None, _mock_logger())
        assert len(merged) == 1

    def test_zero_kinopoisk_id_not_deduplicated(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=0)]
        secondary = [MovieSearchResult(title_ru="B", kinopoisk_id=0)]
        merged = deduplicate_results(primary, secondary, None, _mock_logger())
        assert len(merged) == 2

    def test_empty_primary_returns_secondary(self):
        secondary = [MovieSearchResult(title_ru="A", kinopoisk_id=301)]
        merged = deduplicate_results([], secondary, None, _mock_logger())
        assert len(merged) == 1
        assert merged[0].kinopoisk_id == 301

    def test_empty_secondary_returns_primary(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=301)]
        merged = deduplicate_results(primary, [], None, _mock_logger())
        assert len(merged) == 1
        assert merged[0].kinopoisk_id == 301

    def test_both_empty_returns_empty(self):
        merged = deduplicate_results([], [], None, _mock_logger())
        assert len(merged) == 0

    def test_sort_year_match_first(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=1, year=2000)]
        secondary = [MovieSearchResult(title_ru="B", kinopoisk_id=2, year=1999)]
        merged = deduplicate_results(primary, secondary, "1999", _mock_logger())
        assert merged[0].kinopoisk_id == 2

    def test_sort_by_rating_within_group(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=1, year=1999, rating=7.0)]
        secondary = [MovieSearchResult(title_ru="B", kinopoisk_id=2, year=1999, rating=9.0)]
        merged = deduplicate_results(primary, secondary, "1999", _mock_logger())
        assert merged[0].kinopoisk_id == 2

    def test_no_sort_without_year(self):
        primary = [MovieSearchResult(title_ru="A", kinopoisk_id=1)]
        secondary = [MovieSearchResult(title_ru="B", kinopoisk_id=2)]
        merged = deduplicate_results(primary, secondary, None, _mock_logger())
        assert merged[0].kinopoisk_id == 1


# ---------------------------------------------------------------------------
# Tests for parse_award_tags (BL-10)
# ---------------------------------------------------------------------------

class TestParseAwardTags:
    def test_won_oscar(self):
        result = parse_award_tags("Won 4 Oscars. Another 37 wins & 51 nominations.")
        assert result == ["Оскар"]

    def test_nominated_oscar(self):
        result = parse_award_tags("Nominated for 7 Oscars. Another 37 wins & 185 nominations.")
        assert result == ["Номинант Оскара"]

    def test_won_golden_globe(self):
        result = parse_award_tags("Won 1 Golden Globe. 3 wins & 10 nominations.")
        assert result == ["Золотой глобус"]

    def test_nominated_golden_globe(self):
        result = parse_award_tags("Nominated for 3 Golden Globes. 5 wins & 20 nominations.")
        assert result == ["Номинант Золотого глобуса"]

    def test_won_emmy(self):
        result = parse_award_tags("Won 1 Primetime Emmy. 12 wins & 60 nominations.")
        assert result == ["Эмми"]

    def test_nominated_emmy(self):
        result = parse_award_tags("Nominated for 5 Primetime Emmys. 10 wins & 30 nominations.")
        assert result == ["Номинант Эмми"]

    def test_nominated_bafta(self):
        result = parse_award_tags("Nominated for 3 BAFTA Film Awards. 5 wins.")
        assert result == ["Номинант BAFTA"]

    def test_won_cannes(self):
        result = parse_award_tags("Won Palme d'Or. 5 wins & 3 nominations.")
        assert result == ["Канны"]

    def test_multiple_awards(self):
        result = parse_award_tags("Won 4 Oscars. Won 2 Golden Globes. 100 wins.")
        assert result == ["Оскар", "Золотой глобус"]

    def test_mixed_won_and_nominated(self):
        result = parse_award_tags("Won 4 Oscars. Nominated for 3 Golden Globes. Another 100 wins.")
        assert result == ["Оскар", "Номинант Золотого глобуса"]

    def test_na_returns_empty(self):
        result = parse_award_tags("N/A")
        assert result == []

    def test_empty_string_returns_empty(self):
        result = parse_award_tags("")
        assert result == []

    def test_no_prestigious_awards(self):
        result = parse_award_tags("2 wins & 5 nominations total.")
        assert result == []

    def test_case_insensitive(self):
        result = parse_award_tags("Won 4 OSCARS. Another 37 wins.")
        assert result == ["Оскар"]


# ---------------------------------------------------------------------------
# Tests for normalize_genres (BL-11)
# ---------------------------------------------------------------------------

class TestNormalizeGenres:
    def setup_method(self):
        self.logger = MagicMock()

    def test_en_basic_mapping(self):
        result = normalize_genres(["Боевик", "Драма"], "en", self.logger)
        assert result == ["Action", "Drama"]

    def test_ru_returns_as_is(self):
        result = normalize_genres(["Боевик", "Драма"], "ru", self.logger)
        assert result == ["Боевик", "Драма"]

    def test_en_unknown_genre_fallback(self):
        result = normalize_genres(["Нуар"], "en", self.logger)
        assert result == ["Нуар"]
        self.logger.warning.assert_called()

    def test_en_empty_list(self):
        result = normalize_genres([], "en", self.logger)
        assert result == []

    def test_en_compound_film_noir(self):
        result = normalize_genres(["Фильм-нуар"], "en", self.logger)
        assert result == ["Film-Noir"]

    def test_en_compound_reality_tv(self):
        result = normalize_genres(["Реальное тв"], "en", self.logger)
        assert result == ["Reality-TV"]

    def test_en_compound_talk_show(self):
        result = normalize_genres(["Ток-шоу"], "en", self.logger)
        assert result == ["Talk-Show"]

    def test_en_all_genres_mapped(self):
        for ru, en in _GENRE_RU_TO_EN.items():
            result = normalize_genres([ru.capitalize()], "en", self.logger)
            assert result == [en], f"Failed for '{ru}' -> expected '{en}', got {result}"


# ---------------------------------------------------------------------------
# Tests for clean_title: season/episode pattern removal (BL-15)
# ---------------------------------------------------------------------------

class TestCleanTitleSeasonEpisode:
    """BL-15: Season/episode pattern removal from clean_title."""

    def test_s01e02(self):
        logger = _mock_logger()
        candidates, year = clean_title("Breaking.Bad.S01E02.720p.BluRay", logger)
        assert candidates == ["Breaking Bad"]
        assert year == ""

    def test_1x02(self):
        logger = _mock_logger()
        candidates, year = clean_title("Во все тяжкие 1x02 1080p", logger)
        assert candidates == ["Во все тяжкие"]
        assert year == ""

    def test_cyrillic_se(self):
        logger = _mock_logger()
        candidates, year = clean_title("Чернобыль.С01Э03.WEB-DL", logger)
        assert candidates == ["Чернобыль"]
        assert year == ""

    def test_season_seria(self):
        logger = _mock_logger()
        candidates, year = clean_title("Чернобыль 1 сезон 3 серия HDRip", logger)
        assert candidates == ["Чернобыль"]
        assert year == ""

    def test_se_with_year_in_tail(self):
        logger = _mock_logger()
        candidates, year = clean_title("The.Last.of.Us.S01E03.2023.WEB-DL", logger)
        assert candidates == ["The Last of Us"]
        assert year == "2023"

    def test_se_no_year(self):
        logger = _mock_logger()
        candidates, year = clean_title("Game.of.Thrones.S08E06.1080p", logger)
        assert candidates == ["Game of Thrones"]
        assert year == ""

    def test_year_in_parens_no_se(self):
        logger = _mock_logger()
        candidates, year = clean_title("Сериал (2020)", logger)
        assert candidates == ["Сериал"]
        assert year == "2020"

    def test_numeric_title_with_se(self):
        logger = _mock_logger()
        candidates, year = clean_title("1883 S01E05", logger)
        assert candidates == ["1883"]
        assert year == ""

    def test_multi_episode(self):
        logger = _mock_logger()
        candidates, year = clean_title("Show.S01E02E03.720p", logger)
        assert candidates == ["Show"]
        assert year == ""

    def test_case_insensitive(self):
        logger = _mock_logger()
        candidates, year = clean_title("show.s01e02.720p", logger)
        assert candidates == ["show"]
        assert year == ""


# ---------------------------------------------------------------------------
# Tests for clean_title: absolute episode number removal for anime (BL-16)
# ---------------------------------------------------------------------------

class TestCleanTitleAnimeAbsolute:
    """BL-16: Absolute episode number removal for anime."""

    def test_leading_zero_3digits(self):
        logger = _mock_logger()
        candidates, year = clean_title("Naruto Shippuden - 001 [720p]", logger)
        assert candidates == ["Naruto Shippuden"]
        assert year == ""

    def test_cyrillic_leading_zero(self):
        logger = _mock_logger()
        candidates, year = clean_title("[SubGroup] Наруто 042 (1080p)", logger)
        assert candidates == ["Наруто"]
        assert year == ""

    def test_leading_zero_4digits(self):
        logger = _mock_logger()
        candidates, year = clean_title("One.Piece.0842.720p", logger)
        assert candidates == ["One Piece"]
        assert year == ""

    def test_no_leading_zero_is_year(self):
        logger = _mock_logger()
        candidates, year = clean_title("Наруто 2002", logger)
        assert candidates == ["Наруто"]
        assert year == "2002"

    def test_1080p_not_year(self):
        logger = _mock_logger()
        candidates, year = clean_title("[SubGroup] Наруто 042 (1080p)", logger)
        assert year != "1080"


# ---------------------------------------------------------------------------
# Tests for clean_title: multi-part film detection (BL-17)
# ---------------------------------------------------------------------------

class TestCleanTitleMultiPart:
    """BL-17: Multi-part film detection in clean_title."""

    def test_chast_arabic(self):
        logger = _mock_logger()
        candidates, year = clean_title("Убить Билла Часть 2 (2004)", logger)
        assert "Убить Билла Часть 2" in candidates
        assert "Убить Билла" in candidates
        assert year == "2004"

    def test_vol_english(self):
        logger = _mock_logger()
        candidates, year = clean_title("Kill Bill Vol 2 (2004)", logger)
        assert "Kill Bill Vol 2" in candidates
        assert "Kill Bill" in candidates
        assert year == "2004"

    def test_part_roman(self):
        logger = _mock_logger()
        candidates, year = clean_title("The Godfather Part II (1974)", logger)
        assert "The Godfather Part II" in candidates
        assert "The Godfather" in candidates
        assert year == "1974"

    def test_chast_word_colon(self):
        logger = _mock_logger()
        candidates, year = clean_title("Дюна: Часть вторая (2024)", logger)
        assert "Дюна" in candidates
        assert year == "2024"

    def test_no_multi_part(self):
        logger = _mock_logger()
        candidates, year = clean_title("Аватар (2009)", logger)
        assert candidates == ["Аватар"]
        assert year == "2009"

    def test_volume_full(self):
        logger = _mock_logger()
        candidates, year = clean_title("Harry Potter Volume 3 (2004)", logger)
        assert len(candidates) == 2
