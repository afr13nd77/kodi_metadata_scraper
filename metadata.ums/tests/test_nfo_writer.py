from __future__ import annotations

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from models import (
    MovieDetails,
    TVShowDetails,
    Rating,
    Person,
    Artwork,
    ArtworkType,
    DataSource,
    ProfessionType,
)
from nfo_writer import (
    write_movie_nfo,
    _build_movie_xml,
    _build_tvshow_xml,
    _get_movie_nfo_path,
    _get_tvshow_nfo_path,
    _prettify_xml,
)
from nfo_parser import NfoParser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.enable_nfo_export = True
    s.nfo_overwrite = False
    return s


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def sample_movie():
    return MovieDetails(
        kinopoisk_id=301,
        imdb_id="tt0133093",
        title_ru="Матрица",
        title_original="The Matrix",
        year=1999,
    )


# ---------------------------------------------------------------------------
# 1. test_get_movie_nfo_path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("video_path, expected_nfo", [
    ("movie.mkv", "movie.nfo"),
    ("movie.avi", "movie.nfo"),
    ("/movies/The Matrix.mkv", "/movies/The Matrix.nfo"),
    ("smb://NAS/movie.mp4", "smb://NAS/movie.nfo"),
])
def test_get_movie_nfo_path(video_path, expected_nfo):
    assert _get_movie_nfo_path(video_path) == expected_nfo


# ---------------------------------------------------------------------------
# 2. test_get_tvshow_nfo_path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("input_path, expected_nfo", [
    ("/tvshows/Show/", "/tvshows/Show/tvshow.nfo"),
    ("/tvshows/Show", "/tvshows/Show/tvshow.nfo"),
    ("/tvshows/Show/episode.mkv", "/tvshows/Show/tvshow.nfo"),
    ("smb://NAS/Show/", "smb://NAS/Show/tvshow.nfo"),
])
def test_get_tvshow_nfo_path(input_path, expected_nfo):
    assert _get_tvshow_nfo_path(input_path) == expected_nfo


# ---------------------------------------------------------------------------
# 3. test_build_movie_xml_full
# ---------------------------------------------------------------------------

