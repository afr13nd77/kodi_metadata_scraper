from unittest.mock import MagicMock
from nfo_parser import NfoParser
from logger import Logger
from models import (
    ArtworkType,
    DataSource,
    MovieDetails,
    Person,
    Rating,
    Artwork,
    TVShowDetails,
)


def _make_parser():
    logger = MagicMock(spec=Logger)
    return NfoParser(logger)


class TestNfoParser:
    def test_kinopoisk_url(self):
        parser = _make_parser()
        result = parser.parse("https://www.kinopoisk.ru/film/301/")
        assert result.kinopoisk_id == 301

    def test_kinopoisk_uniqueid(self):
        parser = _make_parser()
        result = parser.parse('<uniqueid type="kinopoisk">301</uniqueid>')
        assert result.kinopoisk_id == 301

    def test_imdb_url(self):
        parser = _make_parser()
        result = parser.parse("some text tt0133093 more text")
        assert result.imdb_id == "tt0133093"

    def test_imdb_uniqueid(self):
        parser = _make_parser()
        result = parser.parse('<uniqueid type="imdb">tt0133093</uniqueid>')
        assert result.imdb_id == "tt0133093"

    def test_mixed_kp_and_imdb(self):
        nfo = """
        <movie>
            <uniqueid type="kinopoisk">301</uniqueid>
            <uniqueid type="imdb">tt0133093</uniqueid>
        </movie>
        """
        parser = _make_parser()
        result = parser.parse(nfo)
        assert result.kinopoisk_id == 301
        assert result.imdb_id == "tt0133093"

    def test_empty_nfo(self):
        parser = _make_parser()
        result = parser.parse("")
        assert result.kinopoisk_id == 0
        assert result.imdb_id == ""

    def test_garbage_content(self):
        parser = _make_parser()
        result = parser.parse("random garbage text with no IDs")
        assert result.kinopoisk_id == 0
        assert result.imdb_id == ""

    def test_kp_url_priority_over_uniqueid(self):
        nfo = """
        https://www.kinopoisk.ru/film/555/
        <uniqueid type="kinopoisk">301</uniqueid>
        """
        parser = _make_parser()
        result = parser.parse(nfo)
        assert result.kinopoisk_id == 555


class TestNfoParserSeriesUrls:
    """Tests for /series/ URL support in NfoParser."""

    def test_series_url_extracts_kp_id(self):
        """URL with /series/ path should extract kp_id correctly."""
        parser = _make_parser()
        result = parser.parse("https://www.kinopoisk.ru/series/252185/")
        assert result.kinopoisk_id == 252185

    def test_film_url_still_works(self):
        """URL with /film/ path should still work (regression test)."""
        parser = _make_parser()
        result = parser.parse("https://www.kinopoisk.ru/film/252185/")
        assert result.kinopoisk_id == 252185

    def test_series_url_https_with_www(self):
        """HTTPS + www variant for /series/ URLs."""
        parser = _make_parser()
        result = parser.parse("https://www.kinopoisk.ru/series/462682/")
        assert result.kinopoisk_id == 462682

    def test_series_url_https_without_www(self):
        """HTTPS without www for /series/ URLs."""
        parser = _make_parser()
        result = parser.parse("https://kinopoisk.ru/series/462682/")
        assert result.kinopoisk_id == 462682

    def test_series_url_http_variant(self):
        """HTTP (non-SSL) variant for /series/ URLs."""
        parser = _make_parser()
        result = parser.parse("http://www.kinopoisk.ru/series/462682/")
        assert result.kinopoisk_id == 462682

    def test_series_url_without_trailing_slash(self):
        """Series URL without trailing slash."""
        parser = _make_parser()
        result = parser.parse("https://www.kinopoisk.ru/series/462682")
        assert result.kinopoisk_id == 462682

    def test_series_url_priority_over_uniqueid(self):
        """Series URL should take priority over uniqueid (same as film URL)."""
        nfo = """
        https://www.kinopoisk.ru/series/462682/
        <uniqueid type="kinopoisk">999</uniqueid>
        """
        parser = _make_parser()
        result = parser.parse(nfo)
        assert result.kinopoisk_id == 462682

    def test_series_url_embedded_in_nfo_xml(self):
        """Series URL embedded within NFO XML content."""
        nfo = """
        <tvshow>
            <title>Breaking Bad</title>
            https://www.kinopoisk.ru/series/462682/
            <uniqueid type="imdb">tt0903747</uniqueid>
        </tvshow>
        """
        parser = _make_parser()
        result = parser.parse(nfo)
        assert result.kinopoisk_id == 462682
        assert result.imdb_id == "tt0903747"


