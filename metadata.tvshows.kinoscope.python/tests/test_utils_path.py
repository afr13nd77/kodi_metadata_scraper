from __future__ import annotations

from unittest.mock import MagicMock

from utils import extract_title_from_path
from logger import Logger


def _mock_logger():
    return MagicMock(spec=Logger)


class TestExtractTitleFromPath:
    def test_windows_path(self):
        logger = _mock_logger()
        result = extract_title_from_path(
            r"E:\Movies\Practical Magic 2 (2026)\Practical.Magic.2.2026.1080p.AMZN.WEB-DL.[Rus.Ukr.Eng].Rutracker.mkv",
            logger,
        )
        assert result[0] == ("filename", "Practical.Magic.2.2026.1080p.AMZN.WEB-DL.[Rus.Ukr.Eng].Rutracker")
        assert result[1] == ("dirname", "Practical Magic 2 (2026)")

    def test_linux_path(self):
        logger = _mock_logger()
        result = extract_title_from_path(
            "/media/movies/Film (2026)/film.mkv", logger
        )
        assert result[0] == ("filename", "film")
        assert result[1] == ("dirname", "Film (2026)")

    def test_smb_path(self):
        logger = _mock_logger()
        result = extract_title_from_path(
            "smb://192.168.0.1/movies/Film (2026)/film.mkv", logger
        )
        assert result[0] == ("filename", "film")
        assert result[1] == ("dirname", "Film (2026)")

    def test_nfs_path(self):
        logger = _mock_logger()
        result = extract_title_from_path(
            "nfs://server/export/Film/film.avi", logger
        )
        assert result[0] == ("filename", "film")
        assert result[1] == ("dirname", "Film")

    def test_no_parent_dir(self):
        logger = _mock_logger()
        result = extract_title_from_path(r"E:\film.mkv", logger)
        assert len(result) == 2
        assert result[0] == ("filename", "film")
        # "E:" is the parent — may be included as dirname

    def test_various_extensions_mkv(self):
        logger = _mock_logger()
        result = extract_title_from_path("/movies/test.mkv", logger)
        assert result[0][1] == "test"

    def test_various_extensions_avi(self):
        logger = _mock_logger()
        result = extract_title_from_path("/movies/test.avi", logger)
        assert result[0][1] == "test"

    def test_various_extensions_mp4(self):
        logger = _mock_logger()
        result = extract_title_from_path("/movies/test.mp4", logger)
        assert result[0][1] == "test"

    def test_various_extensions_strm(self):
        logger = _mock_logger()
        result = extract_title_from_path("/movies/test.strm", logger)
        assert result[0][1] == "test"

    def test_empty_path(self):
        logger = _mock_logger()
        result = extract_title_from_path("", logger)
        assert result == []

    def test_trailing_slash(self):
        logger = _mock_logger()
        result = extract_title_from_path(r"E:\Movies\Film (2026)\\", logger)
        # After rstrip("/"), should handle correctly
        assert any(s == "dirname" for s, _ in result) or any("Film" in n for _, n in result)
