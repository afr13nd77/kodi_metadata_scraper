import sys
import os
from unittest.mock import MagicMock

# Addon entry point
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "python"))
# Shared modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "shared"))

kodi_modules = ["xbmc", "xbmcgui", "xbmcplugin", "xbmcaddon", "xbmcvfs"]
for mod in kodi_modules:
    sys.modules[mod] = MagicMock()