class TestParseFullMovie:
    """Tests for NfoParser.parse_full_movie()."""

    def test_parse_full_movie_complete(self):
        """NFO XML with ALL fields populated. Assert all MovieDetails fields."""
        nfo = """<movie>
            <title>Матрица</title>
            <originaltitle>The Matrix</originaltitle>
            <year>1999</year>
            <plot>Хакер Нео узнаёт правду о мире.</plot>
            <tagline>Добро пожаловать в реальный мир</tagline>
            <runtime>136</runtime>
            <mpaa>R</mpaa>
            <uniqueid type="kinopoisk" default="true">301</uniqueid>
            <uniqueid type="imdb">tt0133093</uniqueid>
            <ratings>
                <rating name="kinopoisk" max="10" default="true">
                    <value>8.5</value>
                    <votes>850000</votes>
                </rating>
                <rating name="imdb" max="10">
                    <value>8.7</value>
                    <votes>1900000</votes>
                </rating>
            </ratings>
            <genre>фантастика</genre>
            <genre>боевик</genre>
            <country>США</country>
            <country>Австралия</country>
            <studio>Warner Bros.</studio>
            <tag>neo</tag>
            <tag>cyberpunk</tag>
            <director>Лана Вачовски</director>
            <director>Лилли Вачовски</director>
            <credits>Лана Вачовски</credits>
            <actor>
                <name>Киану Ривз</name>
                <role>Нео</role>
                <thumb>https://example.com/keanu.jpg</thumb>
                <order>0</order>
            </actor>
            <actor>
                <name>Лоренс Фишбёрн</name>
                <role>Морфеус</role>
                <thumb>https://example.com/laurence.jpg</thumb>
                <order>1</order>
            </actor>
            <thumb aspect="poster">https://example.com/poster.jpg</thumb>
            <thumb aspect="fanart">https://example.com/fanart.jpg</thumb>
            <set>
                <name>Матрица</name>
            </set>
        </movie>"""

        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert details.title_ru == "Матрица"
        assert details.title_original == "The Matrix"
        assert details.year == 1999
        assert details.plot == "Хакер Нео узнаёт правду о мире."
        assert details.tagline == "Добро пожаловать в реальный мир"
        assert details.runtime == 136
        assert details.mpaa == "R"
        assert details.kinopoisk_id == 301
        assert details.imdb_id == "tt0133093"

        assert len(details.ratings) == 2
        assert details.ratings[0].source == DataSource.KINOPOISK
        assert details.ratings[0].value == 8.5
        assert details.ratings[0].votes == 850000
        assert details.ratings[1].source == DataSource.IMDB
        assert details.ratings[1].value == 8.7
        assert details.ratings[1].votes == 1900000

        assert details.genres == ["фантастика", "боевик"]
        assert details.countries == ["США", "Австралия"]
        assert details.studios == ["Warner Bros."]
        assert details.tags == ["neo", "cyberpunk"]

        assert len(details.directors) == 2
        assert details.directors[0].name_ru == "Лана Вачовски"
        assert details.directors[1].name_ru == "Лилли Вачовски"

        assert len(details.writers) == 1
        assert details.writers[0].name_ru == "Лана Вачовски"

        assert len(details.cast) == 2
        assert details.cast[0].name_ru == "Киану Ривз"
        assert details.cast[0].role == "Нео"
        assert details.cast[0].photo_url == "https://example.com/keanu.jpg"
        assert details.cast[0].order == 0
        assert details.cast[1].name_ru == "Лоренс Фишбёрн"
        assert details.cast[1].role == "Морфеус"
        assert details.cast[1].order == 1

        assert len(details.artwork) == 2
        assert details.artwork[0].artwork_type == ArtworkType.POSTER
        assert details.artwork[0].url == "https://example.com/poster.jpg"
        assert details.artwork[1].artwork_type == ArtworkType.FANART
        assert details.artwork[1].url == "https://example.com/fanart.jpg"

        assert details.set_name == "Матрица"

    def test_parse_full_movie_minimal(self):
        """NFO with only <title>. Assert MovieDetails with defaults."""
        nfo = "<movie><title>Минимальный фильм</title></movie>"
        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert details.title_ru == "Минимальный фильм"
        assert details.title_original == ""
        assert details.year == 0
        assert details.plot == ""
        assert details.tagline == ""
        assert details.runtime == 0
        assert details.mpaa == ""
        assert details.kinopoisk_id == 0
        assert details.imdb_id == ""
        assert details.genres == []
        assert details.countries == []
        assert details.studios == []
        assert details.ratings == []
        assert details.directors == []
        assert details.writers == []
        assert details.cast == []
        assert details.artwork == []
        assert details.tags == []
        assert details.set_name == ""

    def test_parse_full_movie_invalid_xml(self):
        """Pass broken XML. Assert returns None."""
        parser = _make_parser()
        result = parser.parse_full_movie("<not valid xml")
        assert result is None

    def test_parse_full_movie_no_title(self):
        """Valid XML without <title>. Assert returns None."""
        parser = _make_parser()
        result = parser.parse_full_movie("<movie><year>2020</year></movie>")
        assert result is None

    def test_parse_full_movie_empty(self):
        """Pass empty string. Assert returns None."""
        parser = _make_parser()
        result = parser.parse_full_movie("")
        assert result is None

    def test_parse_full_movie_ratings(self):
        """XML with ratings block. Assert correct Rating objects."""
        nfo = """<movie>
            <title>Rating Test</title>
            <ratings>
                <rating name="kinopoisk" max="10" default="true">
                    <value>7.8</value>
                    <votes>500000</votes>
                </rating>
                <rating name="imdb" max="10">
                    <value>8.1</value>
                    <votes>1200000</votes>
                </rating>
                <rating name="rottentomatoes" max="100">
                    <value>88</value>
                    <votes>350</votes>
                </rating>
            </ratings>
        </movie>"""
        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert len(details.ratings) == 3

        kp_rating = details.ratings[0]
        assert kp_rating.source == DataSource.KINOPOISK
        assert kp_rating.value == 7.8
        assert kp_rating.votes == 500000

        imdb_rating = details.ratings[1]
        assert imdb_rating.source == DataSource.IMDB
        assert imdb_rating.value == 8.1
        assert imdb_rating.votes == 1200000

        rt_rating = details.ratings[2]
        assert rt_rating.source == DataSource.ROTTEN_TOMATOES
        assert rt_rating.value == 88.0
        assert rt_rating.votes == 350

    def test_parse_full_movie_actors(self):
        """XML with 3 actor elements. Assert Person objects with all fields."""
        nfo = """<movie>
            <title>Actors Test</title>
            <actor>
                <name>Актёр Первый</name>
                <role>Главный герой</role>
                <thumb>https://img.example.com/actor1.jpg</thumb>
                <order>0</order>
            </actor>
            <actor>
                <name>Актёр Второй</name>
                <role>Злодей</role>
                <thumb>https://img.example.com/actor2.jpg</thumb>
                <order>1</order>
            </actor>
            <actor>
                <name>Актёр Третий</name>
                <role>Сайдкик</role>
                <thumb>https://img.example.com/actor3.jpg</thumb>
                <order>2</order>
            </actor>
        </movie>"""
        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert len(details.cast) == 3

        assert details.cast[0].name_ru == "Актёр Первый"
        assert details.cast[0].role == "Главный герой"
        assert details.cast[0].photo_url == "https://img.example.com/actor1.jpg"
        assert details.cast[0].order == 0

        assert details.cast[1].name_ru == "Актёр Второй"
        assert details.cast[1].role == "Злодей"
        assert details.cast[1].photo_url == "https://img.example.com/actor2.jpg"
        assert details.cast[1].order == 1

        assert details.cast[2].name_ru == "Актёр Третий"
        assert details.cast[2].role == "Сайдкик"
        assert details.cast[2].photo_url == "https://img.example.com/actor3.jpg"
        assert details.cast[2].order == 2

    def test_parse_full_movie_artwork(self):
        """XML with poster and fanart thumb elements. Assert Artwork objects."""
        nfo = """<movie>
            <title>Artwork Test</title>
            <thumb aspect="poster">https://img.example.com/poster.jpg</thumb>
            <thumb aspect="fanart">https://img.example.com/fanart.jpg</thumb>
        </movie>"""
        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert len(details.artwork) == 2

        assert details.artwork[0].artwork_type == ArtworkType.POSTER
        assert details.artwork[0].url == "https://img.example.com/poster.jpg"

        assert details.artwork[1].artwork_type == ArtworkType.FANART
        assert details.artwork[1].url == "https://img.example.com/fanart.jpg"

    def test_parse_full_movie_set(self):
        """XML with <set><name> element. Assert set_name populated."""
        nfo = """<movie>
            <title>Set Test</title>
            <set>
                <name>Матрица</name>
            </set>
        </movie>"""
        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert details.set_name == "Матрица"


