[![CI](https://github.com/afr13nd77/kodi_metadata_scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/afr13nd77/kodi_metadata_scraper/actions/workflows/ci.yml)

[Русская версия](README.md)

# Ultimate Movie Scraper (UMS) for Kodi

**Version:** 3.17.1 / 3.17.2 (movie / TV) | **Platform:** Kodi v20 Nexus / v21 Omega | **Language:** Python 3.8 | **License:** MIT

UMS is a metadata scraper for Kodi that fetches rich movie and TV show information from Kinopoisk, OMDb, and TVMaze. It is designed for users who prefer Russian-language metadata while also supporting English titles, international ratings, and full cast and crew data. The project ships as two fully independent addons — install either or both with no cross-dependencies.

---

## Features

### Movie Scraper (`metadata.ums`)

- Search movies by Russian and English title
- Full metadata: title, year, plot, genres, countries, studios, duration, MPAA rating
- Cast and crew with Russian names and photos
- Ratings from Kinopoisk, IMDB, Rotten Tomatoes, and Metacritic (via Kodi rating DB and optionally appended to plot)
- NFO file support (read and write/export)
- Posters and fanart
- Fuzzy matching with 3-level sorting (year, match score, rating)
- Dual search: Russian + original title
- Movie collections and franchises (sets)
- Award tags (Oscar, Emmy, BAFTA, Cannes, Golden Globe)
- Genre normalization (Russian to English)
- Persistent file cache with 7-day TTL
- Auto-select on exact title + year match
- Latin to Cyrillic transliteration fallback
- Duplicate Kinopoisk ID detection with toast notification
- Graceful degradation: offline operation via stale cache and NFO file fallback
- YouTube trailers from Kinopoisk API with caching and graceful degradation
- Wikidata fallback: automatic IMDB ID resolution via Wikidata SPARQL when Kinopoisk doesn't have it (no API key needed)

### TV Show Scraper (`metadata.tvshows.ums`)

- Search TV series (types: TV_SERIES, MINI_SERIES, TV_SHOW)
- Full series metadata with episode guide
- Season and episode information
- Episode descriptions from TVMaze (optional, English, may require VPN)
- Auto-resolve IMDB ID via TVMaze when missing from Kinopoisk
- Per-episode IMDB ratings
- Series ratings from Kinopoisk, IMDB, Rotten Tomatoes, and Metacritic
- Artwork: posters, stills
- NFO file support (read and write/export)
- Smart filename parsing (S01E02, 1x02, Cyrillic patterns)
- Anime detection (absolute numbering)
- Mini-series support
- Multi-part movie handling (Part/Vol)
- Award tags, genre normalization, persistent cache
- Legacy episodeguide fallback
- Duplicate Kinopoisk ID detection
- Graceful degradation: offline operation via stale cache and NFO file fallback
- YouTube trailers from Kinopoisk API
- Wikidata fallback for IMDB ID (same as movie scraper)
- TMDb/TVDB compatibility: auto-resolve KP ID when migrating from another scraper

### Shared

- Addons are fully independent — install only what you need
- Each addon has its own settings (API keys, options)
- cp1251 encoding support for Cyrillic on Windows
- Rate limiting (token bucket) and retry logic with exponential backoff
- API key sanitization in logs
- CI/CD: GitHub Actions (ruff lint + pytest + build ZIP + auto-release on tag `v*`)

---

## Data Sources

| Source | Purpose | Status |
|---|---|---|
| Kinopoisk Unofficial API (`kinopoiskapiunofficial.tech`) | Metadata, cast, posters, seasons, episodes | Primary, required |
| OMDb API (`omdbapi.com`) | IMDB, Rotten Tomatoes, Metacritic ratings | Supplementary, optional |
| TVMaze API (`api.tvmaze.com`) | Episode descriptions, IMDB ID resolution (TV only) | Supplementary, optional |
| Wikidata SPARQL (`query.wikidata.org`) | IMDB ID fallback via Kinopoisk ID | Supplementary, no API key |

TMDb is **not** used.

---

## Installation

### Requirements

- Kodi v20 Nexus or v21 Omega

### Steps

1. Download the ZIP archives from the [Releases](https://github.com/afr13nd77/kodi_metadata_scraper/releases) section.
2. In Kodi, go to **Settings > Add-ons > Install from zip file**.
3. Install the desired addon(s):
   - `metadata.ums-3.17.1.zip` — movie scraper
   - `metadata.tvshows.ums-3.17.2.zip` — TV show scraper
4. Open addon settings and enter your Kinopoisk API key.

### API Keys

- **Kinopoisk Unofficial API** (required): Register at [kinopoiskapiunofficial.tech](https://kinopoiskapiunofficial.tech) for a free key.
- **OMDb API** (optional): Register at [omdbapi.com](https://www.omdbapi.com) for IMDB, Rotten Tomatoes, and Metacritic ratings.

---

## Settings

Each addon (movie and TV) has its own independent settings panel.

| Setting | Description |
|---|---|
| `kinopoisk_api_key` | API key from kinopoiskapiunofficial.tech (required) |
| `omdb_api_key` | OMDb API key for IMDB/RT ratings (optional) |
| `preferred_rating` | Default rating source: Kinopoisk or IMDB |
| `fetch_actor_photos` | Fetch actor photos from Kinopoisk |
| `show_ratings_in_plot` | Append ratings to the plot text |
| `use_tvmaze` | Fetch episode descriptions from TVMaze (TV scraper only, off by default) |
| `genre_language` | Genre language: Russian or English (default: Russian) |
| `auto_select_exact_match` | Auto-select when title + year match exactly |
| `enable_nfo_export` | Write .nfo files next to video files after scraping (off by default) |
| `overwrite_nfo` | Overwrite existing .nfo files (visible only when export is enabled) |
| `enable_duplicate_detection` | Warn when the same Kinopoisk ID is assigned to different files (on by default) |
| `enable_trailers` | Fetch YouTube trailers from Kinopoisk (on by default) |
| `use_wikidata_fallback` | Resolve IMDB ID from Wikidata when Kinopoisk doesn't have it (on by default) |
| `debug_logging` | Enable verbose logging |

---

## Project Structure

```
shared/                  -- shared modules (copied into each addon at build time)
metadata.ums/            -- movie scraper addon
metadata.tvshows.ums/    -- TV show scraper addon
build_zip.py             -- builds both ZIP packages
docs/                    -- feature specifications (requirements, design, tasks)
```

Shared modules include: HTTP client with retry logic, Kinopoisk API client, OMDb client, TVMaze client, Wikidata SPARQL client, NFO parser, NFO writer/exporter, settings manager, logging system, data models (dataclasses), persistent file cache, and duplicate tracker.

---

## Development

### Environment Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install pytest
```

### Running Tests

686 tests total (548 movie + 138 TV).

```bash
# Movie scraper tests (548 tests)
cd metadata.ums && python -m pytest tests/ -v

# TV scraper tests (138 tests)
cd metadata.tvshows.ums && python -m pytest tests/ -v
```

### Linting

```bash
ruff check .
```

### Building ZIP Packages

```
python build_zip.py
```

Output: `metadata.ums-3.17.0.zip` and `metadata.tvshows.ums-3.17.0.zip` in the project root.

---

## License

This project is licensed under the MIT License.
