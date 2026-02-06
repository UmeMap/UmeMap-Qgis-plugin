# -*- coding: utf-8 -*-
"""
Layer Browser module - Dockable WFS layer browser panel.

Provides a hierarchical browser for discovering and loading WFS layers
organized by keyword folders with drag-and-drop, search, and authentication support.

Note: This module uses QgsNetworkAccessManager for async HTTP requests
(unlike style_manager which uses sync 'requests'). This is intentional
to avoid blocking the QGIS UI during GetCapabilities fetching which can
be slow for large WFS services.
"""

import os

from .browser_dock import BrowserDock

# Icon directory for layer browser resources
ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons')