def test_build_movie_xml_full():
    details = MovieDetails(
        kinopoisk_id=301,
        imdb_id="tt0133093",
        title_ru="Матрица",
        title_original="The Matrix",
        year=1999,
        plot="Test plot",
        tagline="Welcome",
        runtime=136,
        mpaa="R",
        genres=["фантастика", "боевик"],
        countries=["США"],
        studios=["Warner Bros."],
        ratings=[
            Rating(DataSource.KINOPOISK, 8.5, 500000),
            Rating(DataSource.IMDB, 8.7, 1800000),
        ],
        directors=[Person(name_ru="Вачовски", profession=ProfessionType.DIRECTOR)],
        writers=[Person(name_ru="Вачовски", profession=ProfessionType.WRITER)],
        cast=[
            Person(
                name_ru="Киану Ривз",
                role="Нео",
                photo_url="http://photo.jpg",
                order=0,
            )
        ],
        artwork=[
            Artwork(url="http://poster.jpg", artwork_type=ArtworkType.POSTER),
            Artwork(url="http://fanart.jpg", artwork_type=ArtworkType.FANART),
        ],
        set_name="Матрица",
        tags=["Оскар"],
    )

    xml_content = _build_movie_xml(details)
    root = ET.fromstring(xml_content.strip())

    assert root.tag == "movie"

    # title
    assert root.findtext("title") == "Матрица"
    # originaltitle
    assert root.findtext("originaltitle") == "The Matrix"
    # year
    assert root.findtext("year") == "1999"
    # plot
    assert root.findtext("plot") == "Test plot"
    # tagline
    assert root.findtext("tagline") == "Welcome"
    # runtime
    assert root.findtext("runtime") == "136"
    # mpaa
    assert root.findtext("mpaa") == "R"

    # uniqueid kinopoisk
    uid_kp = next(
        (e for e in root.findall("uniqueid") if e.get("type") == "kinopoisk"),
        None,
    )
    assert uid_kp is not None
    assert uid_kp.text == "301"
    assert uid_kp.get("default") == "true"

    # uniqueid imdb
    uid_imdb = next(
        (e for e in root.findall("uniqueid") if e.get("type") == "imdb"),
        None,
    )
    assert uid_imdb is not None
    assert uid_imdb.text == "tt0133093"

    # ratings
    ratings_elem = root.find("ratings")
    assert ratings_elem is not None
    rating_elems = ratings_elem.findall("rating")
    assert len(rating_elems) == 2
    kp_rating = next(r for r in rating_elems if r.get("name") == "kinopoisk")
    assert kp_rating.findtext("value") == "8.5"
    assert kp_rating.findtext("votes") == "500000"

    # genres
    genres = [e.text for e in root.findall("genre")]
    assert "фантастика" in genres
    assert "боевик" in genres

    # country
    assert root.findtext("country") == "США"

    # studio
    assert root.findtext("studio") == "Warner Bros."

    # tag
    assert root.findtext("tag") == "Оскар"

    # director
    assert root.findtext("director") == "Вачовски"

    # credits (writer)
    assert root.findtext("credits") == "Вачовски"

    # actor
    actor_elem = root.find("actor")
    assert actor_elem is not None
    assert actor_elem.findtext("name") == "Киану Ривз"
    assert actor_elem.findtext("role") == "Нео"
    assert actor_elem.findtext("thumb") == "http://photo.jpg"
    assert actor_elem.findtext("order") == "0"

    # artwork thumbs
    thumbs = root.findall("thumb")
    assert len(thumbs) == 2
    poster_thumb = next(t for t in thumbs if t.get("aspect") == "poster")
    assert poster_thumb.text == "http://poster.jpg"
    fanart_thumb = next(t for t in thumbs if t.get("aspect") == "fanart")
    assert fanart_thumb.text == "http://fanart.jpg"

    # set
    set_elem = root.find("set")
    assert set_elem is not None
    assert set_elem.findtext("name") == "Матрица"


# ---------------------------------------------------------------------------
# 4. test_build_movie_xml_minimal
# ---------------------------------------------------------------------------

def test_build_movie_xml_minimal():
    details = MovieDetails(kinopoisk_id=12345, title_ru="Тест")

    xml_content = _build_movie_xml(details)
    root = ET.fromstring(xml_content.strip())

    assert root.tag == "movie"
    assert root.findtext("title") == "Тест"

    uid_kp = next(
        (e for e in root.findall("uniqueid") if e.get("type") == "kinopoisk"),
        None,
    )
    assert uid_kp is not None

    # optional elements must be absent
    assert root.find("originaltitle") is None
    assert root.find("year") is None
    assert root.find("plot") is None
    assert root.find("tagline") is None
    assert root.find("runtime") is None
    assert root.find("mpaa") is None
    assert root.find("ratings") is None
    assert root.find("genre") is None
    assert root.find("director") is None
    assert root.find("credits") is None
    assert root.find("actor") is None
    assert root.find("thumb") is None
    assert root.find("set") is None


# ---------------------------------------------------------------------------
# 5. test_build_tvshow_xml_full
# ---------------------------------------------------------------------------

