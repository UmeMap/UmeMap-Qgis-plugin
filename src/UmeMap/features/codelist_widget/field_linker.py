# -*- coding: utf-8 -*-
"""
Field Linker - Layer-level handler for CodeList field linking in attribute table.

In form mode, field linking is handled by:
- editforminit Python code (for ValueMap widgets like Datafångstmetod → kod)
- widget wrapper (for UmeMapCodeListSearch widgets like Artnamn latin ↔ svenska)

In attribute table mode, editforminit never fires. This module handles linking
via the layer's attributeValueChanged signal for:
- ValueMap owner fields → read-only linked text fields (e.g. Datafångstmetod → kod)
- UmeMapCodeListSearch fields are handled by widget_wrapper directly
"""

import json
from typing import Any, Dict, List, Optional

from qgis.core import QgsVectorLayer, QgsEditorWidgetSetup

from ...ui.utils import log


class FieldLinker:
    """Manages CodeList field linking for a single layer."""

    def __init__(self, layer: QgsVectorLayer):
        self._layer = layer
        self._field_links: Dict[int, Dict[str, Any]] = {}
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

            # Parse value_links if available (ValueMap owner fields)
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
            log(f"FieldLinker: Field '{field_name}' (idx={i}, type={widget_setup.type()}): "
                f"linked_fields={linked_fields}, "
                f"has_value_links={value_links is not None}")

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
            # UmeMapCodeListSearch fields don't have value_links —
            # their linking is handled by the widget wrapper directly
            return

        str_value = str(value) if value is not None else ""
        linked_values = value_links.get(str_value)
        if not linked_values:
            log(f"FieldLinker: No mapping for '{str_value}' "
                f"(sample keys: {list(value_links.keys())[:3]})")
            return

        log(f"FieldLinker: Field idx={idx} changed to '{str_value}', "
            f"updating: {linked_values}")

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
                    log(f"FieldLinker: Updated '{field_name}' = '{linked_value}' (fid={fid})")
        finally:
            self._updating = False


class FieldLinkerRegistry:
    """Manages FieldLinker instances across all layers."""

    def __init__(self):
        self._linkers: Dict[str, FieldLinker] = {}

    def register_layer(self, layer: QgsVectorLayer) -> None:
        """Check layer for codelist field links and register if any found."""
        if not isinstance(layer, QgsVectorLayer):
            return

        if layer.id() in self._linkers:
            return

        linker = FieldLinker(layer)
        if linker.setup():
            self._linkers[layer.id()] = linker
            log(f"FieldLinker: Registered field linking for layer '{layer.name()}'")

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
