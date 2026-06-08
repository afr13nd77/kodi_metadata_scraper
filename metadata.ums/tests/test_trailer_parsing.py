from __future__ import annotations

from unittest.mock import MagicMock
from kinopoisk_api import KinopoiskClient, _YOUTUBE_VIDEO_ID_RE
from logger import Logger


def _make_client():
    logger = MagicMock(spec=Logger)
    return KinopoiskClient("test-api-key", logger), logger


# ------------------------------------------------------------------ #
# 1. _YOUTUBE_VIDEO_ID_RE regex tests
# ------------------------------------------------------------------ #

class TestYouTubeVideoIdRegex:
    """Tests for _YOUTUBE_VIDEO_ID_RE regex."""

    def test_watch_format(self):
        """AC-11: youtube.com/watch?v=ID is matched correctly."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        match = _YOUTUBE_VIDEO_ID_RE.search(url)
        assert match is not None
        assert match.group(1) == "dQw4w9WgXcQ"

    def test_short_format(self):
        """AC-11: youtu.be/ID is matched correctly."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        match = _YOUTUBE_VIDEO_ID_RE.search(url)
        assert match is not None
        assert match.group(1) == "dQw4w9WgXcQ"

    def test_embed_format(self):
        """AC-11: youtube.com/embed/ID is matched correctly."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        match = _YOUTUBE_VIDEO_ID_RE.search(url)
        assert match is not None
        assert match.group(1) == "dQw4w9WgXcQ"

    def test_invalid_url_no_match(self):
        """Non-video YouTube URL (channel page) should not match."""
        url = "https://www.youtube.com/channel/UC12345678AB"
        match = _YOUTUBE_VIDEO_ID_RE.search(url)
        assert match is None


# ------------------------------------------------------------------ #
# 2. parse_trailer_url tests
# ------------------------------------------------------------------ #

class TestParseTrailerUrl:
    """Tests for KinopoiskClient.parse_trailer_url."""

    def _make_client_instance(self):
        client, logger = _make_client()
        return client, logger

    def test_youtube_found(self):
        """AC-01: item with YouTube URL returns Kodi plugin URL."""
        client, logger = self._make_client_instance()
        data = {"total": 1, "items": [
            {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
             "name": "Trailer", "site": "YOUTUBE"}
        ]}
        result = client.parse_trailer_url(data)
        assert result == "plugin://plugin.video.youtube/?action=play_video&videoid=dQw4w9WgXcQ"

    def test_priority_trailer_keyword(self):
        """AC-03: item with 'Трейлер' in name is preferred over others."""
        client, logger = self._make_client_instance()
        data = {"total": 2, "items": [
            {"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
             "name": "Тизер", "site": "YOUTUBE"},
            {"url": "https://www.youtube.com/watch?v=BBBBBBBBBBB",
             "name": "Трейлер (дублированный)", "site": "YOUTUBE"},
        ]}
        result = client.parse_trailer_url(data)
        assert "BBBBBBBBBBB" in result

    def test_priority_case_insensitive(self):
        """AC-03: 'TRAILER' keyword matching is case-insensitive."""
        client, logger = self._make_client_instance()
        data = {"total": 2, "items": [
            {"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
             "name": "Teaser", "site": "YOUTUBE"},
            {"url": "https://www.youtube.com/watch?v=BBBBBBBBBBB",
             "name": "Official TRAILER", "site": "YOUTUBE"},
        ]}
        result = client.parse_trailer_url(data)
        assert "BBBBBBBBBBB" in result

    def test_no_youtube_items(self):
        """AC-02: only KINOPOISK_WIDGET items -> returns empty string."""
        client, logger = self._make_client_instance()
        data = {"total": 1, "items": [
            {"url": "https://widgets.kinopoisk.ru/123",
             "name": "Тизер", "site": "KINOPOISK_WIDGET"}
        ]}
        result = client.parse_trailer_url(data)
        assert result == ""

    def test_empty_items(self):
        """AC-02: items=[] -> returns empty string."""
        client, logger = self._make_client_instance()
        data = {"total": 0, "items": []}
        result = client.parse_trailer_url(data)
        assert result == ""

    def test_missing_url(self):
        """Edge case: url=None is filtered out, returns empty string."""
        client, logger = self._make_client_instance()
        data = {"total": 1, "items": [
            {"url": None, "name": "Trailer", "site": "YOUTUBE"}
        ]}
        result = client.parse_trailer_url(data)
        assert result == ""

    def test_missing_site(self):
        """Edge case: site=None is filtered out, returns empty string."""
        client, logger = self._make_client_instance()
        data = {"total": 1, "items": [
            {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
             "name": "Trailer", "site": None}
        ]}
        result = client.parse_trailer_url(data)
        assert result == ""

    def test_first_fallback_no_trailer_keyword(self):
        """AC-03: no 'трейлер'/'trailer' in any name -> takes first YouTube item."""
        client, logger = self._make_client_instance()
        data = {"total": 2, "items": [
            {"url": "https://www.youtube.com/watch?v=FIRST111111",
             "name": "Видео 1", "site": "YOUTUBE"},
            {"url": "https://www.youtube.com/watch?v=SECOND22222",
             "name": "Видео 2", "site": "YOUTUBE"},
        ]}
        result = client.parse_trailer_url(data)
        assert "FIRST111111" in result
