from unittest.mock import MagicMock
from nfo_parser import NfoParser, NfoParseResult
from logger import Logger


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
