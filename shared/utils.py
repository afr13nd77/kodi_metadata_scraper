from __future__ import annotations

import sys
import json
import re
from difflib import SequenceMatcher
import urllib.parse
from typing import NamedTuple
import xbmc

from logger import Logger, _resolve_addon_id
from models import MovieSearchResult, MovieDetails, DataSource
from settings_manager import SettingsManager
from kinopoisk_api import KinopoiskClient


class ManualIdInput(NamedTuple):
    id_type: str
    id_value: str


def get_params() -> dict:
    params = {"handle": int(sys.argv[1])}
    if len(sys.argv) > 2 and sys.argv[2]:
        raw = sys.argv[2].lstrip("?")
        xbmc.log(
            f"[{_resolve_addon_id()}] get_params: raw argv2 repr={repr(raw)}",
            xbmc.LOGDEBUG,
        )
        # Parse with latin-1 to get raw percent-decoded bytes as-is.
        # This avoids the default UTF-8 decoding which fails on cp1251
        # percent-encoded values from Kodi on Russian Windows.
        parsed = urllib.parse.parse_qsl(raw, keep_blank_values=True, encoding='latin-1')
        for key, value in parsed:
            params[key] = _decode_value(value)
    return params


def _decode_value(value: str) -> str:
    """Decode a value that was parsed with latin-1 encoding.

    Kodi on Windows percent-encodes Cyrillic titles using the system
    codepage (cp1251), NOT UTF-8.  ``parse_qsl`` with
    ``encoding='latin-1'`` preserves the raw bytes as single-byte
    characters.  This function tries to detect the actual encoding and
    decode properly.

    Order of attempts:
    1. Pure ASCII -- return as-is (no decoding needed).
    2. UTF-8 -- in case some values *are* UTF-8 encoded.
    3. cp1251 -- confirmed encoding on Russian Windows.
    4. Fallback -- return the value unchanged.
    """
    # Fast path: pure ASCII -- nothing to decode
    try:
        value.encode('ascii')
        return value
    except UnicodeEncodeError:
        pass

    # Get the raw bytes (latin-1 is a transparent 1:1 mapping)
    raw_bytes = value.encode('latin-1')

    # Try UTF-8 first (correct encoding on Linux / modern systems)
    try:
        decoded = raw_bytes.decode('utf-8')
        xbmc.log(
            f"[{_resolve_addon_id()}] _decode_value: decoded as UTF-8",
            xbmc.LOGDEBUG,
        )
        return decoded
    except UnicodeDecodeError:
        pass

    # Try cp1251 (confirmed: Kodi on Russian Windows uses this)
    try:
        decoded = raw_bytes.decode('cp1251')
        xbmc.log(
            f"[{_resolve_addon_id()}] _decode_value: decoded as cp1251",
            xbmc.LOGDEBUG,
        )
        return decoded
    except UnicodeDecodeError:
        pass

    # Nothing worked -- return as-is
    xbmc.log(
        f"[{_resolve_addon_id()}] _decode_value: unable to decode value",
        xbmc.LOGWARNING,
    )
    return value


_TRANSLIT_TABLE = [
    ("shch", "щ"), ("sch", "щ"),
    ("zh", "ж"), ("ch", "ч"), ("sh", "ш"), ("ts", "ц"),
    ("ya", "я"), ("yu", "ю"), ("yo", "ё"), ("ye", "е"),
    ("a", "а"), ("b", "б"), ("v", "в"), ("g", "г"), ("d", "д"),
    ("e", "е"), ("z", "з"), ("i", "и"), ("j", "й"), ("k", "к"),
    ("l", "л"), ("m", "м"), ("n", "н"), ("o", "о"), ("p", "п"),
    ("r", "р"), ("s", "с"), ("t", "т"), ("u", "у"), ("f", "ф"),
    ("h", "х"), ("c", "ц"), ("w", "в"), ("x", "кс"), ("y", "ы"),
]


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r'[а-яёА-ЯЁ]', text))


