from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
sys.modules.setdefault("xbmcplugin", MagicMock())
sys.modules.setdefault("xbmcvfs", MagicMock())

import kinopoisk_api  # noqa: E402
from kinopoisk_api import (  # noqa: E402
    init_key_pool,
    get_current_api_key,
    rotate_key,
    is_all_keys_exhausted,
    KinopoiskClient,
)
from http_client import HttpError  # noqa: E402


def _reset_key_pool():
    """Reset module-level key rotation state between tests."""
    kinopoisk_api._key_pool = []
    kinopoisk_api._current_key_index = 0
    kinopoisk_api._exhausted_keys = set()
    kinopoisk_api._all_keys_exhausted = False
    kinopoisk_api._exhausted_notified = False


def _mock_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    return logger


class TestInitKeyPool:
    def setup_method(self):
        _reset_key_pool()

    def test_filters_empty_strings(self):
        """init_key_pool(['k1', '', 'k3']) -> pool = ['k1', 'k3']"""
        init_key_pool(["k1", "", "k3"])
        assert kinopoisk_api._key_pool == ["k1", "k3"]

    def test_noop_on_second_call(self):
        """Repeat call does not overwrite the pool."""
        init_key_pool(["k1", "k2"])
        init_key_pool(["k3", "k4"])
        assert kinopoisk_api._key_pool == ["k1", "k2"]

    def test_empty_keys(self):
        """init_key_pool(['', '']) -> empty pool."""
        init_key_pool(["", ""])
        assert kinopoisk_api._key_pool == []


class TestGetCurrentApiKey:
    def setup_method(self):
        _reset_key_pool()

    def test_returns_first_key(self):
        init_key_pool(["key_a", "key_b"])
        assert get_current_api_key() == "key_a"

    def test_returns_empty_when_no_pool(self):
        assert get_current_api_key() == ""


class TestRotateKey:
    def setup_method(self):
        _reset_key_pool()

    def test_advances_to_next_key(self):
        """After rotate_key the current key is the next one."""
        init_key_pool(["k1", "k2", "k3"])
        logger = _mock_logger()
        result = rotate_key(logger)
        assert result is True
        assert get_current_api_key() == "k2"

    def test_skips_exhausted_keys(self):
        """If #2 is already exhausted, jump to #3."""
        init_key_pool(["k1", "k2", "k3"])
        logger = _mock_logger()
        kinopoisk_api._exhausted_keys.add(1)  # k2 already exhausted
        rotate_key(logger)  # exhaust k1, skip k2, go to k3
        assert get_current_api_key() == "k3"

    def test_all_exhausted_returns_false(self):
        """With a single key rotate -> False."""
        init_key_pool(["only_key"])
        logger = _mock_logger()
        result = rotate_key(logger)
        assert result is False

    def test_sets_all_keys_exhausted_flag(self):
        init_key_pool(["only_key"])
        logger = _mock_logger()
        rotate_key(logger)
        assert is_all_keys_exhausted() is True

    def test_toast_on_switch(self):
        """On key switch xbmc.executebuiltin is called with exhaustion message."""
        init_key_pool(["k1", "k2"])
        logger = _mock_logger()
        xbmc_mock = sys.modules["xbmc"]
        xbmc_mock.executebuiltin = MagicMock()
        rotate_key(logger)
        xbmc_mock.executebuiltin.assert_called_once()
        call_arg = xbmc_mock.executebuiltin.call_args[0][0]
        assert "исчерпан" in call_arg

    def test_all_exhausted_toast_once(self):
        """Toast 'all keys exhausted' is shown only once."""
        init_key_pool(["k1"])
        logger = _mock_logger()
        xbmc_mock = sys.modules["xbmc"]
        xbmc_mock.executebuiltin = MagicMock()
        rotate_key(logger)  # first call -- sets _exhausted_notified
        call_count_1 = xbmc_mock.executebuiltin.call_count

        # Second call: pool already exhausted, trying again
        rotate_key(logger)
        call_count_2 = xbmc_mock.executebuiltin.call_count
        assert call_count_2 == call_count_1  # no new toast


