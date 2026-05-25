from models import (
    ProfessionType, ArtworkType, DataSource,
    Rating, Person, Artwork, MovieSearchResult, MovieDetails,
    ContentType, Episode, Season, TVShowSearchResult, TVShowDetails
)


class TestEnums:
    def test_profession_type_values(self):
        assert ProfessionType.ACTOR.value == "ACTOR"
        assert ProfessionType.DIRECTOR.value == "DIRECTOR"
        assert ProfessionType.UNKNOWN.value == "UNKNOWN"

    def test_artwork_type_values(self):
        assert ArtworkType.POSTER.value == "poster"
        assert ArtworkType.FANART.value == "fanart"

    def test_data_source_values(self):
        assert DataSource.KINOPOISK.value == "kinopoisk"
        assert DataSource.IMDB.value == "imdb"


class TestRating:
    def test_create_rating(self):
        r = Rating(source=DataSource.KINOPOISK, value=8.5, votes=10000)
        assert r.source == DataSource.KINOPOISK
        assert r.value == 8.5
        assert r.votes == 10000

    def test_default_votes(self):
        r = Rating(source=DataSource.IMDB, value=7.0)
        assert r.votes == 0


class TestPerson:
    def test_create_person(self):
        p = Person(name_ru="Киану Ривз", name_en="Keanu Reeves", role="Neo")
        assert p.name_ru == "Киану Ривз"
        assert p.role == "Neo"
        assert p.profession == ProfessionType.UNKNOWN
        assert p.order == 0

    def test_defaults(self):
        p = Person(name_ru="Тест")
        assert p.name_en == ""
        assert p.photo_url == ""
        assert p.source_id == 0


class TestMovieDetails:
    def test_defaults(self):
        d = MovieDetails()
        assert d.kinopoisk_id == 0
        assert d.genres == []
        assert d.ratings == []
        assert d.cast == []
        assert d.artwork == []

    def test_filled(self):
        d = MovieDetails(
            kinopoisk_id=301,
            title_ru="Матрица",
            year=1999,
            genres=["Фантастика", "Боевик"],
            ratings=[Rating(DataSource.KINOPOISK, 8.5, 10000)],
        )
        assert d.kinopoisk_id == 301
        assert len(d.genres) == 2
        assert d.ratings[0].value == 8.5


class TestMovieSearchResult:
    def test_create(self):
        r = MovieSearchResult(title_ru="Матрица", kinopoisk_id=301, year=1999)
        assert r.title_ru == "Матрица"
        assert r.source == DataSource.KINOPOISK
        assert r.rating == 0.0


class TestContentType:
    def test_all_values_exist(self):
        assert ContentType.FILM.value == "FILM"
        assert ContentType.TV_SERIES.value == "TV_SERIES"
        assert ContentType.MINI_SERIES.value == "MINI_SERIES"
        assert ContentType.TV_SHOW.value == "TV_SHOW"
        assert ContentType.VIDEO.value == "VIDEO"
        assert ContentType.UNKNOWN.value == "UNKNOWN"

    def test_string_representation(self):
        assert "FILM" in str(ContentType.FILM)
        assert "TV_SERIES" in str(ContentType.TV_SERIES)

    def test_member_count(self):
        assert len(ContentType) == 6


class TestEpisode:
    def test_create_with_defaults(self):
        ep = Episode()
        assert ep.season_number == 0
        assert ep.episode_number == 0
        assert ep.title_ru == ""
        assert ep.title_en == ""
        assert ep.synopsis == ""
        assert ep.release_date == ""

    def test_create_with_all_fields(self):
        ep = Episode(
            season_number=1,
            episode_number=5,
            title_ru="Пилот",
            title_en="Pilot",
            synopsis="Первая серия",
            release_date="2008-01-20",
        )
        assert ep.season_number == 1
        assert ep.episode_number == 5
        assert ep.title_ru == "Пилот"
        assert ep.title_en == "Pilot"
        assert ep.synopsis == "Первая серия"
        assert ep.release_date == "2008-01-20"


