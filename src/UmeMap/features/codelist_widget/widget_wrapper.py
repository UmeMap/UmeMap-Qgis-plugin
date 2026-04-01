# -*- coding: utf-8 -*-
"""
CodeList Widget Wrapper - Searchable autocomplete for large CodeLists.

Instead of loading all values upfront (like ValueRelation), this widget
queries the UmeMap server as the user types, with debounce and lazy-loading.
Designed for CodeLists with 124k+ entries.

Supports field linking: when two UmeMapCodeListSearch widgets share the same
CodeList (e.g. Latin name ↔ Swedish name), selecting a value in one widget
automatically updates the linked widget.
"""

import json
from typing import Any, Dict, List, Optional

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
        self._results_map: Dict[str, Dict[str, Any]] = {}  # title -> full result object
        self._valid_value: Optional[str] = None  # Last value selected from list or loaded from DB
        self._feature_id = None  # Feature ID set by QGIS via setFeature()
        self._completer_just_activated = False  # True between completer activation and next setValue()

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
        self._widget.editingFinished.connect(self._on_editing_finished)

        return self._widget

    def initWidget(self, editor):
        if isinstance(editor, QLineEdit):
            self._widget = editor

    def valid(self):
        return self._widget is not None

    def value(self):
        if self._widget:
            text = self._widget.text()
            if not text or text == "(no selection)":
                return None
            # If the completer was recently activated, trust the widget text
            if self._completer_just_activated:
                return text
            # Only return the value if it was selected from the list or loaded from DB
            if self._valid_value is not None and text == self._valid_value:
                return text
            # If text doesn't match a valid value, return the original DB value
            log(f"UmeMapCodeListSearch: value() falling back to _current_value='{self._current_value}' "
                f"(text='{text}', _valid_value='{self._valid_value}')")
            return self._current_value
        return None

    def setEnabled(self, enabled):
        if self._widget:
            self._widget.setEnabled(enabled)

    def setValue(self, value):
        self._current_value = value
        self._completer_just_activated = False  # Reset on new value from QGIS
        text = str(value) if value and str(value) != "NULL" else ""
        self._valid_value = text if text else None
        if self._widget:
            self._ignore_text_change = True
            self._widget.setText(text)
            self._widget.setStyleSheet("")
            self._ignore_text_change = False

    def setFeature(self, feature):
        """Called by QGIS when the widget is associated with a feature (form and table mode)."""
        super().setFeature(feature)
        self._feature_id = feature.id() if feature and feature.isValid() else None
        log(f"UmeMapCodeListSearch: setFeature called, feature_id={self._feature_id}")

    def _on_completer_activated(self, text: str) -> None:
        """Called when user selects an item from the completer popup (Enter or click)."""
        self._ignore_text_change = True
        self._valid_value = text
        self._completer_just_activated = True
        if self._widget:
            self._widget.setText(text)
            self._widget.setStyleSheet("")
        self._ignore_text_change = False
        self._timer.stop()  # Cancel any pending search
        self.emitValueChanged()  # Notify QGIS that the value changed

        # In attribute table mode, also write own value directly to the edit buffer.
        # QGIS may call value() after the widget is destroyed/reset, getting wrong value.
        layer = self.layer()
        if layer and layer.isEditable() and self._feature_id is not None:
            my_field_idx = self.fieldIdx()
            if my_field_idx >= 0:
                layer.changeAttributeValue(self._feature_id, my_field_idx, text)
                log(f"UmeMapCodeListSearch: Wrote own value '{text}' to edit buffer (fid={self._feature_id}, field={my_field_idx})")

        # Update linked fields if configured
        self._update_linked_fields(text)

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

    def _on_editing_finished(self) -> None:
        """Validate the entered text when the widget loses focus or Enter is pressed."""
        if not self._widget or self._ignore_text_change:
            return

        # If completer was just activated, trust that value — don't invalidate
        if self._completer_just_activated:
            return

        # If completer popup is visible or has a current selection, Enter will trigger
        # editingFinished BEFORE activated. Don't invalidate yet — activated will follow.
        if (self._completer and self._completer.popup()
                and self._completer.popup().isVisible()):
            return

        text = self._widget.text()
        if not text:
            # Empty is fine - clear validation state
            self._valid_value = None
            self._widget.setStyleSheet("")
            return

        if self._valid_value is not None and text == self._valid_value:
            # Text matches a valid value - all good
            self._widget.setStyleSheet("")
            return

        # Check if text matches any result from the last search (user typed exact match)
        if text in self._results_map:
            self._valid_value = text
            self._completer_just_activated = True
            self._widget.setStyleSheet("")
            self.emitValueChanged()
            self._update_linked_fields(text)
            return

        # Text doesn't match a valid value - mark as invalid with red border
        self._widget.setStyleSheet("QLineEdit { border: 2px solid red; }")
        log(f"UmeMapCodeListSearch: '{text}' är inte ett giltigt värde. Välj ett värde från listan.")

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
        codelist_title = config.get("codelist", "")
        column_name = config.get("column_name", "")

        if not wfs_url or not codelist_title:
            log("UmeMapCodeListSearch: Missing wfs_url or codelist in widget config.")
            return

        auth_headers = self._get_auth_headers()

        try:
            url = (
                f"{wfs_url}?REQUEST=SearchCodeList"
                f"&codeListTitle={codelist_title}"
                f"&Q={text}"
                f"&LIMIT={self.SEARCH_LIMIT}"
            )
            if column_name:
                url += f"&columnName={column_name}"

            response = requests.get(
                url,
                headers=auth_headers,
                verify=False,
                timeout=5
            )
            if response.status_code == 200:
                results = response.json()
                titles = [item["title"] for item in results]

                # Store full result objects for linked field lookups
                self._results_map = {item["title"]: item for item in results}

                self._model.setStringList(titles)
                self._last_search_text = text
                self._completer.complete()
        except Exception as e:
            log(f"UmeMapCodeListSearch: Search failed: {e}")

    def _update_linked_fields(self, selected_title: str) -> None:
        """Update linked UmeMapCodeListSearch fields when a value is selected.

        Works in two modes:
        - Form mode (Feature Attributes dialog): finds sibling widgets and updates them directly
        - Table mode (Attribute Table): uses layer.changeAttributeValue() to update linked fields
        """
        config = self.config()
        linked_fields_json = config.get("linked_fields", "")
        if not linked_fields_json:
            log(f"UmeMapCodeListSearch: No linked_fields config, skipping")
            return

        result = self._results_map.get(selected_title)
        if not result:
            log(f"UmeMapCodeListSearch: No result found for '{selected_title}' in results_map (keys: {list(self._results_map.keys())[:5]})")
            return

        linked_values = result.get("linkedValues")
        if not linked_values:
            log(f"UmeMapCodeListSearch: No linkedValues in result for '{selected_title}'")
            return

        try:
            linked_fields: List[Dict[str, str]] = json.loads(linked_fields_json)
        except (json.JSONDecodeError, TypeError):
            log(f"UmeMapCodeListSearch: Failed to parse linked_fields config: {linked_fields_json}")
            return

        log(f"UmeMapCodeListSearch: Updating linked fields for '{selected_title}', "
            f"linked_fields={linked_fields}, linkedValues keys={list(linked_values.keys())}")

        # Walk up the widget hierarchy to find QgsAttributeForm.
        # In form mode (Feature Attributes dialog), QgsAttributeForm exists as a parent.
        # In attribute table mode, it does NOT — we must use layer.changeAttributeValue().
        # IMPORTANT: Do NOT fallback to window() — findChild on the window would find
        # widgets from OTHER rows in the attribute table, updating the wrong feature.
        form = self._widget
        while form:
            class_name = type(form).__name__
            if class_name == "QgsAttributeForm" or form.objectName().startswith("QgsAttributeForm"):
                break
            form = form.parentWidget()

        is_form_mode = form is not None
        log(f"UmeMapCodeListSearch: Mode={'form' if is_form_mode else 'table'}, "
            f"form_class={type(form).__name__ if form else 'None'}")

        for link in linked_fields:
            field_name = link.get("fieldName", "")
            column_name = link.get("columnName", "")
            if not field_name or not column_name:
                continue

            # Resolve the linked value: check alt values first, then primary title
            linked_value = linked_values.get(column_name) or linked_values.get("__primary__", "")

            log(f"UmeMapCodeListSearch: Link '{column_name}' -> '{field_name}': "
                f"value='{linked_value}' (tried key '{column_name}', fallback '__primary__')")

            # Skip if no linked value found
            if not linked_value:
                log(f"UmeMapCodeListSearch: No linked value found for '{column_name}', skipping")
                continue

            updated_via_widget = False

            # Form mode: find sibling widget in the QgsAttributeForm
            if is_form_mode:
                sibling = form.findChild(QLineEdit, field_name)
                if sibling:
                    sibling.setText(linked_value)
                    # Mark the linked widget's value as valid (it was set programmatically)
                    sibling_wrapper = self._find_widget_wrapper(sibling)
                    if sibling_wrapper and hasattr(sibling_wrapper, '_valid_value'):
                        sibling_wrapper._valid_value = linked_value
                        sibling.setStyleSheet("")
                    updated_via_widget = True
                    log(f"UmeMapCodeListSearch: Updated '{field_name}' via form widget")
                else:
                    log(f"UmeMapCodeListSearch: Sibling widget '{field_name}' not found in form")

            # Fallback for attribute table mode: update via layer editing buffer
            if not updated_via_widget:
                try:
                    layer = self.layer()
                    feature_id = self._resolve_feature_id(layer)

                    log(f"UmeMapCodeListSearch: Fallback mode - feature_id={feature_id}, "
                        f"layer={layer.name() if layer else None}, editable={layer.isEditable() if layer else False}")
                    if layer and layer.isEditable() and feature_id is not None:
                        field_idx = layer.fields().indexOf(field_name)
                        if field_idx >= 0:
                            layer.changeAttributeValue(feature_id, field_idx, linked_value)
                            log(f"UmeMapCodeListSearch: Updated '{field_name}' = '{linked_value}' via layer (fid={feature_id})")
                        else:
                            log(f"UmeMapCodeListSearch: Field '{field_name}' not found in layer fields")
                    else:
                        log(f"UmeMapCodeListSearch: Cannot update - layer={layer is not None}, "
                            f"editable={layer.isEditable() if layer else 'N/A'}, feature_id={feature_id}")
                except Exception as e:
                    log(f"UmeMapCodeListSearch: Fallback failed for '{field_name}': {e}")

    def _resolve_feature_id(self, layer) -> Optional[int]:
        """Try multiple strategies to get the current feature ID.

        In form mode, setFeature() is called before editing starts.
        In attribute table mode, setFeature() may be called AFTER the value is selected,
        so we need alternative strategies.
        """
        # 1. From setFeature() - works in form mode, sometimes in table mode
        if self._feature_id is not None:
            log(f"UmeMapCodeListSearch: feature_id={self._feature_id} from setFeature()")
            return self._feature_id

        # 2. From context formFeature - works in form mode
        try:
            ctx = self.context()
            if ctx:
                feat = ctx.formFeature()
                if feat and feat.isValid():
                    fid = feat.id()
                    log(f"UmeMapCodeListSearch: feature_id={fid} from context.formFeature()")
                    return fid
        except Exception:
            pass

        # 3. From edit buffer - the current field's value was just changed via emitValueChanged(),
        #    so the feature should be in the buffer's changedAttributeValues
        if layer and layer.isEditable():
            buf = layer.editBuffer()
            if buf:
                changed = buf.changedAttributeValues()
                if changed:
                    # Our field index should be in the most recently changed feature
                    my_field_idx = self.fieldIdx()
                    for fid in reversed(list(changed.keys())):
                        if my_field_idx in changed[fid]:
                            log(f"UmeMapCodeListSearch: feature_id={fid} from edit buffer (matched field {my_field_idx})")
                            return fid
                    # Fallback: use the last changed feature
                    fid = list(changed.keys())[-1]
                    log(f"UmeMapCodeListSearch: feature_id={fid} from edit buffer (last changed)")
                    return fid

        log("UmeMapCodeListSearch: Could not resolve feature_id")
        return None

    @staticmethod
    def _find_widget_wrapper(widget: QLineEdit) -> Optional["UmeMapCodeListWidgetWrapper"]:
        """Find the UmeMapCodeListWidgetWrapper associated with a QLineEdit widget."""
        wrapper = QgsEditorWidgetWrapper.fromWidget(widget)
        if isinstance(wrapper, UmeMapCodeListWidgetWrapper):
            return wrapper
        return None

    def _get_auth_headers(self) -> Dict[str, str]:
        """Extract authentication headers from the layer's auth configuration."""
        layer = self.layer()
        if not layer:
            return {}
        return AuthManager.get_headers_from_layer(layer)
