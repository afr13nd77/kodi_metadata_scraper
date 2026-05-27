from __future__ import annotations

from models import (
    MovieSearchResult, MovieDetails, Person, Artwork, Rating,
    ProfessionType, ArtworkType, DataSource, Season, Episode
)
from http_client import HttpClient, RateLimiter, HttpError
from logger import Logger
from typing import Optional


_PROFESSION_MAP: dict[str, ProfessionType] = {
    "ACTOR": ProfessionType.ACTOR,
    "DIRECTOR": ProfessionType.DIRECTOR,
    "WRITER": ProfessionType.WRITER,
    "PRODUCER": ProfessionType.PRODUCER,
    "COMPOSER": ProfessionType.COMPOSER,
    "OPERATOR": ProfessionType.OPERATOR,
    "EDITOR": ProfessionType.EDITOR,
    "DESIGN": ProfessionType.DESIGN,
}

_IMAGE_TYPE_MAP: dict[str, ArtworkType] = {
    "POSTER": ArtworkType.POSTER,
    "STILL": ArtworkType.FANART,
    "FAN_ART": ArtworkType.FANART,
    "SCREENSHOT": ArtworkType.FANART,
}

_AGE_LIMIT_TO_MPAA: dict[str, str] = {
    "age0": "G",
    "age6": "G",
    "age12": "PG-13",
    "age16": "R",
    "age18": "NC-17",
}

_GENRE_RU_TO_EN: dict[str, str] = {
    "боевик": "Action",
    "приключения": "Adventure",
    "мультфильм": "Animation",
    "биография": "Biography",
    "комедия": "Comedy",
    "криминал": "Crime",
    "документальный": "Documentary",
    "драма": "Drama",
    "семейный": "Family",
    "фэнтези": "Fantasy",
    "фильм-нуар": "Film-Noir",
    "история": "History",
    "ужасы": "Horror",
    "музыка": "Music",
    "мюзикл": "Musical",
    "детектив": "Mystery",
    "новости": "News",
    "реальное тв": "Reality-TV",
    "мелодрама": "Romance",
    "фантастика": "Sci-Fi",
    "короткометражка": "Short",
    "спорт": "Sport",
    "триллер": "Thriller",
    "военный": "War",
    "вестерн": "Western",
    "аниме": "Anime",
    "для взрослых": "Adult",
    "церемония": "Ceremony",
    "концерт": "Concert",
    "ток-шоу": "Talk-Show",
    "игра": "Game-Show",
}


def normalize_genres(genres_ru: list[str], language: str, logger) -> list[str]:
    if language != "en":
        logger.debug(f"normalize_genres: language='{language}', returning as-is: {genres_ru}")
        return genres_ru

    result = []
    unmapped = []
    for genre in genres_ru:
        key = genre.lower()
        mapped = _GENRE_RU_TO_EN.get(key)
        if mapped:
            result.append(mapped)
        else:
            unmapped.append(genre)
            result.append(genre)

    logger.info(
        f"normalize_genres: input={genres_ru}, output={result}"
        + (f", unmapped={unmapped}" if unmapped else "")
    )

    if unmapped:
        logger.warning(f"normalize_genres: unmapped genres: {unmapped}")

    return result


_kp_global_limiter = RateLimiter(18.0)
_kp_staff_limiter = RateLimiter(9.0)


