# -*- coding: utf-8 -*-
"""
Stored Value Display - Shows the stored value of a value map outside the editor.

QGIS shows a value map's description everywhere, so a role field whose list shows the
actor hierarchy ("Gator och Parker / Parkdrift") shows the whole hierarchy in the attribute
table too, although only "Parkdrift" is stored. Fields the server marks with the
``umemap_display`` option get a widget type that edits exactly like a value map but has
no field formatter of its own, so the table, identify results and labels show the stored
value while the form and the table editor still offer the hierarchical list.
"""

from typing import Dict, List

from qgis.core import QgsEditorWidgetSetup, QgsMapLayer, QgsProject, QgsVectorLayer
from qgis.gui import QgsEditorWidgetFactory, QgsGui

from ...ui.utils import log

WIDGET_TYPE = "UmeMapStoredValueMap"
VALUE_MAP_TYPE = "ValueMap"
DISPLAY_OPTION = "umemap_display"
DISPLAY_STORED_VALUE = "value"


class StoredValueMapWidgetFactory(QgsEditorWidgetFactory):
    """Creates value map editors for fields that show their stored value outside the editor."""

    def __init__(self):
        super().__init__("UmeMap Value Map (stored value)")

    def create(self, layer, fieldIdx, editor, parent):
        return _value_map_factory().create(layer, fieldIdx, editor, parent)

    def configWidget(self, layer, fieldIdx, parent):
        return _value_map_factory().configWidget(layer, fieldIdx, parent)

    def fieldScore(self, layer, fieldIdx):
        # Never picked automatically; only fields marked by the server get this widget.
        return 0


class StoredValueDisplay:
    """Switches marked value map fields to the stored value display, and back when the plugin unloads."""

    def __init__(self):
        self._switched: Dict[str, List[int]] = {}

    def register_existing_layers(self) -> None:
        """Apply the display to the layers that are already in the project."""
        for layer in QgsProject.instance().mapLayers().values():
            self.apply(layer)

    def apply(self, layer: QgsMapLayer) -> None:
        """Switch the marked value map fields of a layer, e.g. after it was added or its style replaced."""
        if not isinstance(layer, QgsVectorLayer):
            return

        switched: List[int] = []

        for index in range(layer.fields().count()):
            setup = layer.editorWidgetSetup(index)
            config = setup.config()

            if setup.type() == WIDGET_TYPE:
                switched.append(index)
            elif setup.type() == VALUE_MAP_TYPE and config.get(DISPLAY_OPTION) == DISPLAY_STORED_VALUE:
                layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup(WIDGET_TYPE, config))
                switched.append(index)

        if not switched:
            self._switched.pop(layer.id(), None)
            return

        if layer.id() not in self._switched:
            layer.willBeDeleted.connect(lambda lid=layer.id(): self._switched.pop(lid, None))
        self._switched[layer.id()] = switched
        log(f"StoredValueDisplay: Showing stored values for {len(switched)} field(s) in '{layer.name()}'")

    def restore_all(self) -> None:
        """Give the switched fields their value map widget back, so they work without the plugin."""
        project = QgsProject.instance()

        for layer_id, indexes in self._switched.items():
            layer = project.mapLayer(layer_id)
            if not isinstance(layer, QgsVectorLayer):
                continue

            for index in indexes:
                setup = layer.editorWidgetSetup(index)
                if setup.type() == WIDGET_TYPE:
                    layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup(VALUE_MAP_TYPE, setup.config()))

        self._switched.clear()


def _value_map_factory() -> QgsEditorWidgetFactory:
    return QgsGui.editorWidgetRegistry().factory(VALUE_MAP_TYPE)