def transliterate_to_cyrillic(text: str) -> str:
    """Transliterate Latin text to Cyrillic using greedy matching.

    Returns the text unchanged if it already contains Cyrillic characters
    or if no characters could be mapped.
    """
    if _has_cyrillic(text):
        return text

    text_lower = text.lower()
    result = []
    i = 0
    while i < len(text_lower):
        matched = False
        for lat, cyr in _TRANSLIT_TABLE:
            if text_lower[i:i + len(lat)] == lat:
                out = cyr.capitalize() if text[i].isupper() else cyr
                result.append(out)
                i += len(lat)
                matched = True
                break
        if not matched:
            result.append(text[i])
            i += 1
    return "".join(result)


SIMILARITY_THRESHOLD: float = 0.6

_SEASON_EPISODE_PATTERNS = [
    # SxxExx (S01E02, S1E3, S01E02E03) — case insensitive
    re.compile(r'\bS\d{1,2}E\d{1,3}(?:E\d{1,3})*\b', re.IGNORECASE),
    # Кириллический СxxЭxx (С01Э03)
    re.compile(r'\bС\d{1,2}Э\d{1,3}\b', re.IGNORECASE),
    # NxNN (1x02, 12x05)
    re.compile(r'(?<![a-zA-Zа-яА-ЯёЁ0-9])\d{1,2}x\d{2,3}\b', re.IGNORECASE),
    # "N сезон N серия" / "N сезон, N серия"
    re.compile(r'\b\d{1,2}\s*сезон\s*,?\s*\d{1,3}\s*(?:серия|серии|серий)\b', re.IGNORECASE),
    # "N сезон" (без серии)
    re.compile(r'\b\d{1,2}\s*сезон\b', re.IGNORECASE),
]

_ABSOLUTE_EPISODE_PATTERN = re.compile(
    r'(?:^|[\s\-])0\d{1,3}(?=[\s\-.,\]\)]|$)'
)

_MULTI_PART_PATTERN = re.compile(
    r'^(?P<base>.+?)\s*[:.]*\s*'
    r'(?:Part|Часть|Vol\.?|Volume|Том)\s+'
    r'(?P<part>\d+|I{1,3}V?|VI{0,3}|IV|'
    r'первая|вторая|третья|четвёртая|пятая|'
    r'первый|второй|третий|четвёртый|пятый)'
    r'\s*$',
    re.IGNORECASE,
)

# BUG-009: Release/encoding tags pattern for truncation.
# Matches the first technical tag (rip, resolution, codec, audio, HDR, marker)
# and everything after it is discarded.
_RELEASE_TAG_PATTERN = re.compile(
    r'\b(?:'
    # Rip tags
    r'BDRip|BRRip|HDRip|WEBRip|WEB-DL|WEBDL|WEB(?:-DL|Rip|DL)|'
    r'DVDRip|DVDScr|CAMRip|HDCAM|HDTV|PDTV|SDTV|'
    r'Blu-?ray|Remux|DVDR|TVRip|SATRip|HDTVRip|'
    # Resolution
    r'480p|576p|720p|1080p|1080i|2160p|4K|UHD|'
    # Codecs
    r'x264|x265|H\.?264|H\.?265|HEVC|AVC|XviD|DivX|AV1|VP9|MPEG-?2|MPEG-?4|'
    # Audio
    r'AAC|AC3|DTS-HD|DTS-X|DTS|DD5\.1|DD2\.0|DD7\.1|Atmos|TrueHD|FLAC|EAC3|LPCM|'
    # Bit depth / HDR
    r'10bit|8bit|HDR10\+?|HDR|DV|DoVi|SDR|'
    # Markers
    r'PROPER|REPACK|EXTENDED|Remastered|Unrated|Uncut|IMAX|Open\.?Matte'
    r')\b',
    re.IGNORECASE,
)

# BUG-009: Russian releaser marker "от <name>"
_RELEASER_PATTERN = re.compile(r'\bот\s+\S+', re.IGNORECASE)

