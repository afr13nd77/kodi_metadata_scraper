from __future__ import annotations

import re
import threading
from typing import Any, Optional

from http_client import HttpClient, HttpError, RateLimiter
from models import SeasonArtInfo


_tvmaze_limiter = RateLimiter(2.0)

_show_cache: dict[str, int] = {}
_episodes_cache: dict[int, list[dict]] = {}
_tvmaze_cache_lock = threading.Lock()
_TVMAZE_CACHE_MAX_SHOWS = 20
_TVMAZE_CACHE_MAX_EPISODES = 10
_seasons_cache: dict[int, list[SeasonArtInfo]] = {}
_TVMAZE_CACHE_MAX_SEASONS = 10


class TvmazeClient:

    BASE_URL = "https://api.tvmaze.com"
    TIMEOUT = 5
    _HTML_TAG_RE = re.compile(r"<[^>]+>")

    def __init__(self, logger: Any = None) -> None:
        self._logger = logger
        self._http = HttpClient(
            base_url=self.BASE_URL,
            headers={"Accept": "application/json"},
            rate_limiter=_tvmaze_limiter,
            timeout=self.TIMEOUT,
            logger=logger,
        )

    def get_episode_plot(
        self,
        imdb_id: str,
        season: int,
        episode: int,
        title_original: str = "",
    ) -> Optional[str]:
        if not imdb_id and not title_original:
            self._log_debug(
                "TvmazeClient.get_episode_plot: no imdb_id or title_original, skipping"
            )
            return None

        self._log_info(
            f"TvmazeClient.get_episode_plot: "
            f"imdb_id={imdb_id}, S{season:02d}E{episode:02d}, "
            f"title_original='{title_original}'"
        )

        # Try IMDB lookup first, then name search as fallback
        show_id = None
        if imdb_id:
            show_id = self.lookup_show(imdb_id)
        if show_id is None and title_original:
            show_id = self.search_show(title_original)
        if show_id is None:
            return None

        episodes = self.get_episodes(show_id)
        if episodes is None:
            return None

        for ep in episodes:
            if ep.get("season") == season and ep.get("number") == episode:
                summary = ep.get("summary") or ""
                plot = self._strip_html(summary)
                if plot:
                    return plot
                self._log_debug(
                    f"TvmazeClient.get_episode_plot: empty summary for "
                    f"imdb_id={imdb_id}, S{season:02d}E{episode:02d}"
                )
                return None

        self._log_debug(
            f"TvmazeClient.get_episode_plot: episode not found for "
            f"imdb_id={imdb_id}, S{season:02d}E{episode:02d}"
        )
        return None

    def lookup_show(self, imdb_id: str) -> Optional[int]:
        with _tvmaze_cache_lock:
            if imdb_id in _show_cache:
                self._log_debug(
                    f"TvmazeClient.lookup_show: cache hit for imdb_id={imdb_id}"
                )
                return _show_cache[imdb_id]

        self._log_info(
            f"TvmazeClient.lookup_show: looking up imdb_id={imdb_id}"
        )

        try:
            data = self._http.get_json("/lookup/shows", {"imdb": imdb_id})
        except HttpError as exc:
            if exc.status_code == 404:
                self._log_debug(
                    f"TvmazeClient.lookup_show: show not found for "
                    f"imdb_id={imdb_id}"
                )
                return None
            self._log_warning(
                f"TvmazeClient.lookup_show: HTTP error for "
                f"imdb_id={imdb_id}: {exc}"
            )
            return None
        except Exception as exc:
            self._log_warning(
                f"TvmazeClient.lookup_show: unexpected error for "
                f"imdb_id={imdb_id}: {exc}"
            )
            return None

        raw_id = data.get("id")
        if not raw_id:
            self._log_warning(
                f"TvmazeClient.lookup_show: no 'id' in response for "
                f"imdb_id={imdb_id}"
            )
            return None
        show_id = int(raw_id)

        with _tvmaze_cache_lock:
            if len(_show_cache) >= _TVMAZE_CACHE_MAX_SHOWS:
                oldest_key = next(iter(_show_cache))
                del _show_cache[oldest_key]
            _show_cache[imdb_id] = show_id

        self._log_info(
            f"TvmazeClient.lookup_show: success imdb_id={imdb_id} -> "
            f"show_id={show_id}"
        )
        return show_id

    def search_show(self, name: str) -> Optional[int]:
        """Find TVMaze show ID by name using singlesearch.

        Fallback when IMDB ID is not available from Kinopoisk.
        API: GET /singlesearch/shows?q={name}
        """
        with _tvmaze_cache_lock:
            if name in _show_cache:
                self._log_debug(
                    f"TvmazeClient.search_show: cache hit for name='{name}'"
                )
                return _show_cache[name]

        self._log_info(
            f"TvmazeClient.search_show: searching for name='{name}'"
        )

        try:
            data = self._http.get_json("/singlesearch/shows", {"q": name})
        except HttpError as exc:
            if exc.status_code == 404:
                self._log_debug(
                    f"TvmazeClient.search_show: show not found for "
                    f"name='{name}'"
                )
                return None
            self._log_warning(
                f"TvmazeClient.search_show: HTTP error for "
                f"name='{name}': {exc}"
            )
            return None
        except Exception as exc:
            self._log_warning(
                f"TvmazeClient.search_show: unexpected error for "
                f"name='{name}': {exc}"
            )
            return None

        raw_id = data.get("id")
        if not raw_id:
            self._log_warning(
                f"TvmazeClient.search_show: no 'id' in response for "
                f"name='{name}'"
            )
            return None
        show_id = int(raw_id)

        with _tvmaze_cache_lock:
            if len(_show_cache) >= _TVMAZE_CACHE_MAX_SHOWS:
                oldest_key = next(iter(_show_cache))
                del _show_cache[oldest_key]
            _show_cache[name] = show_id

        self._log_info(
            f"TvmazeClient.search_show: success name='{name}' -> "
            f"show_id={show_id}"
        )
        return show_id

    def search_imdb_id(self, name: str) -> Optional[str]:
        if not name:
            return None

        self._log_info(
            f"TvmazeClient.search_imdb_id: searching for name='{name}'"
        )

        try:
            data = self._http.get_json("/singlesearch/shows", {"q": name})
        except HttpError as exc:
            if exc.status_code == 404:
                self._log_debug(
                    f"TvmazeClient.search_imdb_id: show not found for "
                    f"name='{name}'"
                )
                return None
            self._log_warning(
                f"TvmazeClient.search_imdb_id: HTTP error for "
                f"name='{name}': {exc}"
            )
            return None
        except Exception as exc:
            self._log_warning(
                f"TvmazeClient.search_imdb_id: unexpected error for "
                f"name='{name}': {exc}"
            )
            return None

        externals = data.get("externals") or {}
        imdb_id = externals.get("imdb") or ""
        if not imdb_id:
            self._log_debug(
                f"TvmazeClient.search_imdb_id: no IMDB ID in response for "
                f"name='{name}'"
            )
            return None

        self._log_info(
            f"TvmazeClient.search_imdb_id: success name='{name}' -> "
            f"imdb_id={imdb_id}"
        )
        return imdb_id

    def get_episodes(self, show_id: int) -> Optional[list[dict]]:
        with _tvmaze_cache_lock:
            if show_id in _episodes_cache:
                self._log_debug(
                    f"TvmazeClient.get_episodes: cache hit for "
                    f"show_id={show_id}"
                )
                return _episodes_cache[show_id]

        self._log_info(
            f"TvmazeClient.get_episodes: fetching episodes for "
            f"show_id={show_id}"
        )

        try:
            data = self._http.get_json(f"/shows/{show_id}/episodes")
        except HttpError as exc:
            self._log_warning(
                f"TvmazeClient.get_episodes: HTTP error for "
                f"show_id={show_id}: {exc}"
            )
            return None
        except Exception as exc:
            self._log_warning(
                f"TvmazeClient.get_episodes: unexpected error for "
                f"show_id={show_id}: {exc}"
            )
            return None

        if not isinstance(data, list):
            self._log_warning(
                f"TvmazeClient.get_episodes: unexpected response type "
                f"for show_id={show_id}: {type(data).__name__}"
            )
            return None

        with _tvmaze_cache_lock:
            if len(_episodes_cache) >= _TVMAZE_CACHE_MAX_EPISODES:
                oldest_key = next(iter(_episodes_cache))
                del _episodes_cache[oldest_key]
            _episodes_cache[show_id] = data

        self._log_info(
            f"TvmazeClient.get_episodes: success for show_id={show_id}, "
            f"{len(data)} episodes"
        )
        return data

    def get_seasons(self, show_id: int) -> Optional[list[SeasonArtInfo]]:
        with _tvmaze_cache_lock:
            if show_id in _seasons_cache:
                self._log_debug(
                    f"TvmazeClient.get_seasons: cache hit for show_id={show_id}"
                )
                return _seasons_cache[show_id]

        self._log_info(
            f"TvmazeClient.get_seasons: fetching seasons for show_id={show_id}"
        )

        try:
            data = self._http.get_json(f"/shows/{show_id}/seasons")
        except HttpError as exc:
            self._log_warning(
                f"TvmazeClient.get_seasons: HTTP error for show_id={show_id}: {exc}"
            )
            return None
        except Exception as exc:
            self._log_warning(
                f"TvmazeClient.get_seasons: unexpected error for show_id={show_id}: {exc}"
            )
            return None

        if not isinstance(data, list):
            self._log_warning(
                f"TvmazeClient.get_seasons: unexpected response type "
                f"for show_id={show_id}: {type(data).__name__}"
            )
            return None

        result: list[SeasonArtInfo] = []
        for item in data:
            num = item.get("number")
            if num is None:
                self._log_warning(
                    f"TvmazeClient.get_seasons: skipping season with "
                    f"number=None in show_id={show_id}"
                )
                continue
            image = item.get("image") or {}
            result.append(SeasonArtInfo(
                number=int(num),
                name=item.get("name") or "",
                poster_url=image.get("original", ""),
                poster_preview_url=image.get("medium", ""),
            ))

        with _tvmaze_cache_lock:
            if len(_seasons_cache) >= _TVMAZE_CACHE_MAX_SEASONS:
                oldest_key = next(iter(_seasons_cache))
                del _seasons_cache[oldest_key]
            _seasons_cache[show_id] = result

        self._log_info(
            f"TvmazeClient.get_seasons: success for show_id={show_id}, "
            f"{len(result)} seasons"
        )
        return result

    def _strip_html(self, html: str) -> str:
        if not html:
            return ""
        text = self._HTML_TAG_RE.sub("", html)
        text = " ".join(text.split())
        return text

    def _log_debug(self, message: str) -> None:
        if self._logger is not None:
            self._logger.debug(message)

    def _log_info(self, message: str) -> None:
        if self._logger is not None:
            self._logger.info(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None:
            self._logger.warning(message)
