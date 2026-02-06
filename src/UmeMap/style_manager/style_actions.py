# -*- coding: utf-8 -*-
"""
Style Actions - Context menu actions for style management.
"""

from typing import Callable, Optional

from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis, QgsMapLayerType
from qgis.utils import iface

from .style_service import StyleService
from ..ui.utils import show_error_popup


class StyleActions:
    """Manages context menu actions for style operations."""

    def __init__(self, qgis_iface, tr_func: Optional[Callable[[str], str]] = None):
        """
        Initialize StyleActions.

        :param qgis_iface: QGIS interface instance
        :param tr_func: Translation function for i18n support
        """
        self.iface = qgis_iface
        self._tr = tr_func or (lambda x: x)
        self.style_service = StyleService(tr_func)
        self._action = None

    def register(self) -> QAction:
        """
        Register the "Save Style To UmeMap" context menu action.

        :return: The created QAction
        """
        self._action = QAction(
            self._tr("Save Style To UmeMap"),
            self.iface.mainWindow()
        )
        self._action.triggered.connect(self._on_save_style)

        # Add to vector layer context menu
        self.iface.addCustomActionForLayerType(
            self._action,
            "",
            QgsMapLayerType.VectorLayer,
            True
        )

        return self._action

    def unregister(self) -> None:
        """Remove the context menu action."""
        if self._action:
            self.iface.removeCustomActionForLayerType(self._action)
            self._action = None

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
            iface.messageBar().pushMessage(
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