def test_build_tvshow_xml_full():
    details = TVShowDetails(
        kinopoisk_id=555,
        imdb_id="tt0944947",
        title_ru="Игра престолов",
        title_original="Game of Thrones",
        year=2011,
        plot="Борьба за трон",
        tagline="Winter is coming",
        runtime=60,
        mpaa="TV-MA",
        genres=["фэнтези", "драма"],
        countries=["США", "Великобритания"],
        studios=["HBO"],
        ratings=[Rating(DataSource.KINOPOISK, 9.1, 300000)],
        directors=[Person(name_ru="Дэвид Бениофф", profession=ProfessionType.DIRECTOR)],
        writers=[Person(name_ru="Дэвид Бениофф", profession=ProfessionType.WRITER)],
        cast=[Person(name_ru="Питер Динклэйдж", role="Тирион Ланнистер", order=0)],
        artwork=[
            Artwork(url="http://poster.jpg", artwork_type=ArtworkType.POSTER),
            Artwork(url="http://fanart.jpg", artwork_type=ArtworkType.FANART),
        ],
        tags=["Эмми"],
    )

    xml_content = _build_tvshow_xml(details)
    root = ET.fromstring(xml_content.strip())

    assert root.tag == "tvshow"
    assert root.findtext("title") == "Игра престолов"
    assert root.findtext("originaltitle") == "Game of Thrones"
    assert root.findtext("year") == "2011"
    assert root.findtext("plot") == "Борьба за трон"
    assert root.findtext("tagline") == "Winter is coming"
    assert root.findtext("runtime") == "60"
    assert root.findtext("mpaa") == "TV-MA"

    uid_kp = next(
        (e for e in root.findall("uniqueid") if e.get("type") == "kinopoisk"),
        None,
    )
    assert uid_kp is not None
    assert uid_kp.text == "555"

    genres = [e.text for e in root.findall("genre")]
    assert "фэнтези" in genres

    assert root.find("set") is None


# ---------------------------------------------------------------------------
# 6. test_ratings_max_values
# ---------------------------------------------------------------------------

def test_ratings_max_values():
    details = MovieDetails(
        kinopoisk_id=1,
        title_ru="Тест",
        ratings=[
            Rating(DataSource.KINOPOISK, 8.0, 100),
            Rating(DataSource.IMDB, 7.5, 200),
            Rating(DataSource.ROTTEN_TOMATOES, 90, 300),
            Rating(DataSource.METACRITIC, 85, 400),
        ],
    )

    xml_content = _build_movie_xml(details)
    root = ET.fromstring(xml_content.strip())

    ratings_elem = root.find("ratings")
    assert ratings_elem is not None

    rating_map = {r.get("name"): r for r in ratings_elem.findall("rating")}

    assert rating_map["kinopoisk"].get("max") == "10"
    assert rating_map["imdb"].get("max") == "10"
    assert rating_map["rottentomatoes"].get("max") == "100"
    assert rating_map["metacritic"].get("max") == "100"

    # default="true" only on kinopoisk
    assert rating_map["kinopoisk"].get("default") == "true"
    assert rating_map["imdb"].get("default") is None
    assert rating_map["rottentomatoes"].get("default") is None
    assert rating_map["metacritic"].get("default") is None


# ---------------------------------------------------------------------------
# 7. test_writers_use_credits_tag
# ---------------------------------------------------------------------------

def test_writers_use_credits_tag():
    details = MovieDetails(
        kinopoisk_id=1,
        title_ru="Тест",
        writers=[
            Person(name_ru="Автор Первый", profession=ProfessionType.WRITER),
            Person(name_ru="Автор Второй", profession=ProfessionType.WRITER),
        ],
    )

    xml_content = _build_movie_xml(details)
    root = ET.fromstring(xml_content.strip())

    credits_elems = root.findall("credits")
    assert len(credits_elems) == 2
    names = [e.text for e in credits_elems]
    assert "Автор Первый" in names
    assert "Автор Второй" in names

    # must NOT use <writer> tag
    assert root.find("writer") is None


# ---------------------------------------------------------------------------
# 8. test_artwork_poster_fanart_only
# ---------------------------------------------------------------------------

