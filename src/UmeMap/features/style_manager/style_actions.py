# -*- coding: utf-8 -*-
"""
Style Actions - Context menu and toolbar actions for style management.
"""

import os
from typing import Callable, List, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QApplication, QMessageBox
from qgis.core import Qgis, QgsMapLayer, QgsMapLayerType

from .style_service import StyleService
from ...ui.utils import show_error_popup


ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "icons")


class StyleActions:
    """Manages context menu and toolbar actions for style operations."""

    # Object names used to find orphaned actions from a previous plugin instance
    SAVE_ACTION_NAME = "UmeMapSaveStyleAction"
    UPDATE_ACTION_NAME = "UmeMapUpdateStyleAction"

    def __init__(
        self,
        qgis_iface,
        style_service: StyleService,
        tr_func: Optional[Callable[[str], str]] = None,
        on_style_updated: Optional[Callable[[QgsMapLayer], None]] = None,
    ):
        """
        Initialize StyleActions.

        :param qgis_iface: QGIS interface instance
        :param style_service: Shared StyleService instance
        :param tr_func: Translation function for i18n support
        :param on_style_updated: Called with the layer after its style has been replaced
        """
        self.iface = qgis_iface
        self._tr = tr_func or (lambda x: x)
        self.style_service = style_service
        self._on_style_updated = on_style_updated
        self._layer_actions: List[QAction] = []
        self.update_all_action: Optional[QAction] = None

    def register(self) -> None:
        """
        Register the layer context menu actions ("Save Style To UmeMap" and
        "Update Style From UmeMap") and create the "Update Styles On All UmeMap
        Layers" action, which the plugin adds to its toolbar and menu.

        Removes any stale actions from a previous plugin instance first
        to prevent duplicates after reinstalling without restarting QGIS.
        """
        self._remove_stale_actions()

        update_action = self._create_action(
            "style_update.svg", self._tr("Update Style From UmeMap"),
            self.UPDATE_ACTION_NAME, self._on_update_style)
        save_action = self._create_action(
            "style_save.svg", self._tr("Save Style To UmeMap"),
            self.SAVE_ACTION_NAME, self._on_save_style)

        for action in (update_action, save_action):
            self.iface.addCustomActionForLayerType(action, "", QgsMapLayerType.VectorLayer, True)
            self._layer_actions.append(action)

        self.update_all_action = self._create_action(
            "style_update_all.svg", self._tr("Update Styles On All UmeMap Layers"),
            "", self._on_update_all_styles)

    def _create_action(self, icon_name: str, text: str, object_name: str, callback) -> QAction:
        """Create a QAction with an icon from the plugin's icons folder."""
        action = QAction(QIcon(os.path.join(ICONS_DIR, icon_name)), text, self.iface.mainWindow())
        if object_name:
            action.setObjectName(object_name)
        action.triggered.connect(callback)
        return action

    def _remove_stale_actions(self) -> None:
        """Remove any orphaned layer context menu actions from previous instances."""
        # First, remove our own actions if present
        self.unregister()

        # Find and remove orphaned actions by objectName from previous instances
        main_window = self.iface.mainWindow()
        for name in (self.SAVE_ACTION_NAME, self.UPDATE_ACTION_NAME):
            for action in main_window.findChildren(QAction, name):
                self.iface.removeCustomActionForLayerType(action)
                action.deleteLater()

    def unregister(self) -> None:
        """Remove the context menu actions."""
        for action in self._layer_actions:
            self.iface.removeCustomActionForLayerType(action)
            action.deleteLater()
        self._layer_actions.clear()

        if self.update_all_action:
            self.update_all_action.deleteLater()
            self.update_all_action = None

    def _on_save_style(self) -> None:
        """Handler for Save Style To UmeMap action."""
        current_layer = self.iface.activeLayer()

        if not current_layer:
            show_error_popup(
                self._tr("Save styles - Error"),
                self._tr("No active layer selected.")
            )
            return

        result = self.style_service.save_to_server(current_layer)

        if result.status == "success":
            self.iface.messageBar().pushMessage(
                self._tr("Save"),
                self._tr("Saved styles"),
                level=Qgis.Success,
                duration=5
            )
        else:
            if result.code == "AUTH_ERROR":
                show_error_popup(
                    self._tr("Authentication error"),
                    self._tr("The API key is invalid or missing. Please check your authentication configuration.")
                )
            else:
                show_error_popup(
                    self._tr("Save styles - Error"),
                    result.message
                )

    def _on_update_style(self) -> None:
        """Handler for Update Style From UmeMap action (layer context menu)."""
        layer = self.iface.activeLayer()

        if not layer:
            show_error_popup(
                self._tr("Update style - Error"),
                self._tr("No active layer selected.")
            )
            return

        if not self.style_service.is_umemap_layer(layer):
            show_error_popup(
                self._tr("Update style - Error"),
                self._tr("The layer is not a UmeMap layer.")
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success = self._update_layer_style(layer)
        finally:
            QApplication.restoreOverrideCursor()

        if success:
            self.iface.messageBar().pushMessage(
                self._tr("Update style"),
                self._tr("Style updated on '{0}'.").format(layer.name()),
                level=Qgis.Success,
                duration=5
            )
        else:
            self.iface.messageBar().pushMessage(
                self._tr("Update style"),
                self._tr("Could not update style on '{0}'. See the UmeMap log for details.").format(layer.name()),
                level=Qgis.Warning,
                duration=10
            )

    def _on_update_all_styles(self) -> None:
        """Handler for Update Styles On All UmeMap Layers action (toolbar/menu)."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layers = self.style_service.umemap_layers()
        finally:
            QApplication.restoreOverrideCursor()

        if not layers:
            self.iface.messageBar().pushMessage(
                self._tr("Update style"),
                self._tr("No UmeMap layers in the project."),
                level=Qgis.Info,
                duration=5
            )
            return

        answer = QMessageBox.question(
            self.iface.mainWindow(),
            self._tr("Update style"),
            self._tr("Update the style on {0} UmeMap layers from the server?\n\n"
                     "Symbology and other settings made in QGIS will be replaced.").format(len(layers)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            updated = sum(1 for layer in layers if self._update_layer_style(layer))
        finally:
            QApplication.restoreOverrideCursor()

        self.iface.messageBar().pushMessage(
            self._tr("Update style"),
            self._tr("Style updated on {0} of {1} UmeMap layers.").format(updated, len(layers)),
            level=Qgis.Success if updated == len(layers) else Qgis.Warning,
            duration=5
        )

    def _update_layer_style(self, layer: QgsMapLayer) -> bool:
        """Replace a layer's style from the server and notify listeners."""
        if not self.style_service.update_style(layer):
            return False

        if self._on_style_updated:
            self._on_style_updated(layer)
        return True