class TestParseFullTVShow:
    """Tests for NfoParser.parse_full_tvshow()."""

    def test_parse_full_tvshow_complete(self):
        """Full TVShow NFO. Assert TVShowDetails with all fields.
        Verify no set_name attribute (TVShowDetails doesn't have it).
        """
        nfo = """<tvshow>
            <title>Во все тяжкие</title>
            <originaltitle>Breaking Bad</originaltitle>
            <year>2008</year>
            <plot>Учитель химии начинает варить метамфетамин.</plot>
            <tagline>All Hail the King</tagline>
            <runtime>47</runtime>
            <mpaa>TV-MA</mpaa>
            <uniqueid type="kinopoisk" default="true">462682</uniqueid>
            <uniqueid type="imdb">tt0903747</uniqueid>
            <ratings>
                <rating name="kinopoisk" max="10" default="true">
                    <value>9.0</value>
                    <votes>700000</votes>
                </rating>
                <rating name="imdb" max="10">
                    <value>9.5</value>
                    <votes>2000000</votes>
                </rating>
            </ratings>
            <genre>драма</genre>
            <genre>криминал</genre>
            <country>США</country>
            <studio>AMC</studio>
            <tag>emmy</tag>
            <director>Винс Гиллиган</director>
            <credits>Винс Гиллиган</credits>
            <actor>
                <name>Брайан Крэнстон</name>
                <role>Уолтер Уайт</role>
                <thumb>https://example.com/cranston.jpg</thumb>
                <order>0</order>
            </actor>
            <actor>
                <name>Аарон Пол</name>
                <role>Джесси Пинкман</role>
                <thumb>https://example.com/paul.jpg</thumb>
                <order>1</order>
            </actor>
            <thumb aspect="poster">https://example.com/bb_poster.jpg</thumb>
            <thumb aspect="fanart">https://example.com/bb_fanart.jpg</thumb>
        </tvshow>"""

        parser = _make_parser()
        details = parser.parse_full_tvshow(nfo)

        assert details is not None
        assert isinstance(details, TVShowDetails)
        assert details.title_ru == "Во все тяжкие"
        assert details.title_original == "Breaking Bad"
        assert details.year == 2008
        assert details.plot == "Учитель химии начинает варить метамфетамин."
        assert details.tagline == "All Hail the King"
        assert details.runtime == 47
        assert details.mpaa == "TV-MA"
        assert details.kinopoisk_id == 462682
        assert details.imdb_id == "tt0903747"

        assert len(details.ratings) == 2
        assert details.ratings[0].source == DataSource.KINOPOISK
        assert details.ratings[0].value == 9.0
        assert details.ratings[0].votes == 700000

        assert details.genres == ["драма", "криминал"]
        assert details.countries == ["США"]
        assert details.studios == ["AMC"]
        assert details.tags == ["emmy"]

        assert len(details.directors) == 1
        assert details.directors[0].name_ru == "Винс Гиллиган"

        assert len(details.writers) == 1
        assert details.writers[0].name_ru == "Винс Гиллиган"

        assert len(details.cast) == 2
        assert details.cast[0].name_ru == "Брайан Крэнстон"
        assert details.cast[0].role == "Уолтер Уайт"
        assert details.cast[1].name_ru == "Аарон Пол"

        assert len(details.artwork) == 2
        assert details.artwork[0].artwork_type == ArtworkType.POSTER
        assert details.artwork[1].artwork_type == ArtworkType.FANART

        # TVShowDetails does NOT have set_name attribute
        assert not hasattr(details, "set_name")

    def test_parse_full_tvshow_no_title(self):
        """TVShow NFO without <title>. Assert returns None."""
        nfo = """<tvshow>
            <year>2008</year>
            <genre>драма</genre>
        </tvshow>"""
        parser = _make_parser()
        result = parser.parse_full_tvshow(nfo)
        assert result is None