class TestRequestWithRotation:
    def setup_method(self):
        _reset_key_pool()

    def test_retries_on_402(self):
        """Mock HttpClient -> 402 on key 1, 200 on key 2."""
        init_key_pool(["k1", "k2"])
        logger = _mock_logger()
        client = KinopoiskClient("k1", logger)

        # First call raises 402, second (after rotation) succeeds
        call_count = [0]

        def mock_get_json(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise HttpError(402, "Payment Required", "http://test")
            return {"films": []}

        client._http.get_json = mock_get_json
        # After rotation, _rebuild_http_clients creates new _http
        # We need to mock the rebuilt client too
        original_rebuild = client._rebuild_http_clients

        def mock_rebuild(new_key):
            original_rebuild(new_key)
            client._http.get_json = mock_get_json

        client._rebuild_http_clients = mock_rebuild

        result = client._request_with_rotation(
            False, "get_json", "v2.1/films/search-by-keyword", {"keyword": "test"}
        )
        assert result == {"films": []}
        assert call_count[0] == 2

    def test_retries_on_403(self):
        """Mock HttpClient -> 403 on key 1, 200 on key 2."""
        init_key_pool(["k1", "k2"])
        logger = _mock_logger()
        client = KinopoiskClient("k1", logger)

        call_count = [0]

        def mock_get_json(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise HttpError(403, "Forbidden", "http://test")
            return {"data": "ok"}

        client._http.get_json = mock_get_json
        original_rebuild = client._rebuild_http_clients

        def mock_rebuild(new_key):
            original_rebuild(new_key)
            client._http.get_json = mock_get_json

        client._rebuild_http_clients = mock_rebuild

        result = client._request_with_rotation(False, "get_json", "test/path")
        assert result == {"data": "ok"}
        assert call_count[0] == 2

    def test_all_exhausted_raises(self):
        """402 on the only key -> HttpError."""
        init_key_pool(["only_key"])
        logger = _mock_logger()
        client = KinopoiskClient("only_key", logger)
        client._http.get_json = MagicMock(
            side_effect=HttpError(402, "Payment Required", "http://test")
        )

        import pytest

        with pytest.raises(HttpError) as exc_info:
            client._request_with_rotation(False, "get_json", "test/path")
        assert exc_info.value.status_code == 402

    def test_non_402_error_passes_through(self):
        """404 does not trigger rotation."""
        init_key_pool(["k1", "k2"])
        logger = _mock_logger()
        client = KinopoiskClient("k1", logger)
        client._http.get_json = MagicMock(
            side_effect=HttpError(404, "Not Found", "http://test")
        )

        import pytest

        with pytest.raises(HttpError) as exc_info:
            client._request_with_rotation(False, "get_json", "test/path")
        assert exc_info.value.status_code == 404
        assert get_current_api_key() == "k1"  # key not rotated


class TestSettingsKinopoiskApiKeys:
    def test_multiple_keys(self):
        """Mock addon with 3 keys -> list of 3."""
        addon = MagicMock()

        def mock_get(key):
            mapping = {
                "kinopoisk_api_key": "aaa",
                "kinopoisk_api_key_2": "bbb",
                "kinopoisk_api_key_3": "ccc",
                "kinopoisk_api_key_4": "",
                "kinopoisk_api_key_5": "",
            }
            return mapping.get(key, "")

        addon.getSetting = mock_get
        addon.getSettingBool = MagicMock(return_value=False)
        addon.getSettingInt = MagicMock(return_value=0)

        from settings_manager import SettingsManager

        sm = SettingsManager(addon=addon)
        assert sm.kinopoisk_api_keys == ["aaa", "bbb", "ccc"]

    def test_single_key(self):
        """Only key1 -> list of 1 (AC-06)."""
        addon = MagicMock()

        def mock_get(key):
            if key == "kinopoisk_api_key":
                return "only_one"
            return ""

        addon.getSetting = mock_get
        addon.getSettingBool = MagicMock(return_value=False)
        addon.getSettingInt = MagicMock(return_value=0)

        from settings_manager import SettingsManager

        sm = SettingsManager(addon=addon)
        assert sm.kinopoisk_api_keys == ["only_one"]
        assert sm.kinopoisk_api_key == "only_one"  # legacy compat