class TestSeason:
    def test_create_with_defaults(self):
        s = Season()
        assert s.number == 0
        assert s.episodes == []

    def test_create_with_number(self):
        s = Season(number=3)
        assert s.number == 3

    def test_adding_episodes(self):
        s = Season(number=1)
        ep1 = Episode(season_number=1, episode_number=1, title_ru="Первая")
        ep2 = Episode(season_number=1, episode_number=2, title_ru="Вторая")
        s.episodes.append(ep1)
        s.episodes.append(ep2)
        assert len(s.episodes) == 2
        assert s.episodes[0].title_ru == "Первая"
        assert s.episodes[1].title_ru == "Вторая"

    def test_episodes_do_not_share_across_instances(self):
        s1 = Season(number=1)
        s2 = Season(number=2)
        s1.episodes.append(Episode(season_number=1, episode_number=1))
        assert len(s2.episodes) == 0


class TestTVShowSearchResult:
    def test_create_with_required_title(self):
        r = TVShowSearchResult(title_ru="Во все тяжкие")
        assert r.title_ru == "Во все тяжкие"
        assert r.title_original == ""
        assert r.year == 0
        assert r.kinopoisk_id == 0
        assert r.imdb_id == ""
        assert r.poster_url == ""
        assert r.rating == 0.0
        assert r.source == DataSource.KINOPOISK

    def test_default_content_type_is_tv_series(self):
        r = TVShowSearchResult(title_ru="Тест")
        assert r.content_type == ContentType.TV_SERIES

    def test_create_with_all_fields(self):
        r = TVShowSearchResult(
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            year=2008,
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            poster_url="https://poster.jpg",
            rating=9.1,
            content_type=ContentType.MINI_SERIES,
            source=DataSource.IMDB,
        )
        assert r.title_ru == "Во все тяжкие"
        assert r.title_original == "Breaking Bad"
        assert r.year == 2008
        assert r.kinopoisk_id == 462682
        assert r.imdb_id == "tt0903747"
        assert r.content_type == ContentType.MINI_SERIES
        assert r.source == DataSource.IMDB


class TestTVShowDetails:
    def test_defaults(self):
        d = TVShowDetails()
        assert d.kinopoisk_id == 0
        assert d.imdb_id == ""
        assert d.title_ru == ""
        assert d.title_original == ""
        assert d.tagline == ""
        assert d.year == 0
        assert d.plot == ""
        assert d.runtime == 0
        assert d.mpaa == ""
        assert d.genres == []
        assert d.countries == []
        assert d.studios == []
        assert d.ratings == []
        assert d.directors == []
        assert d.writers == []
        assert d.cast == []
        assert d.artwork == []

    def test_filled(self):
        d = TVShowDetails(
            kinopoisk_id=462682,
            imdb_id="tt0903747",
            title_ru="Во все тяжкие",
            title_original="Breaking Bad",
            tagline="All hail the king",
            year=2008,
            plot="Школьный учитель химии",
            runtime=47,
            mpaa="TV-MA",
            genres=["Драма", "Триллер"],
            countries=["США"],
            studios=["AMC"],
            ratings=[Rating(DataSource.KINOPOISK, 9.1, 500000)],
            directors=[Person(name_ru="Винс Гиллиган")],
            writers=[Person(name_ru="Питер Гулд")],
            cast=[Person(name_ru="Брайан Крэнстон", role="Walter White")],
            artwork=[Artwork(url="https://poster.jpg", artwork_type=ArtworkType.POSTER)],
        )
        assert d.kinopoisk_id == 462682
        assert d.imdb_id == "tt0903747"
        assert d.title_ru == "Во все тяжкие"
        assert d.title_original == "Breaking Bad"
        assert d.year == 2008
        assert d.runtime == 47
        assert len(d.genres) == 2
        assert len(d.ratings) == 1
        assert d.ratings[0].value == 9.1
        assert len(d.directors) == 1
        assert len(d.cast) == 1
        assert d.cast[0].role == "Walter White"
        assert len(d.artwork) == 1

    def test_lists_do_not_share_across_instances(self):
        d1 = TVShowDetails()
        d2 = TVShowDetails()
        d1.genres.append("Драма")
        assert d2.genres == []
