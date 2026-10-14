# -*- coding: utf-8 -*-
"""
Commit Refresher - Shows the values the database set when edits are saved.

A WFS-T insert only returns the new feature ids, so after saving QGIS keeps showing
the values it sent: columns the server fills in, such as created date and user or
generated attributes, stay empty until the layer is reloaded. The refresher reloads
UmeMap layers from the server once added or changed features have been committed.
"""

from typing import Callable, Dict, List, Set

from qgis.core import Qgis, QgsMapLayer, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QTimer

from ...core.wfs_utils import parse_wfs_data_source
from ...ui.utils import log


class CommitRefresher:
    """Reloads UmeMap layers from the server after added or changed features are saved."""

    def __init__(self, is_umemap_layer: Callable[[QgsMapLayer], bool]):
        """
        :param is_umemap_layer: Tells whether a layer comes from a UmeMap server
        """
        self._is_umemap_layer = is_umemap_layer
        self._connections: Dict[str, List[tuple]] = {}
        self._pending: Set[str] = set()

    def register_existing_layers(self) -> None:
        """Watch the layers that are already in the project."""
        for layer in QgsProject.instance().mapLayers().values():
            self.register_layer(layer)

    def register_layer(self, layer: QgsMapLayer) -> None:
        """Watch a layer for saved edits if it is a WFS layer."""
        if not isinstance(layer, QgsVectorLayer) or layer.id() in self._connections:
            return

        wfs_url, layer_name = parse_wfs_data_source(layer)
        if not wfs_url or not layer_name or layer_name.startswith("CodeList_"):
            return

        layer_id = layer.id()
        connections = [
            (layer.committedFeaturesAdded, lambda *_: self._pending.add(layer_id)),
            (layer.committedAttributeValuesChanges, lambda *_: self._pending.add(layer_id)),
            (layer.committedGeometriesChanges, lambda *_: self._pending.add(layer_id)),
            (layer.afterCommitChanges, lambda: self._on_after_commit(layer_id)),
            (layer.willBeDeleted, lambda: self.unregister_layer(layer_id)),
        ]
        for signal, slot in connections:
            signal.connect(slot)
        self._connections[layer_id] = [(layer, signal, slot) for signal, slot in connections]

    def unregister_layer(self, layer_id: str) -> None:
        """Stop watching a layer."""
        self._pending.discard(layer_id)
        for _layer, signal, slot in self._connections.pop(layer_id, []):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):  # nosec B110
                pass

    def unregister_all(self) -> None:
        """Stop watching all layers."""
        for layer_id in list(self._connections):
            self.unregister_layer(layer_id)

    def _on_after_commit(self, layer_id: str) -> None:
        if layer_id not in self._pending:
            return
        self._pending.discard(layer_id)

        # Reload once the commit has finished; reloading inside the commit signal
        # would interfere with QGIS clearing the edit buffer.
        QTimer.singleShot(0, lambda: self._reload(layer_id))

    def _reload(self, layer_id: str) -> None:
        layer = QgsProject.instance().mapLayer(layer_id)
        if not isinstance(layer, QgsVectorLayer):
            return

        # Unsaved edits made after the save would be lost, so leave the layer as it is
        if layer.isEditable() and layer.isModified():
            log(f"'{layer.name()}' has unsaved edits and was not reloaded from UmeMap.", Qgis.Info)
            return

        try:
            if not self._is_umemap_layer(layer):
                return

            layer.reload()
            layer.triggerRepaint()
            log(f"Reloaded '{layer.name()}' from UmeMap to show the values set by the database.", Qgis.Info)
        except Exception as e:
            log(f"[ERROR] Could not reload '{layer.name()}' after saving: {e}", Qgis.Warning)