# BUG-010: Release group name after year removal (e.g. "- EniaHD")
_RELEASE_GROUP_PATTERN = re.compile(
    r'(?:\s{2,}-\s+|\s{2,})([A-Za-z0-9]{2,20})\s*$'
)

# BL-71: Collection prefix pattern (e.g., "MCU150-", "SW03-", "DC021-")
_COLLECTION_PREFIX_PATTERN = re.compile(r'^[A-Z]{2,5}\d{1,3}-')

_KP_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?kinopoisk\.ru/(?:film|series)/(\d+)",
    re.IGNORECASE,
)

_IMDB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?imdb\.com/title/(tt\d{7,8})",
    re.IGNORECASE,
)

_KP_PREFIX_PATTERN = re.compile(
    r"^kp:?(\d+)$",
    re.IGNORECASE,
)

_IMDB_PREFIX_PATTERN = re.compile(
    r"^(tt\d{7,8})$",
    re.IGNORECASE,
)


def _strip_season_episode(cleaned: str, extracted_year: str, logger: Logger) -> tuple[str, str]:
    for pattern in _SEASON_EPISODE_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            # Извлечь год из хвоста ПЕРЕД отсечением (для случая "S01E03.2023")
            tail = cleaned[match.end():]
            if not extracted_year:
                year_in_tail = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', tail)
                if year_in_tail:
                    extracted_year = year_in_tail.group(1)
                    logger.info(f"_strip_season_episode: extracted year '{extracted_year}' from tail")
            cleaned = cleaned[:match.start()].strip(' -,')
            logger.info(f"_strip_season_episode: removed '{match.group()}', result='{cleaned}'")
            return cleaned, extracted_year
    return cleaned, extracted_year


def _strip_absolute_episode(cleaned: str, logger: Logger) -> str:
    match = _ABSOLUTE_EPISODE_PATTERN.search(cleaned)
    if match:
        ep_num = match.group().strip(' -')
        cleaned = cleaned[:match.start()].strip(' -,')
        logger.info(f"_strip_absolute_episode: removed '{ep_num}', result='{cleaned}'")
    return cleaned


