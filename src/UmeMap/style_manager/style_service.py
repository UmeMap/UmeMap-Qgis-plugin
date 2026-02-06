# -*- coding: utf-8 -*-
"""
Style Service - Handles saving and loading styles from UmeMap server.
"""

import os
import tempfile
from typing import Callable, Optional

from qgis.core import Qgis, QgsMapLayer

from ..core.api_client import UmeMapApiClient, ApiResponse
from ..core.auth_manager import AuthManager
from ..core.wfs_utils import parse_wfs_data_source
from ..ui.utils import log


class StyleService:
    """Service for managing layer styles with UmeMap server."""

    def __init__(self, tr_func: Optional[Callable[[str], str]] = None):
        """
        Initialize StyleService.

        :param tr_func: Translation function for i18n support
        """
        self._tr = tr_func or (lambda x: x)

    def save_to_server(self, layer: QgsMapLayer) -> ApiResponse:
        """
        Save layer's current style to UmeMap server.

        :param layer: QGIS layer to save style from
        :return: ApiResponse with result
        """
        wfs_url, layer_name = parse_wfs_data_source(layer)

        if not wfs_url or not layer_name:
            return ApiResponse(
                status="error",
                data=None,
                message=self._tr("Could not parse WFS data source"),
                code="PARSE_ERROR"
            )

        # Check if server is UmeMap
        if not UmeMapApiClient.is_umemap_server(wfs_url):
            return ApiResponse(
                status="error",
                data=None,
                message=self._tr("Server is not a UmeMap server"),
                code="NOT_UMEMAP"
            )

        # Save style to temp file
        temp_folder = tempfile.gettempdir()
        qml_path = os.path.join(temp_folder, f"{layer_name}.qml")

        layer.saveNamedStyle(qml_path)

        # Read QML file
        try:
            with open(qml_path, mode="rb") as xml_file:
                xml_data = xml_file.read()
        except Exception as e:
            return ApiResponse(
                status="error",
                data=None,
                message=f"Could not read style file: {str(e)}",
                code="FILE_ERROR"
            )

        # Get auth headers and send to server
        headers = AuthManager.get_headers_from_layer(layer)
        client = UmeMapApiClient(wfs_url, headers)

        return client.save_vector_style(layer_name, xml_data)

    def load_from_server(self, layer: QgsMapLayer) -> bool:
        """
        Load and apply style from UmeMap server to layer.

        :param layer: QGIS layer to apply style to
        :return: True if style was applied, False otherwise
        """
        wfs_url, layer_name = parse_wfs_data_source(layer)

        if not wfs_url or not layer_name:
            return False

        # Check if server is UmeMap
        if not UmeMapApiClient.is_umemap_server(wfs_url):
            return False

        # Get auth headers and fetch style
        headers = AuthManager.get_headers_from_layer(layer)
        client = UmeMapApiClient(wfs_url, headers)

        style_doc = client.get_vector_style(layer_name)
        if not style_doc:
            return False

        return self.apply_style_to_layer(layer, style_doc)

    def apply_style_to_layer(self, layer: QgsMapLayer, style_doc) -> bool:
        """
        Apply a style document to a layer.

        :param layer: QGIS layer to apply style to
        :param style_doc: QDomDocument with style
        :return: True if successful, False otherwise
        """
        import_result = layer.importNamedStyle(style_doc)

        if import_result[0]:
            layer.setCustomProperty("umemap_style_applied", True)
            layer.triggerRepaint()
            log(f"UmeMap style applied on '{layer.name()}'.", Qgis.Info)
            return True
        else:
            log(f"Could not import style to '{layer.name()}'.", Qgis.Warning)
            return False

    def should_apply_style(self, layer: QgsMapLayer) -> bool:
        """
        Check if UmeMap style should be applied to a layer.

        :param layer: QGIS layer to check
        :return: True if style should be applied
        """
        if not layer:
            return False

        # Skip if style already has been applied before
        if layer.customProperty("umemap_style_applied", False):
            return False

        # If style is from project file, skip
        style_uri = layer.styleURI()
        if style_uri and style_uri.startswith("project:"):
            log(f"Local style used for '{layer.name()}'.", Qgis.Info)
            return False

        # Check if it's a UmeMap server
        wfs_url, layer_name = parse_wfs_data_source(layer)
        if not wfs_url or not layer_name:
            return False

        if not UmeMapApiClient.is_umemap_server(wfs_url):
            return False

        return True

    def on_layer_added(self, layer: QgsMapLayer) -> None:
        """
        Event handler for when a layer is added to the project.
        Applies UmeMap style if appropriate.

        :param layer: The layer that was added
        """
        try:
            if self.should_apply_style(layer):
                self.load_from_server(layer)
        except Exception as e:
            log(f"[ERROR] on_layer_added failed for '{layer.name()}': {e}", Qgis.Critical)
