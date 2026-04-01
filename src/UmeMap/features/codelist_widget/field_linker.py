# -*- coding: utf-8 -*-
"""
Field Linker - Layer-level handler for CodeList field linking in attribute table.

In form mode, field linking is handled by the editforminit Python code (for ValueMap)
and the widget wrapper (for UmeMapCodeListSearch). But in attribute table mode, neither
mechanism fires. This module connects to the layer's attributeValueChanged signal to
handle field linking regardless of editing mode.

It reads linked_fields and value_links from widget configs (both ValueMap and
UmeMapCodeListSearch) and updates linked fields via layer.changeAttributeValue().
"""

import json
from typing import Any, Dict, List, Optional, Set

from qgis.core import QgsVectorLayer, QgsEditorWidgetSetup

from ...ui.utils import log


class FieldLinker:
    """Manages CodeList field linking for a single layer."""

    def __init__(self, layer: QgsVectorLayer):
        self._layer = layer
        # Map from field index -> list of {fieldName, columnName, value_links}
        self._field_links: Dict[int, List[Dict[str, Any]]] = {}
        # Guard against recursive updates
        self._updating = False

    def setup(self) -> bool:
        """Scan widget configs and connect signal. Returns True if any links were found."""
        fields = self._layer.fields()

        for i in range(fields.count()):
            field_name = fields.at(i).name()
            widget_setup: QgsEditorWidgetSetup = self._layer.editorWidgetSetup(i)
            config = widget_setup.config()

            linked_fields_json = config.get("linked_fields", "")
            if not linked_fields_json:
                continue

            try:
                linked_fields: List[Dict[str, str]] = json.loads(linked_fields_json)
            except (json.JSONDecodeError, TypeError):
                continue

            if not linked_fields:
                continue

            # Parse value_links if available (ValueMap widgets)
            value_links: Optional[Dict[str, Dict[str, str]]] = None
            value_links_json = config.get("value_links", "")
            if value_links_json:
                try:
                    value_links = json.loads(value_links_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            self._field_links[i] = {
                "linked_fields": linked_fields,
                "value_links": value_links,
            }

        if not self._field_links:
            return False

        self._layer.attributeValueChanged.connect(self._on_attribute_value_changed)
        return True

    def teardown(self) -> None:
        """Disconnect signal."""
        try:
            self._layer.attributeValueChanged.disconnect(self._on_attribute_value_changed)
        except Exception:
            pass
        self._field_links.clear()

    def _on_attribute_value_changed(self, fid: int, idx: int, value: Any) -> None:
        """Handle attribute value changes and update linked fields."""
        if self._updating:
            return

        link_info = self._field_links.get(idx)
        if not link_info:
            return

        linked_fields: List[Dict[str, str]] = link_info["linked_fields"]
        value_links: Optional[Dict[str, Dict[str, str]]] = link_info["value_links"]

        if not value_links:
            return

        str_value = str(value) if value is not None else ""
        linked_values = value_links.get(str_value)
        if not linked_values:
            return

        self._updating = True
        try:
            fields = self._layer.fields()
            for link in linked_fields:
                column_name = link.get("columnName", "")
                field_name = link.get("fieldName", "")
                if not column_name or not field_name:
                    continue

                linked_value = linked_values.get(column_name)
                if linked_value is None:
                    continue

                target_idx = fields.indexOf(field_name)
                if target_idx >= 0:
                    self._layer.changeAttributeValue(fid, target_idx, linked_value)
        finally:
            self._updating = False


class FieldLinkerRegistry:
    """Manages FieldLinker instances across all layers."""

    def __init__(self):
        self._linkers: Dict[str, FieldLinker] = {}  # layer id -> FieldLinker

    def register_layer(self, layer: QgsVectorLayer) -> None:
        """Check layer for codelist field links and register if any found."""
        if not isinstance(layer, QgsVectorLayer):
            return

        # Skip if already registered
        if layer.id() in self._linkers:
            return

        linker = FieldLinker(layer)
        if linker.setup():
            self._linkers[layer.id()] = linker
            log(f"FieldLinker: Registered field linking for layer '{layer.name()}'")

            # Clean up when layer is removed
            layer.willBeDeleted.connect(lambda lid=layer.id(): self._unregister_layer(lid))

    def _unregister_layer(self, layer_id: str) -> None:
        """Remove linker for a layer."""
        linker = self._linkers.pop(layer_id, None)
        if linker:
            linker.teardown()

    def unregister_all(self) -> None:
        """Clean up all linkers."""
        for linker in self._linkers.values():
            linker.teardown()
        self._linkers.clear()