def normalize_for_matching(text: str) -> str:
    if not text:
        return ""
    result = text.lower()
    result = result.replace("-", " ")
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def fuzzy_score(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0
    norm_query = normalize_for_matching(query)
    norm_candidate = normalize_for_matching(candidate)
    if not norm_query or not norm_candidate:
        return 0.0
    return SequenceMatcher(None, norm_query, norm_candidate).ratio()


def best_fuzzy_score(query: str, candidates: list[str]) -> float:
    if not query or not candidates:
        return 0.0
    scores = [fuzzy_score(query, c) for c in candidates if c]
    return max(scores) if scores else 0.0


def extract_alt_title(result: MovieSearchResult, query: str, logger: Logger) -> str:
    query_is_cyrillic = _has_cyrillic(query)

    if query_is_cyrillic:
        alt_title = result.title_original or ""
    else:
        alt_title = result.title_ru or ""

    if not alt_title or not alt_title.strip():
        logger.info("extract_alt_title: no alt_title available")
        return ""

    alt_title = alt_title.strip()

    if alt_title.lower() == query.lower():
        logger.info(
            f"extract_alt_title: alt_title '{alt_title}' matches query, skipping"
        )
        return ""

    alt_is_cyrillic = _has_cyrillic(alt_title)
    if query_is_cyrillic and alt_is_cyrillic:
        logger.info(
            f"extract_alt_title: alt_title '{alt_title}' same script as query, skipping"
        )
        return ""
    if not query_is_cyrillic and not alt_is_cyrillic:
        logger.info(
            f"extract_alt_title: alt_title '{alt_title}' same script as query, skipping"
        )
        return ""

    logger.info(
        f"extract_alt_title: query='{query}', alt_title='{alt_title}', "
        f"source={'title_original' if query_is_cyrillic else 'title_ru'}"
    )
    return alt_title


def deduplicate_results(
    primary: list[MovieSearchResult],
    secondary: list[MovieSearchResult],
    search_year: str | None,
    logger: Logger,
) -> list[MovieSearchResult]:
    seen_ids: set[int] = set()
    merged: list[MovieSearchResult] = []

    for r in primary:
        if r.kinopoisk_id and r.kinopoisk_id in seen_ids:
            continue
        if r.kinopoisk_id:
            seen_ids.add(r.kinopoisk_id)
        merged.append(r)

    added_from_secondary = 0
    for r in secondary:
        if r.kinopoisk_id and r.kinopoisk_id in seen_ids:
            continue
        if r.kinopoisk_id:
            seen_ids.add(r.kinopoisk_id)
        merged.append(r)
        added_from_secondary += 1

    logger.info(
        f"deduplicate_results: primary={len(primary)}, secondary={len(secondary)}, "
        f"added_new={added_from_secondary}, total={len(merged)}"
    )

    if search_year:
        target_year = int(search_year) if search_year.isdigit() else 0
        merged.sort(
            key=lambda r: (
                0 if r.year == target_year else 1,
                -r.rating,
            )
        )

    return merged


def clean_title(raw_title: str, logger: Logger) -> tuple[list[str], str]:
    # Step 1: Remove bracketed content [...]
    cleaned = re.sub(r'\[.*?\]', '', raw_title)

    # Step 2: Extract year from parentheses (YYYY) if present
    year_match = re.search(r'\((\d{4})\)', cleaned)
    extracted_year = year_match.group(1) if year_match else ""
    cleaned = re.sub(r'\(\d{4}\)', '', cleaned)

    # Step 3: Replace dots and underscores with spaces
    cleaned = re.sub(r'[._]+', ' ', cleaned)

    cleaned = cleaned.strip(' -,')

    # Step 3.0: Remove release/encoding tags (BUG-009)
    release_match = _RELEASE_TAG_PATTERN.search(cleaned)
    if release_match:
        removed = cleaned[release_match.start():]
        cleaned = cleaned[:release_match.start()].strip(' -,')
        logger.info(f"clean_title: removed release tags: '{removed}', result='{cleaned}'")
    # Also strip Russian releaser marker "от <name>"
    releaser_match = _RELEASER_PATTERN.search(cleaned)
    if releaser_match:
        removed_rel = cleaned[releaser_match.start():]
        cleaned = cleaned[:releaser_match.start()].strip(' -,')
        logger.info(f"clean_title: removed releaser marker: '{removed_rel}', result='{cleaned}'")

    # Step 3.0c: Strip release group name "- GroupName" or trailing junk (BUG-010)
    group_match = _RELEASE_GROUP_PATTERN.search(cleaned)
    if group_match:
        removed_group = cleaned[group_match.start():]
        cleaned = cleaned[:group_match.start()].strip(' -,')
        logger.info(f"clean_title: removed release group: '{removed_group}', result='{cleaned}'")

    # Step 3.0d: Strip collection prefix (BL-71)
    if extracted_year:
        prefix_match = _COLLECTION_PREFIX_PATTERN.match(cleaned)
        if prefix_match:
            removed_prefix = prefix_match.group(0)
            cleaned = cleaned[prefix_match.end():].strip()
            logger.info(f"clean_title: removed collection prefix '{removed_prefix}', result='{cleaned}'")

    # Step 3.1: Remove season/episode patterns (BL-15)
    cleaned, extracted_year = _strip_season_episode(cleaned, extracted_year, logger)

    # Step 3.2: Remove absolute episode numbers (BL-16)
    cleaned = _strip_absolute_episode(cleaned, logger)

    # Step 4: If no year yet, look for a bare 4-digit year (19xx/20xx)
    # and truncate everything after it (codec/quality/release junk)
    if not extracted_year:
        bare_year_match = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', cleaned)
        if bare_year_match:
            extracted_year = bare_year_match.group(1)
            # Truncate at the year position (everything after is junk)
            truncated = cleaned[:bare_year_match.start()].strip(' -,')
            if truncated:
                cleaned = truncated
    else:
        # Even with a paren year, try to remove junk after a bare year
        bare_year_match = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', cleaned)
        if bare_year_match:
            truncated = cleaned[:bare_year_match.start()].strip(' -,')
            if truncated:
                cleaned = truncated

    # Step 5: Split on '/' for multiple title candidates
    candidates = []
    if '/' in cleaned:
        parts = [p.strip(' -,') for p in cleaned.split('/')]
        candidates = [p for p in parts if p]
    if not candidates:
        candidates = [cleaned] if cleaned else []

    # Step 5.1: Detect multi-part films (BL-17)
    expanded = []
    for c in candidates:
        mp_match = _MULTI_PART_PATTERN.match(c)
        if mp_match:
            base = mp_match.group('base').strip(' :.,-')
            expanded.append(c)
            if base and base != c:
                expanded.append(base)
            logger.info(f"clean_title: multi-part detected: full='{c}', base='{base}'")
        else:
            expanded.append(c)
    candidates = expanded

    logger.info(f"clean_title: '{raw_title}' -> candidates={candidates}, year={extracted_year}")
    return candidates, extracted_year


_SUSPICIOUS_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
_SUSPICIOUS_RELEASE_RE = re.compile(r'^Release\s*:', re.IGNORECASE)
_SUSPICIOUS_DOMAIN_RE = re.compile(r'\b[\w-]+\.(org|ru|com|net|info|me|to)\b', re.IGNORECASE)
_SUSPICIOUS_WRAPPED_RE = re.compile(r'^[=~\[\]]+\S+[=~\[\]]+$')


def is_title_suspicious(title: str, logger: Logger) -> bool:
    # Возвращает True, если title похож на мусор релизера
    if not title:
        logger.info("is_title_suspicious: empty title -> False")
        return False

    checks = (
        ("email", bool(_SUSPICIOUS_EMAIL_RE.search(title))),
        ("release_prefix", bool(_SUSPICIOUS_RELEASE_RE.search(title))),
        ("domain", bool(_SUSPICIOUS_DOMAIN_RE.search(title))),
        ("wrapped_special", bool(_SUSPICIOUS_WRAPPED_RE.match(title))),
        ("short_upper", len(title) <= 6 and title.isupper() and ' ' not in title),
    )
    for pattern_name, matched in checks:
        if matched:
            logger.info(f"is_title_suspicious: title='{title}' matched pattern: {pattern_name}")
            return True

    logger.info(f"is_title_suspicious: title='{title}' not suspicious")
    return False


_VIDEO_EXTENSIONS = {
    ".mkv", ".avi", ".mp4", ".m4v", ".mov", ".wmv", ".flv",
    ".ts", ".m2ts", ".vob", ".iso", ".img", ".strm",
    ".divx", ".ogm", ".webm", ".3gp",
}


def extract_title_from_path(file_path: str, logger: Logger) -> list[tuple[str, str]]:
    # Не используем os.path: путь может быть Windows, SMB или POSIX независимо от ОС Kodi
    if not file_path:
        logger.info("extract_title_from_path: empty path -> []")
        return []

    try:
        normalized = file_path.replace("\\", "/").rstrip("/")
        parts = normalized.split("/")
        result: list[tuple[str, str]] = []

        filename = parts[-1]
        dot = filename.rfind(".")
        if dot != -1:
            ext = filename[dot:]
            if ext.lower() in _VIDEO_EXTENSIONS:
                filename = filename[:dot]
            elif len(ext) <= 5 and dot >= 2:
                filename = filename[:dot]
        if filename:
            result.append(("filename", filename))

        if len(parts) >= 2 and parts[-2]:
            result.append(("dirname", parts[-2]))

        logger.info(f"extract_title_from_path: '{file_path}' -> {result}")
        return result
    except Exception as e:
        logger.error(f"extract_title_from_path: failed for '{file_path}': {e}")
        return []


def extract_kinopoisk_id(params: dict, logger: Logger) -> int:
    # Try uniqueIDs from Kodi (camelCase)
    uniqueids = params.get("uniqueIDs", {})
    if not uniqueids:
        uniqueids = params.get("uniqueids", {})

    # Parse JSON string if needed
    if isinstance(uniqueids, str):
        try:
            uniqueids = json.loads(uniqueids)
        except (json.JSONDecodeError, TypeError):
            uniqueids = {}

    # Try url param (JSON from find action)
    if not uniqueids:
        url_str = params.get("url", "")
        if url_str:
            try:
                uniqueids = json.loads(url_str)
            except (json.JSONDecodeError, TypeError):
                pass

    # Direct param
    kp_id_str = ""
    if isinstance(uniqueids, dict):
        kp_id_str = uniqueids.get("kinopoisk", "")
    if not kp_id_str:
        kp_id_str = params.get("kinopoisk", "")
    if not kp_id_str:
        id_val = params.get("id", "")
        if id_val and str(id_val).isdigit():
            kp_id_str = str(id_val)

    if kp_id_str:
        try:
            kp_id = int(kp_id_str)
            logger.info(f"extract_kinopoisk_id: found kp_id={kp_id}")
            return kp_id
        except (ValueError, TypeError):
            logger.warning(f"extract_kinopoisk_id: invalid kp_id value: {kp_id_str}")

    return 0


def extract_imdb_id(params: dict, logger: Logger) -> str:
    uniqueids = params.get("uniqueIDs", {})
    if not uniqueids:
        uniqueids = params.get("uniqueids", {})

    if isinstance(uniqueids, str):
        try:
            uniqueids = json.loads(uniqueids)
        except (json.JSONDecodeError, TypeError):
            uniqueids = {}

    if not uniqueids:
        url_str = params.get("url", "")
        if url_str:
            try:
                uniqueids = json.loads(url_str)
            except (json.JSONDecodeError, TypeError):
                pass

    imdb_id = ""
    if isinstance(uniqueids, dict):
        imdb_id = uniqueids.get("imdb", "")
    if not imdb_id:
        imdb_id = params.get("imdb", "")

    if imdb_id:
        logger.info(f"extract_imdb_id: found imdb_id={imdb_id}")

    return imdb_id


def parse_manual_id_input(title: str, logger: Logger) -> ManualIdInput | None:
    cleaned = title.strip()
    if not cleaned:
        return None

    match = _KP_URL_PATTERN.search(cleaned)
    if match:
        kp_id = match.group(1)
        logger.info(f"parse_manual_id_input: detected KP URL, id={kp_id}")
        return ManualIdInput(id_type="kp", id_value=kp_id)

    match = _IMDB_URL_PATTERN.search(cleaned)
    if match:
        imdb_id = match.group(1).lower()
        logger.info(f"parse_manual_id_input: detected IMDB URL, id={imdb_id}")
        return ManualIdInput(id_type="imdb", id_value=imdb_id)

    match = _KP_PREFIX_PATTERN.match(cleaned)
    if match:
        kp_id = match.group(1)
        logger.info(f"parse_manual_id_input: detected KP prefix, id={kp_id}")
        return ManualIdInput(id_type="kp", id_value=kp_id)

    match = _IMDB_PREFIX_PATTERN.match(cleaned)
    if match:
        imdb_id = match.group(1).lower()
        logger.info(f"parse_manual_id_input: detected IMDB prefix, id={imdb_id}")
        return ManualIdInput(id_type="imdb", id_value=imdb_id)

    return None


def _longest_common_prefix(strings: list[str]) -> str:
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while prefix and not s.startswith(prefix):
            prefix = prefix[:-1]
    return prefix


def extract_franchise_name(current_title: str, related_titles: list[str]) -> str:
    all_titles = [current_title] + related_titles
    lcp = _longest_common_prefix(all_titles)
    lcp = lcp.rstrip(" :—-–")
    if len(lcp) >= 2:
        return lcp

    # Fallback: strip " N: subtitle" then ": subtitle" from current title
    base = re.sub(r"\s+\d+(\s*:.*)?$", "", current_title)
    base = re.sub(r"\s*:.*$", "", base)
    return base.strip(" :—-–")


def search_kp_by_imdb(imdb_id: str, settings: SettingsManager, logger: Logger) -> int:
    logger.info(f"search_kp_by_imdb: searching for imdb_id={imdb_id}")

    if not settings.kinopoisk_api_key:
        logger.error("search_kp_by_imdb: no API key")
        return 0

    # Step 1: KP API — direct IMDB→KP resolution
    from kinopoisk_api import get_current_api_key
    kp_client = KinopoiskClient(get_current_api_key() or settings.kinopoisk_api_key, logger)
    kp_id = kp_client.get_kp_id_by_imdb_id(imdb_id)
    if kp_id:
        logger.info(f"search_kp_by_imdb: KP API resolved kp_id={kp_id} for imdb_id={imdb_id}")
        return kp_id

    logger.info(f"search_kp_by_imdb: KP API returned no result for imdb_id={imdb_id}, trying Wikidata fallback")

    # Step 2: Wikidata fallback — SPARQL P345→P2603
    from wikidata_client import WikidataClient
    wikidata = WikidataClient(logger)
    wd_kp_id = wikidata.get_kp_id_by_imdb_id(imdb_id)
    if wd_kp_id and wd_kp_id > 0:
        logger.info(f"search_kp_by_imdb: Wikidata resolved kp_id={wd_kp_id} for imdb_id={imdb_id}")
        return wd_kp_id

    logger.warning(f"search_kp_by_imdb: no results for imdb_id={imdb_id} (KP API + Wikidata both failed)")
    return 0


def details_to_search_result(details: MovieDetails) -> MovieSearchResult:
    # Конвертация MovieDetails в MovieSearchResult (рейтинг KP, превью постера)
    kp_rating = 0.0
    for r in details.ratings:
        if r.source == DataSource.KINOPOISK:
            kp_rating = r.value
            break

    poster_url = ""
    if details.artwork:
        poster_url = details.artwork[0].preview_url or details.artwork[0].url

    return MovieSearchResult(
        title_ru=details.title_ru,
        title_original=details.title_original,
        year=details.year,
        kinopoisk_id=details.kinopoisk_id,
        imdb_id=details.imdb_id,
        poster_url=poster_url,
        rating=kp_rating,
        source=DataSource.KINOPOISK,
    )


def resolve_manual_id(
    manual_id: ManualIdInput,
    kp_client: KinopoiskClient,
    settings: SettingsManager,
    logger: Logger,
    allowed_types: list[str],
) -> list[MovieSearchResult]:
    # Резолв ручного ID (kp/imdb) в список из одного MovieSearchResult
    kp_id: int = 0

    if manual_id.id_type == "kp":
        kp_id = int(manual_id.id_value)
    elif manual_id.id_type == "imdb":
        kp_id = search_kp_by_imdb(manual_id.id_value, settings, logger)
        if not kp_id:
            logger.warning(
                f"resolve_manual_id: IMDB ID '{manual_id.id_value}' "
                f"could not be resolved to KP ID"
            )
            return []

    raw_data = kp_client.fetch_details_raw(kp_id)
    if raw_data is None:
        logger.warning(
            f"resolve_manual_id: fetch_details_raw returned None for kp_id={kp_id}"
        )
        return []

    content_type = raw_data.get("type", "UNKNOWN")
    if content_type not in allowed_types:
        logger.warning(
            f"resolve_manual_id: type mismatch for kp_id={kp_id}: "
            f"got '{content_type}', expected one of {allowed_types}"
        )
        return []

    details = kp_client.parse_details(raw_data)
    if details is None:
        logger.warning(f"resolve_manual_id: parse_details returned None for kp_id={kp_id}")
        return []

    search_result = details_to_search_result(details)
    logger.info(
        f"resolve_manual_id: resolved kp_id={kp_id}, "
        f"title='{search_result.title_ru}' ({search_result.year})"
    )
    return [search_result]
