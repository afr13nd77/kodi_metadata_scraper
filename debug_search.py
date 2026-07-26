from __future__ import annotations

"""Standalone debug script for testing the UMS search pipeline outside Kodi.

Usage:
    python debug_search.py YOUR_API_KEY "Braveheart 1995"
    python debug_search.py YOUR_API_KEY "Матрица"

Requires only Python 3.8+ stdlib. Mocks xbmc/xbmcaddon so that shared/
modules can be imported without a running Kodi instance.
"""

import json
import os
import sys
import types

# ---------------------------------------------------------------------------
# 1. Mock xbmc and xbmcaddon BEFORE any shared/ imports
# ---------------------------------------------------------------------------

xbmc_mock = types.ModuleType("xbmc")
xbmc_mock.LOGDEBUG = 0
xbmc_mock.LOGINFO = 1
xbmc_mock.LOGWARNING = 2
xbmc_mock.LOGERROR = 3
xbmc_mock.LOGFATAL = 4
xbmc_mock.log = lambda msg, level=0: None  # silent by default
sys.modules["xbmc"] = xbmc_mock

xbmcaddon_mock = types.ModuleType("xbmcaddon")


class _MockAddon:
    def getAddonInfo(self, key):
        return "debug.script"

    def getSetting(self, key):
        return ""

    def getSettingBool(self, key):
        return False

    def getSettingInt(self, key):
        return 0

    def setSettingBool(self, key, value):
        pass


xbmcaddon_mock.Addon = _MockAddon
sys.modules["xbmcaddon"] = xbmcaddon_mock

# ---------------------------------------------------------------------------
# 2. Add shared/ to sys.path so we can import project modules
# ---------------------------------------------------------------------------

_script_dir = os.path.dirname(os.path.abspath(__file__))
_shared_dir = os.path.join(_script_dir, "shared")
if _shared_dir not in sys.path:
    sys.path.insert(0, _shared_dir)

# ---------------------------------------------------------------------------
# 3. Import project modules (after mocks are in place)
# ---------------------------------------------------------------------------

from utils import clean_title, best_fuzzy_score, SIMILARITY_THRESHOLD  # noqa: E402
from http_client import HttpClient  # noqa: E402
from logger import Logger  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text, max_len=30):
    # type: (str, int) -> str
    """Truncate string to max_len, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _safe_float(value):
    """Convert value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _format_rating(value):
    """Format a rating value for display."""
    rating = _safe_float(value)
    if rating > 0:
        return "{:.1f}".format(rating)
    return "-"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 3:
        print("Usage: python debug_search.py API_KEY \"raw title\"")
        print("Example: python debug_search.py abc123 \"Braveheart 1995\"")
        sys.exit(1)

    api_key = sys.argv[1]
    raw_title = sys.argv[2]

    # Create logger (debug enabled so we see internal pipeline messages)
    logger = Logger(debug_enabled=True)

    # --- Phase 1: clean_title ---
    candidates, year = clean_title(raw_title, logger)
    keyword = candidates[0] if candidates else raw_title

    print("")
    print("=== clean_title pipeline ===")
    print("Input:      \"{}\"".format(raw_title))
    print("Candidates: {}".format(candidates))
    print("Year:       \"{}\"".format(year))
    print("Keyword:    \"{}\"".format(keyword))

    # --- Phase 2: Direct API call via HttpClient ---
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    http = HttpClient(
        base_url="https://kinopoiskapiunofficial.tech/api",
        headers=headers,
        logger=logger,
    )

    try:
        data = http.get_json(
            "v2.1/films/search-by-keyword",
            {"keyword": keyword, "page": "1"},
        )
    except Exception as exc:
        print("")
        print("ERROR: API request failed: {}".format(exc))
        print("")
        print("Possible causes:")
        print("  - Invalid API key")
        print("  - Network connectivity issue")
        print("  - API rate limit exceeded")
        sys.exit(1)

    films = data.get("films", [])

    # --- Phase 3: Build table ---
    print("")
    print("=== API Response ({} results) ===".format(len(films)))

    # Table header
    hdr_fmt = "{:<3}| {:<9}| {:<32}| {:<32}| {:<6}| {:<12}| {:<8}| {}"
    sep_fmt = "{}-+-{}-+-{}-+-{}-+-{}-+-{}-+-{}-+-{}"

    print(hdr_fmt.format(
        "#", "KP ID", "nameRu", "nameEn", "Year", "Type", "Rating", "Fuzzy",
    ))
    print(sep_fmt.format(
        "---", "---------", "--------------------------------",
        "--------------------------------", "------", "------------",
        "--------", "------",
    ))

    row_fmt = "{:<3}| {:<9}| {:<32}| {:<32}| {:<6}| {:<12}| {:<8}| {}"

    total_film_type = 0
    total_fuzzy_pass = 0

    for idx, film in enumerate(films, start=1):
        name_ru = film.get("nameRu", "") or ""
        name_en = film.get("nameEn", "") or ""
        name_original = film.get("nameOriginal", "") or ""
        film_type = film.get("type", "UNKNOWN") or "UNKNOWN"
        film_year = str(film.get("year", "")) or ""
        film_id = film.get("filmId", "") or ""
        rating_raw = film.get("rating", "")

        # Compute fuzzy score against keyword
        score = best_fuzzy_score(keyword, [name_ru, name_en, name_original])

        # Check filters
        is_film_type = film_type == "FILM"
        fuzzy_pass = score >= SIMILARITY_THRESHOLD

        # Year match check (for checkmark)
        if year:
            year_match = (film_year == year)
        else:
            year_match = True

        mark = ""
        if fuzzy_pass and year_match:
            mark = " OK"

        if is_film_type:
            total_film_type += 1
        if fuzzy_pass:
            total_fuzzy_pass += 1

        print(row_fmt.format(
            idx,
            film_id,
            _truncate(name_ru),
            _truncate(name_en or name_original),
            film_year,
            film_type,
            _format_rating(rating_raw),
            "{:.3f}{}".format(score, mark),
        ))

    # --- Phase 4: Summary ---
    print("")
    print("=== Summary ===")
    print("Total: {}, Passed filter (FILM): {}, Fuzzy >= {}: {}".format(
        len(films), total_film_type, SIMILARITY_THRESHOLD, total_fuzzy_pass,
    ))


if __name__ == "__main__":
    main()
