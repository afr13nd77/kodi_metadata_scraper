from __future__ import annotations

import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

# Patch _HAS_XBMCVFS before importing FileCache so that
# the class uses stdlib open()/os instead of xbmcvfs mocks.
import cache as cache_module
cache_module._HAS_XBMCVFS = False
from cache import FileCache  # noqa: E402 -- must patch _HAS_XBMCVFS before import


class TestFileCache:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.logger = MagicMock()
        self.cache = FileCache.__new__(FileCache)
        self.cache._addon_id = "test.addon"
        self.cache._logger = self.logger
        self.cache._ttl_days = 7
        self.cache._cache_dir = self.tmpdir

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_miss_no_file(self):
        result = self.cache.get("nonexistent_key")
        assert result is None

    def test_put_then_get_hit(self):
        data = {"title": "Test Movie", "year": 2025}
        self.cache.put("test_key", data)
        result = self.cache.get("test_key")
        assert result == data

    def test_get_expired_ttl(self):
        # Write a cache file with expired timestamp
        file_path = os.path.join(self.tmpdir, "expired_key.json")
        expired_time = (datetime.now() - timedelta(days=8)).isoformat(timespec="seconds")
        envelope = {"cached_at": expired_time, "ttl_days": 7, "data": {"test": True}}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        result = self.cache.get("expired_key")
        assert result is None
        # File should be deleted
        assert not os.path.exists(file_path)

    def test_get_fresh_ttl(self):
        # Write a cache file with fresh timestamp
        file_path = os.path.join(self.tmpdir, "fresh_key.json")
        fresh_time = datetime.now().isoformat(timespec="seconds")
        envelope = {"cached_at": fresh_time, "ttl_days": 7, "data": {"test": True}}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        result = self.cache.get("fresh_key")
        assert result == {"test": True}

    def test_get_corrupted_json(self):
        file_path = os.path.join(self.tmpdir, "corrupt_key.json")
        with open(file_path, "w") as f:
            f.write("this is not json{{{")

        result = self.cache.get("corrupt_key")
        assert result is None
        # File should be deleted
        assert not os.path.exists(file_path)
        # Warning should be logged
        self.logger.warning.assert_called()

    def test_put_creates_directory(self):
        subdir = os.path.join(self.tmpdir, "subdir", "cache")
        self.cache._cache_dir = subdir
        self.cache.put("key1", {"data": 1})
        assert os.path.exists(subdir)
        result = self.cache.get("key1")
        assert result == {"data": 1}

    def test_delete_existing(self):
        self.cache.put("del_key", {"data": 1})
        assert self.cache.get("del_key") is not None
        self.cache.delete("del_key")
        assert self.cache.get("del_key") is None

    def test_delete_nonexistent(self):
        # Should not raise
        self.cache.delete("nonexistent_key_xyz")

    def test_clear_all_files(self):
        self.cache.put("key1", {"a": 1})
        self.cache.put("key2", {"b": 2})
        self.cache.put("key3", {"c": 3})
        self.cache.clear()
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None
        assert self.cache.get("key3") is None

    def test_sanitize_key(self):
        assert self.cache._sanitize_key("simple_key") == "simple_key"
        assert self.cache._sanitize_key("key-with-dashes") == "key_with_dashes"
        assert self.cache._sanitize_key("key.with.dots") == "key_with_dots"
        assert self.cache._sanitize_key("kp_details_301") == "kp_details_301"
        assert self.cache._sanitize_key("omdb_ratings_tt0133093") == "omdb_ratings_tt0133093"

    def test_put_cyrillic_data(self):
        data = {"title": "Матрица", "genres": ["Фантастика"]}
        self.cache.put("cyrillic_key", data)
        result = self.cache.get("cyrillic_key")
        assert result == data
        assert result["title"] == "Матрица"

    def test_put_list_data(self):
        data = [{"name": "Actor1"}, {"name": "Actor2"}]
        self.cache.put("staff_key", data)
        result = self.cache.get("staff_key")
        assert result == data

    def test_get_invalid_cached_at_treated_as_expired(self):
        file_path = os.path.join(self.tmpdir, "bad_date.json")
        envelope = {"cached_at": "not-a-date", "ttl_days": 7, "data": {"test": True}}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f)

        result = self.cache.get("bad_date")
        assert result is None

    def test_put_error_graceful(self):
        with patch.object(self.cache, '_ensure_dir', side_effect=OSError("mocked")):
            self.cache.put("fail_key", {"data": 1})
        self.logger.warning.assert_called()

    def test_envelope_format(self):
        self.cache.put("format_key", {"test": 1})
        file_path = os.path.join(self.tmpdir, "format_key.json")
        with open(file_path, "r", encoding="utf-8") as f:
            envelope = json.load(f)
        assert "cached_at" in envelope
        assert "ttl_days" in envelope
        assert "data" in envelope
        assert envelope["ttl_days"] == 7
        assert envelope["data"] == {"test": 1}