def test_artwork_poster_fanart_only():
    details = MovieDetails(
        kinopoisk_id=1,
        title_ru="Тест",
        artwork=[
            Artwork(url="http://poster.jpg", artwork_type=ArtworkType.POSTER),
            Artwork(url="http://fanart.jpg", artwork_type=ArtworkType.FANART),
            Artwork(url="http://banner.jpg", artwork_type=ArtworkType.BANNER),
            Artwork(url="http://clearlogo.png", artwork_type=ArtworkType.CLEARLOGO),
        ],
    )

    xml_content = _build_movie_xml(details)
    root = ET.fromstring(xml_content.strip())

    # Only direct <thumb> children (not nested inside <actor>)
    thumbs = [e for e in root if e.tag == "thumb"]
    assert len(thumbs) == 2

    aspects = {t.get("aspect") for t in thumbs}
    assert "poster" in aspects
    assert "fanart" in aspects


# ---------------------------------------------------------------------------
# 9. test_xml_special_characters
# ---------------------------------------------------------------------------

def test_xml_special_characters():
    details = MovieDetails(
        kinopoisk_id=1,
        title_ru='Tom & Jerry',
        plot='<script>alert("xss")</script>',
    )

    xml_content = _build_movie_xml(details)

    # Must parse without raising
    root = ET.fromstring(xml_content.strip())

    # ET unescapes on read, so text content is preserved as-is
    assert root.findtext("title") == "Tom & Jerry"
    assert root.findtext("plot") == '<script>alert("xss")</script>'


# ---------------------------------------------------------------------------
# 10. test_prettify_xml_declaration
# ---------------------------------------------------------------------------

def test_prettify_xml_declaration():
    elem = ET.Element("test")
    ET.SubElement(elem, "child").text = "value"

    result = _prettify_xml(elem)

    assert result.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
    assert result.endswith("\n")


# ---------------------------------------------------------------------------
# 11. test_set_element_movie_only
# ---------------------------------------------------------------------------

def test_set_element_movie_only():
    movie = MovieDetails(kinopoisk_id=1, title_ru="Тест", set_name="Saga")
    xml_content = _build_movie_xml(movie)
    root = ET.fromstring(xml_content.strip())

    set_elem = root.find("set")
    assert set_elem is not None
    assert set_elem.findtext("name") == "Saga"

    tvshow = TVShowDetails(kinopoisk_id=2, title_ru="Шоу")
    xml_content_tv = _build_tvshow_xml(tvshow)
    root_tv = ET.fromstring(xml_content_tv.strip())

    assert root_tv.find("set") is None


# ---------------------------------------------------------------------------
# 12. test_write_movie_nfo_disabled
# ---------------------------------------------------------------------------

def test_write_movie_nfo_disabled(sample_movie, mock_logger):
    settings = MagicMock()
    settings.enable_nfo_export = False

    with patch("nfo_writer.xbmcvfs") as mock_vfs:
        write_movie_nfo(sample_movie, "/movies/movie.mkv", settings, mock_logger)

    mock_vfs.File.assert_not_called()


# ---------------------------------------------------------------------------
# 13. test_write_movie_nfo_exists_no_overwrite
# ---------------------------------------------------------------------------

def test_write_movie_nfo_exists_no_overwrite(sample_movie, mock_logger):
    settings = MagicMock()
    settings.enable_nfo_export = True
    settings.nfo_overwrite = False

    with patch("nfo_writer.xbmcvfs") as mock_vfs:
        mock_vfs.exists.return_value = True
        write_movie_nfo(sample_movie, "/movies/movie.mkv", settings, mock_logger)

    mock_vfs.File.assert_not_called()


# ---------------------------------------------------------------------------
# 14. test_write_movie_nfo_exists_overwrite
# ---------------------------------------------------------------------------

def test_write_movie_nfo_exists_overwrite(sample_movie, mock_logger):
    settings = MagicMock()
    settings.enable_nfo_export = True
    settings.nfo_overwrite = True

    with patch("nfo_writer.xbmcvfs") as mock_vfs:
        mock_vfs.exists.return_value = True
        mock_file = MagicMock()
        mock_file.write.return_value = True
        mock_vfs.File.return_value = mock_file

        write_movie_nfo(sample_movie, "/movies/movie.mkv", settings, mock_logger)

    mock_vfs.File.assert_called_once()


