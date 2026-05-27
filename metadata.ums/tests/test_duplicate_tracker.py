from __future__ import annotations

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

# Patch _HAS_XBMCVFS before importing DuplicateTracker so that
# the class uses stdlib open()/os instead of xbmcvfs mocks.
import duplicate_tracker as dt_module
dt_module._HAS_XBMCVFS = False
from duplicate_tracker import DuplicateTracker  # noqa: E402


class TestDuplicateTracker:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.logger = MagicMock()
        self.tracker_path = os.path.join(self.tmpdir, "duplicate_tracker.json")
        # Build instance bypassing __init__ to avoid _get_tracker_path() logic
        self.tracker = DuplicateTracker.__new__(DuplicateTracker)
        self.tracker._addon_id = "test.addon"
        self.tracker._logger = self.logger
        self.tracker._tracker_path = self.tracker_path

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_new_entry_returns_none(self):
        result = self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert result is None
        assert os.path.exists(self.tracker_path)
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"447301": "/movies/A.mkv"}

    def test_same_path_returns_none(self):
        result1 = self.tracker.check_and_update(447301, "/movies/A.mkv")
        result2 = self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert result1 is None
        assert result2 is None

    def test_different_path_returns_existing(self):
        result1 = self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert result1 is None
        result2 = self.tracker.check_and_update(447301, "/movies/B.mkv")
        assert result2 == "/movies/A.mkv"
        # File must be updated with new path
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["447301"] == "/movies/B.mkv"

    def test_multiple_kp_ids(self):
        assert self.tracker.check_and_update(100, "/movies/X.mkv") is None
        assert self.tracker.check_and_update(200, "/movies/Y.mkv") is None
        # Duplicates on each
        assert self.tracker.check_and_update(100, "/movies/X2.mkv") == "/movies/X.mkv"
        assert self.tracker.check_and_update(200, "/movies/Y2.mkv") == "/movies/Y.mkv"
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"100": "/movies/X2.mkv", "200": "/movies/Y2.mkv"}

    def test_corrupted_json_returns_none(self):
        with open(self.tracker_path, "w", encoding="utf-8") as f:
            f.write("this is not json{{{")
        result = self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert result is None
        # Corrupted file should be deleted and new data written
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"447301": "/movies/A.mkv"}
        self.logger.warning.assert_called()

    def test_not_dict_json_returns_none(self):
        with open(self.tracker_path, "w", encoding="utf-8") as f:
            f.write("[1,2,3]")
        result = self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert result is None
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == {"447301": "/movies/A.mkv"}
        self.logger.warning.assert_called()

    def test_clear_deletes_file(self):
        self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert os.path.exists(self.tracker_path)
        self.tracker.clear()
        assert not os.path.exists(self.tracker_path)

    def test_clear_nonexistent_file(self):
        # Must not raise
        assert not os.path.exists(self.tracker_path)
        self.tracker.clear()

    def test_cyrillic_path_preserved(self):
        path = "/movies/Матрица (1999)/Матрица.mkv"
        self.tracker.check_and_update(447301, path)
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["447301"] == path
        assert "Матрица" in data["447301"]

    def test_persistence_across_instances(self):
        self.tracker.check_and_update(447301, "/movies/A.mkv")
        # Create a second tracker instance with the same path
        tracker2 = DuplicateTracker.__new__(DuplicateTracker)
        tracker2._addon_id = "test.addon"
        tracker2._logger = MagicMock()
        tracker2._tracker_path = self.tracker_path
        result = tracker2.check_and_update(447301, "/movies/B.mkv")
        assert result == "/movies/A.mkv"

    def test_write_error_returns_none(self):
        with patch.object(self.tracker, '_write_file', side_effect=OSError("disk full")):
            result = self.tracker.check_and_update(447301, "/movies/A.mkv")
        assert result is None
        self.logger.warning.assert_called()

    def test_basename_for_folder_trailing_slash(self):
        path_with_slash = "/tv/Breaking Bad/"
        result = self.tracker.check_and_update(447301, path_with_slash)
        assert result is None
        # Read back and verify trailing slash preserved
        with open(self.tracker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["447301"] == path_with_slash
        assert data["447301"].endswith("/")