class KinopoiskClient:
    BASE_URL = "https://kinopoiskapiunofficial.tech/api"

    def __init__(self, api_key: str, logger: Logger):
        self._logger = logger
        self._api_key = api_key

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self._http = HttpClient(
            base_url=self.BASE_URL,
            headers=headers,
            rate_limiter=_kp_global_limiter,
            logger=logger,
        )
        self._http_staff = HttpClient(
            base_url=self.BASE_URL,
            headers=headers,
            rate_limiter=_kp_staff_limiter,
            logger=logger,
        )

    def search(
        self, title: str, year: Optional[str] = None, type_filter: Optional[list[str]] = None,
    ) -> list[MovieSearchResult]:
        from utils import best_fuzzy_score, SIMILARITY_THRESHOLD

        self._logger.info(f"KinopoiskClient.search: title='{title}', year={year}, type_filter={type_filter}")

        try:
            params = {"keyword": title, "page": "1"}
            data = self._http.get_json("v2.1/films/search-by-keyword", params)
        except HttpError as e:
            self._logger.error(f"KinopoiskClient.search failed: {e}")
            return []

        films = data.get("films", [])
        results: list[MovieSearchResult] = []
        fuzzy_scores: list[float] = []
        filtered_count = 0

        for film in films:
            film_type = film.get("type", "UNKNOWN")
            if type_filter and film_type not in type_filter:
                filtered_count += 1
                continue

            film_year = self._safe_int(str(film.get("year", "")))

            result = MovieSearchResult(
                title_ru=film.get("nameRu", "") or film.get("nameEn", ""),
                title_original=film.get("nameEn", "") or film.get("nameOriginal", ""),
                year=film_year,
                kinopoisk_id=self._safe_int(film.get("filmId", 0)),
                poster_url=film.get("posterUrl", ""),
                rating=self._safe_float(film.get("rating", 0)),
                source=DataSource.KINOPOISK,
            )
            results.append(result)

            name_ru = film.get("nameRu", "") or ""
            name_en = film.get("nameEn", "") or ""
            name_original = film.get("nameOriginal", "") or ""
            score = best_fuzzy_score(title, [name_ru, name_en, name_original])
            fuzzy_scores.append(score)

            self._logger.debug(
                f"KinopoiskClient.search: fuzzy '{title}' vs "
                f"'{name_ru}'/'{name_en}'/'{name_original}' "
                f"-> score={score:.3f}"
            )

        if type_filter and filtered_count > 0:
            self._logger.info(
                f"KinopoiskClient.search: filtered {filtered_count} results "
                f"by type_filter={type_filter}"
            )

        target_year = self._safe_int(year) if year else None

        def _sort_key(idx_result: tuple[int, MovieSearchResult]) -> tuple:
            idx, r = idx_result
            year_match = 0 if (target_year is not None and r.year == target_year) else 1
            return (year_match, -fuzzy_scores[idx], -r.rating)

        indexed = list(enumerate(results))
        indexed.sort(key=_sort_key)
        results = [r for _, r in indexed]
        sorted_scores = [fuzzy_scores[i] for i, _ in indexed]

        if results and all(s < SIMILARITY_THRESHOLD for s in sorted_scores):
            self._logger.warning(
                f"KinopoiskClient.search: all {len(results)} results "
                f"below similarity threshold ({SIMILARITY_THRESHOLD}) "
                f"for query '{title}'"
            )

        self._logger.info(f"KinopoiskClient.search: found {len(results)} results for '{title}'")
        return results

    # ------------------------------------------------------------------
    # details: fetch_raw + parse + backward-compatible wrapper
    # ------------------------------------------------------------------

    def fetch_details_raw(self, kinopoisk_id: int) -> Optional[dict]:
        """HTTP request for film details, returns raw dict."""
        self._logger.info(f"KinopoiskClient.fetch_details_raw: kp_id={kinopoisk_id}")
        try:
            data = self._http.get_json(f"v2.2/films/{kinopoisk_id}")
        except HttpError as e:
            self._logger.error(f"KinopoiskClient.fetch_details_raw failed: {e}")
            return None
        self._logger.info(f"KinopoiskClient.fetch_details_raw: success for kp_id={kinopoisk_id}")
        return data

    def parse_details(self, data: dict, genre_language: str = "ru") -> MovieDetails:
        """Parse raw dict into MovieDetails."""
        mpaa = (data.get("ratingMpaa", "") or "").upper()
        if not mpaa:
            age_limit = (data.get("ratingAgeLimits", "") or "").lower()
            mapped = _AGE_LIMIT_TO_MPAA.get(age_limit, "")
            if mapped:
                self._logger.info(
                    f"KinopoiskClient.parse_details: ratingMpaa empty, "
                    f"mapped ratingAgeLimits='{age_limit}' -> mpaa='{mapped}'"
                )
                mpaa = mapped

        details = MovieDetails(
            kinopoisk_id=self._safe_int(data.get("kinopoiskId", 0)),
            imdb_id=data.get("imdbId", "") or "",
            title_ru=data.get("nameRu", "") or data.get("nameOriginal", ""),
            title_original=data.get("nameOriginal", "") or data.get("nameEn", ""),
            year=self._safe_int(data.get("year", 0)),
            plot=data.get("description", "") or "",
            tagline=self._clean_tagline(data.get("slogan", "") or ""),
            runtime=self._safe_int(data.get("filmLength", 0)),
            mpaa=mpaa,
            genres=normalize_genres(
                [g["genre"].capitalize() for g in data.get("genres", []) if g.get("genre")],
                genre_language,
                self._logger,
            ),
            countries=[c["country"] for c in data.get("countries", []) if c.get("country")],
        )

        kp_rating = self._safe_float(data.get("ratingKinopoisk", 0))
        kp_votes = self._safe_int(data.get("ratingKinopoiskVoteCount", 0))
        if kp_rating > 0:
            details.ratings.append(Rating(DataSource.KINOPOISK, kp_rating, kp_votes))

        imdb_rating = self._safe_float(data.get("ratingImdb", 0))
        imdb_votes = self._safe_int(data.get("ratingImdbVoteCount", 0))
        if imdb_rating > 0:
            details.ratings.append(Rating(DataSource.IMDB, imdb_rating, imdb_votes))

        poster_url = data.get("posterUrl", "")
        if poster_url:
            details.artwork.append(Artwork(
                url=poster_url,
                preview_url=data.get("posterUrlPreview", "") or "",
                artwork_type=ArtworkType.POSTER,
                source=DataSource.KINOPOISK,
            ))

        self._logger.info(
            f"KinopoiskClient.parse_details: parsed kp_id={details.kinopoisk_id}, "
            f"title='{details.title_ru}', "
            f"{len(details.ratings)} ratings, {len(details.artwork)} artwork"
        )
        return details

    def get_details(self, kinopoisk_id: int, genre_language: str = "ru") -> Optional[MovieDetails]:
        """Backward compatible: fetch + parse."""
        data = self.fetch_details_raw(kinopoisk_id)
        if data is None:
            return None
        return self.parse_details(data, genre_language)

    # ------------------------------------------------------------------
    # staff: fetch_raw + parse + backward-compatible wrapper
    # ------------------------------------------------------------------

    def fetch_staff_raw(self, kinopoisk_id: int) -> Optional[list]:
        """HTTP request for film staff, returns raw list."""
        self._logger.info(f"KinopoiskClient.fetch_staff_raw: kp_id={kinopoisk_id}")
        try:
            data = self._http_staff.get_json("v1/staff", {"filmId": str(kinopoisk_id)})
        except HttpError as e:
            self._logger.error(f"KinopoiskClient.fetch_staff_raw failed: {e}")
            return None
        self._logger.info(f"KinopoiskClient.fetch_staff_raw: success for kp_id={kinopoisk_id}")
        return data

    def parse_staff(self, data: list) -> tuple[list[Person], list[Person], list[Person]]:
        """Parse raw list into (directors, writers, cast)."""
        directors: list[Person] = []
        writers: list[Person] = []
        cast: list[Person] = []

        for idx, staff in enumerate(data if isinstance(data, list) else []):
            profession_key = staff.get("professionKey", "")
            profession = _PROFESSION_MAP.get(profession_key, ProfessionType.UNKNOWN)

            person = Person(
                name_ru=staff.get("nameRu", "") or staff.get("nameEn", ""),
                name_en=staff.get("nameEn", "") or "",
                role=staff.get("description", "") or "",
                profession=profession,
                photo_url=staff.get("posterUrl", "") or "",
                source_id=self._safe_int(staff.get("staffId", 0)),
            )

            if profession == ProfessionType.DIRECTOR:
                person.order = len(directors)
                directors.append(person)
            elif profession == ProfessionType.WRITER:
                person.order = len(writers)
                writers.append(person)
            elif profession == ProfessionType.ACTOR:
                person.order = len(cast)
                cast.append(person)

        self._logger.info(
            f"KinopoiskClient.parse_staff: {len(directors)} directors, "
            f"{len(writers)} writers, {len(cast)} actors"
        )
        return directors, writers, cast

    def get_staff(self, kinopoisk_id: int) -> tuple[list[Person], list[Person], list[Person]]:
        """Backward compatible: fetch + parse."""
        data = self.fetch_staff_raw(kinopoisk_id)
        if data is None:
            return [], [], []
        return self.parse_staff(data)

    # ------------------------------------------------------------------
    # images: fetch_raw + parse + backward-compatible wrapper
    # ------------------------------------------------------------------

    def fetch_images_raw(self, kinopoisk_id: int, image_types: list[str] | None = None) -> list[dict]:
        """HTTP requests for each image_type, returns combined raw list of items."""
        if image_types is None:
            image_types = ["POSTER", "STILL"]

        self._logger.info(
            f"KinopoiskClient.fetch_images_raw: kp_id={kinopoisk_id}, types={image_types}"
        )

        items: list[dict] = []
        for img_type in image_types:
            try:
                data = self._http.get_json(
                    f"v2.2/films/{kinopoisk_id}/images",
                    {"type": img_type, "page": "1"}
                )
            except HttpError as e:
                self._logger.warning(
                    f"KinopoiskClient.fetch_images_raw: failed for type={img_type}: {e}"
                )
                continue

            for item in data.get("items", []):
                item["_type"] = img_type
                items.append(item)

        self._logger.info(
            f"KinopoiskClient.fetch_images_raw: fetched {len(items)} raw items "
            f"for kp_id={kinopoisk_id}"
        )
        return items

    def parse_images(self, items: list[dict]) -> list[Artwork]:
        """Parse raw items into list[Artwork]."""
        artworks: list[Artwork] = []
        for item in items:
            img_type = item.get("_type", "")
            artwork_type = _IMAGE_TYPE_MAP.get(img_type, ArtworkType.FANART)
            image_url = item.get("imageUrl", "")
            if image_url:
                artworks.append(Artwork(
                    url=image_url,
                    preview_url=item.get("previewUrl", "") or "",
                    artwork_type=artwork_type,
                    source=DataSource.KINOPOISK,
                ))

        self._logger.info(f"KinopoiskClient.parse_images: parsed {len(artworks)} artworks")
        return artworks

    def get_images(self, kinopoisk_id: int, image_types: list[str] | None = None) -> list[Artwork]:
        """Backward compatible: fetch + parse."""
        items = self.fetch_images_raw(kinopoisk_id, image_types)
        return self.parse_images(items)

    # ------------------------------------------------------------------
    # sequels: fetch_raw + backward-compatible wrapper (no parse needed)
    # ------------------------------------------------------------------

    def fetch_sequels_raw(self, kinopoisk_id: int) -> Optional[list]:
        """HTTP request for sequels/prequels, returns raw list."""
        self._logger.info(f"KinopoiskClient.fetch_sequels_raw: kp_id={kinopoisk_id}")

        try:
            data = self._http.get_json(f"v2.1/films/{kinopoisk_id}/sequels_and_prequels")
        except HttpError as e:
            if e.status_code == 404:
                self._logger.info(
                    f"KinopoiskClient.fetch_sequels_raw: kp_id={kinopoisk_id} is standalone (404)"
                )
                return []
            else:
                self._logger.error(f"KinopoiskClient.fetch_sequels_raw failed: {e}")
                return None

        if not isinstance(data, list):
            self._logger.warning(
                f"KinopoiskClient.fetch_sequels_raw: unexpected response type "
                f"for kp_id={kinopoisk_id}"
            )
            return []

        self._logger.info(
            f"KinopoiskClient.fetch_sequels_raw: found {len(data)} related films "
            f"for kp_id={kinopoisk_id}"
        )
        return data

    def get_sequels(self, kinopoisk_id: int) -> list[dict]:
        """Backward compatible: fetch raw."""
        data = self.fetch_sequels_raw(kinopoisk_id)
        return data if data is not None else []

    # ------------------------------------------------------------------
    # seasons: fetch_raw + parse + backward-compatible wrapper
    # ------------------------------------------------------------------

    def fetch_seasons_raw(self, kinopoisk_id: int) -> Optional[dict]:
        """HTTP request for TV seasons, returns raw dict."""
        self._logger.info(f"KinopoiskClient.fetch_seasons_raw: kp_id={kinopoisk_id}")
        try:
            data = self._http.get_json(f"v2.2/films/{kinopoisk_id}/seasons")
        except HttpError as e:
            self._logger.error(f"KinopoiskClient.fetch_seasons_raw failed: {e}")
            return None
        self._logger.info(f"KinopoiskClient.fetch_seasons_raw: success for kp_id={kinopoisk_id}")
        return data

    def parse_seasons(self, data: dict) -> list[Season]:
        """Parse raw dict into list[Season]."""
        items = data.get("items", [])
        if not items:
            self._logger.warning(
                "KinopoiskClient.parse_seasons: data contains 0 seasons"
            )
            return []

        seasons: list[Season] = []
        for item in items:
            season = Season(number=self._safe_int(item.get("number", 0)))
            for ep_data in item.get("episodes", []):
                episode = Episode(
                    season_number=self._safe_int(ep_data.get("seasonNumber", 0)),
                    episode_number=self._safe_int(ep_data.get("episodeNumber", 0)),
                    title_ru=(ep_data.get("nameRu", "") or ep_data.get("nameEn", "") or ""),
                    title_en=(ep_data.get("nameEn", "") or ""),
                    synopsis=(ep_data.get("synopsis", "") or ""),
                    release_date=(ep_data.get("releaseDate", "") or ""),
                )
                season.episodes.append(episode)
            seasons.append(season)

        total_episodes = sum(len(s.episodes) for s in seasons)
        self._logger.info(
            f"KinopoiskClient.parse_seasons: {len(seasons)} seasons, "
            f"{total_episodes} episodes"
        )
        return seasons

    def get_seasons(self, kinopoisk_id: int) -> list[Season]:
        """Backward compatible: fetch + parse."""
        data = self.fetch_seasons_raw(kinopoisk_id)
        if data is None:
            return []
        return self.parse_seasons(data)

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_float(value) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _clean_tagline(tagline: str) -> str:
        return tagline.strip("\"'«»“”")