class TestRoundtripMovie:
    """Test writing a MovieDetails to XML and parsing it back."""

    def test_roundtrip_movie(self):
        """Create MovieDetails, generate XML via nfo_writer._build_movie_xml,
        parse back with parse_full_movie. Assert key fields match.
        """
        from nfo_writer import _build_movie_xml

        original = MovieDetails(
            kinopoisk_id=301,
            imdb_id="tt0133093",
            title_ru="Матрица",
            title_original="The Matrix",
            year=1999,
            plot="Хакер Нео узнаёт правду о мире.",
            tagline="Добро пожаловать в реальный мир",
            runtime=136,
            mpaa="R",
            genres=["фантастика", "боевик"],
            countries=["США"],
            studios=["Warner Bros."],
            ratings=[
                Rating(source=DataSource.KINOPOISK, value=8.5, votes=850000),
                Rating(source=DataSource.IMDB, value=8.7, votes=1900000),
            ],
            directors=[Person(name_ru="Лана Вачовски")],
            writers=[Person(name_ru="Лана Вачовски")],
            cast=[
                Person(
                    name_ru="Киану Ривз",
                    role="Нео",
                    photo_url="https://example.com/keanu.jpg",
                    order=0,
                ),
            ],
            artwork=[
                Artwork(url="https://example.com/poster.jpg", artwork_type=ArtworkType.POSTER),
                Artwork(url="https://example.com/fanart.jpg", artwork_type=ArtworkType.FANART),
            ],
            set_name="Матрица",
            tags=["cyberpunk"],
        )

        xml_string = _build_movie_xml(original)
        parser = _make_parser()
        parsed = parser.parse_full_movie(xml_string)

        assert parsed is not None
        assert parsed.title_ru == original.title_ru
        assert parsed.title_original == original.title_original
        assert parsed.year == original.year
        assert parsed.kinopoisk_id == original.kinopoisk_id
        assert parsed.imdb_id == original.imdb_id
        assert parsed.plot == original.plot
        assert parsed.tagline == original.tagline
        assert parsed.runtime == original.runtime
        assert parsed.mpaa == original.mpaa
        assert parsed.genres == original.genres
        assert parsed.countries == original.countries
        assert parsed.studios == original.studios
        assert parsed.tags == original.tags
        assert parsed.set_name == original.set_name

        assert len(parsed.ratings) == len(original.ratings)
        for orig_r, parsed_r in zip(original.ratings, parsed.ratings):
            assert parsed_r.source == orig_r.source
            assert parsed_r.value == orig_r.value
            assert parsed_r.votes == orig_r.votes

        assert len(parsed.cast) == len(original.cast)
        assert parsed.cast[0].name_ru == original.cast[0].name_ru
        assert parsed.cast[0].role == original.cast[0].role
        assert parsed.cast[0].photo_url == original.cast[0].photo_url

        assert len(parsed.artwork) == len(original.artwork)
        assert parsed.artwork[0].artwork_type == ArtworkType.POSTER
        assert parsed.artwork[1].artwork_type == ArtworkType.FANART


