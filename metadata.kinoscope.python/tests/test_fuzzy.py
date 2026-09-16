from __future__ import annotations

from unittest.mock import patch
from difflib import SequenceMatcher

from utils import normalize_for_matching, fuzzy_score, best_fuzzy_score, SIMILARITY_THRESHOLD


class TestNormalizeForMatching:
    def test_lowercase(self):
        assert normalize_for_matching("Interstellar") == "interstellar"

    def test_hyphens_to_spaces(self):
        assert normalize_for_matching("Человек-паук") == "человек паук"

    def test_multiple_spaces(self):
        assert normalize_for_matching("The  Dark   Knight") == "the dark knight"

    def test_leading_trailing_spaces(self):
        assert normalize_for_matching("  hello  ") == "hello"

    def test_combined_normalization(self):
        assert normalize_for_matching("The  Dark-Knight  ") == "the dark knight"

    def test_empty_string(self):
        assert normalize_for_matching("") == ""

    def test_none_input(self):
        assert normalize_for_matching(None) == ""


class TestFuzzyScore:
    def test_exact_match(self):
        assert fuzzy_score("Interstellar", "Interstellar") == 1.0

    def test_case_insensitive(self):
        assert fuzzy_score("interstellar", "Interstellar") == 1.0

    def test_typo_interstellar(self):
        assert fuzzy_score("Interstllar", "Interstellar") >= 0.8

    def test_typo_brigada(self):
        assert fuzzy_score("Бригата", "Бригада") >= 0.8

    def test_empty_candidate(self):
        assert fuzzy_score("query", "") == 0.0

    def test_none_candidate(self):
        assert fuzzy_score("query", None) == 0.0

    def test_empty_query(self):
        assert fuzzy_score("", "candidate") == 0.0

    def test_both_empty(self):
        assert fuzzy_score("", "") == 0.0

    def test_hyphen_normalization(self):
        assert fuzzy_score("Человек-паук", "Человек паук") == 1.0

    def test_uses_sequence_matcher(self):
        with patch("utils.SequenceMatcher", wraps=SequenceMatcher) as mock_sm:
            fuzzy_score("hello", "hello")
            mock_sm.assert_called_once()

    def test_completely_different(self):
        assert fuzzy_score("xyzabc", "Interstellar") < 0.3


class TestBestFuzzyScore:
    def test_max_of_three_fields(self):
        score = best_fuzzy_score("Interstllar", ["Интерстеллар", "Interstellar", "Interstellar"])
        assert score == fuzzy_score("Interstllar", "Interstellar")

    def test_empty_candidates_list(self):
        assert best_fuzzy_score("query", []) == 0.0

    def test_all_none_candidates(self):
        assert best_fuzzy_score("query", [None, None]) == 0.0

    def test_mixed_none_and_valid(self):
        score = best_fuzzy_score("Interstellar", [None, "", "Interstellar"])
        assert score == 1.0

    def test_empty_query(self):
        assert best_fuzzy_score("", ["candidate"]) == 0.0


class TestSimilarityThreshold:
    def test_threshold_value(self):
        assert SIMILARITY_THRESHOLD == 0.6

    def test_threshold_is_float(self):
        assert isinstance(SIMILARITY_THRESHOLD, float)