# ---------------------------------------------------------------------------
# 15. test_write_movie_nfo_empty_path
# ---------------------------------------------------------------------------

def test_write_movie_nfo_empty_path(sample_movie, mock_logger):
    settings = MagicMock()
    settings.enable_nfo_export = True

    with patch("nfo_writer.xbmcvfs") as mock_vfs:
        write_movie_nfo(sample_movie, "", settings, mock_logger)

    mock_vfs.File.assert_not_called()


# ---------------------------------------------------------------------------
# 16. test_write_movie_nfo_write_error
# ---------------------------------------------------------------------------

def test_write_movie_nfo_write_error(sample_movie, mock_logger):
    settings = MagicMock()
    settings.enable_nfo_export = True
    settings.nfo_overwrite = False

    with patch("nfo_writer.xbmcvfs") as mock_vfs:
        mock_vfs.exists.return_value = False
        mock_vfs.File.side_effect = OSError("disk full")

        # Must NOT raise
        write_movie_nfo(sample_movie, "/movies/movie.mkv", settings, mock_logger)

    mock_logger.warning.assert_called()


# ---------------------------------------------------------------------------
# 17. test_nfo_parseable_by_nfo_parser  (AC-20)
# ---------------------------------------------------------------------------

def test_nfo_parseable_by_nfo_parser():
    details = MovieDetails(
        kinopoisk_id=301,
        imdb_id="tt0133093",
        title_ru="Матрица",
    )

    xml_content = _build_movie_xml(details)

    parser = NfoParser(logger=MagicMock())
    result = parser.parse(xml_content)

    assert result.kinopoisk_id == 301
    assert result.imdb_id == "tt0133093"


# ---------------------------------------------------------------------------
# 18. test_get_movie_nfo_path_directory_trailing_slash  (BL-57)
# ---------------------------------------------------------------------------

def test_get_movie_nfo_path_directory_trailing_slash():
    assert _get_movie_nfo_path("/movies/The Matrix (1999)/") == ""


# ---------------------------------------------------------------------------
# 19. test_get_movie_nfo_path_directory_backslash  (BL-57)
# ---------------------------------------------------------------------------

def test_get_movie_nfo_path_directory_backslash():
    assert _get_movie_nfo_path("C:\\Movies\\The Matrix (1999)\\") == ""


# ---------------------------------------------------------------------------
# 20. test_get_movie_nfo_path_directory_no_extension  (BL-57)
# ---------------------------------------------------------------------------

def test_get_movie_nfo_path_directory_no_extension():
    assert _get_movie_nfo_path("/movies/The Matrix (1999)") == ""


# ---------------------------------------------------------------------------
# 21. test_get_movie_nfo_path_normal_file  (BL-57)
# ---------------------------------------------------------------------------

def test_get_movie_nfo_path_normal_file():
    assert _get_movie_nfo_path("/movies/The Matrix (1999).mkv") == "/movies/The Matrix (1999).nfo"


# ---------------------------------------------------------------------------
# 22. test_write_movie_nfo_directory_path_skips  (BL-57)
# ---------------------------------------------------------------------------

def test_write_movie_nfo_directory_path_skips(sample_movie, mock_settings, mock_logger):
    with patch("nfo_writer.xbmcvfs") as mock_vfs:
        write_movie_nfo(sample_movie, "smb://server/Movies/The Matrix (1999)/", mock_settings, mock_logger)

    mock_vfs.File.assert_not_called()
    mock_logger.info.assert_called()
    logged_messages = " ".join(str(call) for call in mock_logger.info.call_args_list)
    assert "directory path detected" in logged_messages
