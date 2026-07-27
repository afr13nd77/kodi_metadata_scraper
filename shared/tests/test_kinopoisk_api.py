from __future__ import annotations

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
sys.modules.setdefault("xbmcplugin", MagicMock())
sys.modules.setdefault("xbmcvfs", MagicMock())

from kinopoisk_api import map_production_status  # noqa: E402


def _mock_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    return logger


class TestMapProductionStatus:

    def test_production_status_completed(self):
        """productionStatus='COMPLETED' -> 'Ended'."""
        result = map_production_status({"productionStatus": "COMPLETED"}, _mock_logger())
        assert result == "Ended"

    def test_production_status_filming(self):
        """productionStatus='FILMING' -> 'In Production'."""
        result = map_production_status({"productionStatus": "FILMING"}, _mock_logger())
        assert result == "In Production"

    def test_production_status_pre_production(self):
        """productionStatus='PRE_PRODUCTION' -> 'In Production'."""
        result = map_production_status({"productionStatus": "PRE_PRODUCTION"}, _mock_logger())
        assert result == "In Production"

    def test_production_status_post_production(self):
        """productionStatus='POST_PRODUCTION' -> 'In Production'."""
        result = map_production_status({"productionStatus": "POST_PRODUCTION"}, _mock_logger())
        assert result == "In Production"

    def test_production_status_announced(self):
        """productionStatus='ANNOUNCED' -> 'Planned'."""
        result = map_production_status({"productionStatus": "ANNOUNCED"}, _mock_logger())
        assert result == "Planned"

    def test_production_status_unknown(self):
        """Unknown productionStatus -> '' + warning."""
        logger = _mock_logger()
        result = map_production_status({"productionStatus": "UNKNOWN_VALUE"}, logger)
        assert result == ""
        logger.warning.assert_called_once()

    def test_completed_true(self):
        """productionStatus=None, completed=True -> 'Ended'."""
        result = map_production_status({"productionStatus": None, "completed": True}, _mock_logger())
        assert result == "Ended"

    def test_completed_false(self):
        """productionStatus=None, completed=False -> 'Returning Series'."""
        result = map_production_status({"productionStatus": None, "completed": False}, _mock_logger())
        assert result == "Returning Series"

    def test_no_fields(self):
        """Empty dict {} -> ''."""
        result = map_production_status({}, _mock_logger())
        assert result == ""

    def test_production_status_null_completed_none(self):
        """productionStatus=None, no completed field -> ''."""
        result = map_production_status({"productionStatus": None}, _mock_logger())
        assert result == ""

    def test_production_status_priority(self):
        """productionStatus='COMPLETED' + completed=False -> 'Ended' (productionStatus wins)."""
        result = map_production_status(
            {"productionStatus": "COMPLETED", "completed": False}, _mock_logger()
        )
        assert result == "Ended"

    def test_no_logger(self):
        """Function works without logger."""
        result = map_production_status({"completed": True})
        assert result == "Ended"

    def test_no_logger_warning(self):
        """Function works without logger on unknown status."""
        result = map_production_status({"productionStatus": "WEIRD"})
        assert result == ""
