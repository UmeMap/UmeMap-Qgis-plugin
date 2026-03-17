# -*- coding: utf-8 -*-
"""
CodeList Widget Wrapper - Searchable autocomplete for large CodeLists.

Instead of loading all values upfront (like ValueRelation), this widget
queries the UmeMap server as the user types, with debounce and lazy-loading.
Designed for CodeLists with 124k+ entries.
"""

from typing import Dict, Optional

import requests

from qgis.gui import QgsEditorWidgetWrapper
from qgis.PyQt.QtCore import Qt, QStringListModel, QTimer
from qgis.PyQt.QtWidgets import QCompleter, QLineEdit

from ...core.auth_manager import AuthManager
from ...ui.utils import log


class UmeMapCodeListWidgetWrapper(QgsEditorWidgetWrapper):
    """Editor widget wrapper that provides searchable autocomplete for CodeLists."""

    # Minimum characters required before triggering a search
    MIN_SEARCH_LENGTH = 2

    # Debounce interval in milliseconds
    DEBOUNCE_MS = 300

    # Maximum number of results to request from the server
    SEARCH_LIMIT = 50

    def __init__(self, layer, fieldIdx, editor, parent):
        super().__init__(layer, fieldIdx, editor, parent)
        self._widget: Optional[QLineEdit] = None
        self._completer: Optional[QCompleter] = None
        self._timer: Optional[QTimer] = None
        self._model: Optional[QStringListModel] = None
        self._current_value = None
        self._ignore_text_change = False  # Prevents re-search when completer sets text
        self._last_search_text = ""  # Track what we last searched for

    def createWidget(self, parent):
        self._widget = QLineEdit(parent)
        self._widget.setPlaceholderText("Skriv för att söka...")

        # Setup autocomplete model and completer
        self._model = QStringListModel()
        self._completer = QCompleter(self._model, self._widget)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setMaxVisibleItems(15)
        self._widget.setCompleter(self._completer)

        # When user selects from the popup (Enter or click), set the value
        self._completer.activated.connect(self._on_completer_activated)

        # Debounce timer - wait after last keystroke before searching
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DEBOUNCE_MS)
        self._timer.timeout.connect(self._do_search)

        self._widget.textChanged.connect(self._on_text_changed)

        return self._widget

    def initWidget(self, editor):
        if isinstance(editor, QLineEdit):
            self._widget = editor

    def valid(self):
        return self._widget is not None

    def value(self):
        if self._widget:
            text = self._widget.text()
            return text if text and text != "(no selection)" else None
        return None

    def setEnabled(self, enabled):
        if self._widget:
            self._widget.setEnabled(enabled)

    def setValue(self, value):
        self._current_value = value
        if self._widget:
            self._ignore_text_change = True
            self._widget.setText(str(value) if value and str(value) != "NULL" else "")
            self._ignore_text_change = False

    def _on_completer_activated(self, text: str) -> None:
        """Called when user selects an item from the completer popup (Enter or click)."""
        self._ignore_text_change = True
        if self._widget:
            self._widget.setText(text)
        self._ignore_text_change = False
        self._timer.stop()  # Cancel any pending search
        self.emitValueChanged()  # Notify QGIS that the value changed

    def _on_text_changed(self, text: str) -> None:
        """Handle text changes with debounce. Ignores changes from completer navigation."""
        if self._ignore_text_change:
            return

        # When the completer popup is visible and user navigates with arrow keys,
        # Qt updates the text field. Don't trigger a new search in that case.
        if self._completer and self._completer.popup() and self._completer.popup().isVisible():
            return

        if len(text) >= self.MIN_SEARCH_LENGTH:
            self._timer.start()  # Restart debounce timer
        else:
            self._model.setStringList([])
            self._last_search_text = ""

    def _do_search(self) -> None:
        """Execute the CodeList search against the UmeMap server."""
        text = self._widget.text() if self._widget else ""
        if len(text) < self.MIN_SEARCH_LENGTH:
            return

        # Skip if we already searched for this exact text
        if text == self._last_search_text:
            return

        config = self.config()
        wfs_url = config.get("wfs_url", "")
        codelist_guid = config.get("codelist_guid", "")

        if not wfs_url or not codelist_guid:
            log("UmeMapCodeListSearch: Missing wfs_url or codelist_guid in widget config.")
            return

        auth_headers = self._get_auth_headers()

        try:
            url = (
                f"{wfs_url}?REQUEST=SearchCodeList"
                f"&CODELIST={codelist_guid}"
                f"&Q={text}"
                f"&LIMIT={self.SEARCH_LIMIT}"
            )
            response = requests.get(
                url,
                headers=auth_headers,
                verify=False,
                timeout=5
            )
            if response.status_code == 200:
                results = response.json()
                titles = [item["title"] for item in results]
                self._model.setStringList(titles)
                self._last_search_text = text
                self._completer.complete()
        except Exception as e:
            log(f"UmeMapCodeListSearch: Search failed: {e}")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Extract authentication headers from the layer's auth configuration."""
        layer = self.layer()
        if not layer:
            return {}
        return AuthManager.get_headers_from_layer(layer)