class TestTrailerNfo:
    """Tests for trailer roundtrip in NFO export/import."""

    KODI_TRAILER_URL = (
        "plugin://plugin.video.youtube/?action=play_video&videoid=dQw4w9WgXcQ"
    )

    def test_nfo_writer_includes_trailer(self):
        """AC-07: MovieDetails with trailer_url -> XML contains <trailer>."""
        from nfo_writer import _build_movie_xml
        import xml.etree.ElementTree as ET

        details = MovieDetails(
            title_ru="Трейлер Тест",
            trailer_url=self.KODI_TRAILER_URL,
        )
        xml_string = _build_movie_xml(details)

        root = ET.fromstring(xml_string)
        trailer_elem = root.find("trailer")
        assert trailer_elem is not None, "<trailer> element must be present in XML"
        assert trailer_elem.text == self.KODI_TRAILER_URL

    def test_nfo_writer_no_trailer(self):
        """MovieDetails without trailer_url -> XML has no <trailer>."""
        from nfo_writer import _build_movie_xml
        import xml.etree.ElementTree as ET

        details = MovieDetails(
            title_ru="Без Трейлера",
            trailer_url="",
        )
        xml_string = _build_movie_xml(details)

        root = ET.fromstring(xml_string)
        trailer_elem = root.find("trailer")
        assert trailer_elem is None, "<trailer> element must NOT be present when trailer_url is empty"

    def test_nfo_parser_reads_trailer(self):
        """AC-08: NFO XML with <trailer> -> parse_full_movie returns trailer_url."""
        nfo = """<movie>
            <title>Парсинг Трейлера</title>
            <year>2024</year>
            <trailer>plugin://plugin.video.youtube/?action=play_video&amp;videoid=dQw4w9WgXcQ</trailer>
        </movie>"""

        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert details.trailer_url == self.KODI_TRAILER_URL

    def test_nfo_parser_no_trailer(self):
        """NFO XML without <trailer> -> trailer_url is empty."""
        nfo = """<movie>
            <title>Без Трейлера</title>
            <year>2024</year>
        </movie>"""

        parser = _make_parser()
        details = parser.parse_full_movie(nfo)

        assert details is not None
        assert details.trailer_url == ""

    def test_nfo_roundtrip_trailer(self):
        """Write NFO with trailer -> parse it back -> trailer_url matches."""
        from nfo_writer import _build_movie_xml

        original = MovieDetails(
            title_ru="Roundtrip Трейлер",
            year=2024,
            trailer_url=self.KODI_TRAILER_URL,
        )

        xml_string = _build_movie_xml(original)
        parser = _make_parser()
        parsed = parser.parse_full_movie(xml_string)

        assert parsed is not None
        assert parsed.trailer_url == original.trailer_url

    def test_nfo_tvshow_trailer(self):
        """AC-08: TVShowDetails with trailer -> write and parse back."""
        from nfo_writer import _build_tvshow_xml

        original = TVShowDetails(
            title_ru="Сериал с Трейлером",
            year=2024,
            trailer_url=self.KODI_TRAILER_URL,
        )

        xml_string = _build_tvshow_xml(original)
        parser = _make_parser()
        parsed = parser.parse_full_tvshow(xml_string)

        assert parsed is not None
        assert parsed.trailer_url == original.trailer_url
