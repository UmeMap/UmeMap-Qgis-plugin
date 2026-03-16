# -*- coding: utf-8 -*-
"""
Style Service - Handles saving and loading styles from UmeMap server.
"""

import os
import tempfile
from typing import Callable, List, Optional, Set

from qgis.core import Qgis, QgsApplication, QgsDataSourceUri, QgsMapLayer, QgsProject, QgsTask, QgsVectorLayer
from qgis.PyQt.QtXml import QDomDocument

from ...core.api_client import UmeMapApiClient, ApiResponse
from ...core.auth_manager import AuthManager
from ...core.wfs_utils import parse_wfs_data_source
from ...ui.utils import log


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
            log(f"Could not parse WFS data source for '{layer.name()}' (url={wfs_url}, typename={layer_name}).", Qgis.Warning)
            return False

        # Check if server is UmeMap
        if not UmeMapApiClient.is_umemap_server(wfs_url):
            log(f"Server '{wfs_url}' is not a UmeMap server.", Qgis.Warning)
            return False

        # Get auth headers and fetch style
        headers = AuthManager.get_headers_from_layer(layer)
        client = UmeMapApiClient(wfs_url, headers)

        style_doc = client.get_vector_style(layer_name)
        if not style_doc:
            log(f"Could not fetch style for '{layer_name}' from '{wfs_url}'.", Qgis.Warning)
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

        # Skip CodeList lookup layers (auto-loaded for ValueRelation)
        if layer_name.startswith("CodeList_"):
            return False

        if not UmeMapApiClient.is_umemap_server(wfs_url):
            return False

        return True

    def on_layer_added(self, layer: QgsMapLayer) -> None:
        """
        Event handler for when a layer is added to the project.
        Applies UmeMap style if appropriate, then auto-loads any
        CodeList lookup layers required by ValueRelation widgets.

        :param layer: The layer that was added
        """
        try:
            if self.should_apply_style(layer):
                success = self.load_from_server(layer)
                if success:
                    self._ensure_codelist_layers(layer)
                else:
                    log(f"Style could not be applied to '{layer.name()}'.", Qgis.Warning)
        except Exception as e:
            log(f"[ERROR] on_layer_added failed for '{layer.name()}': {e}", Qgis.Critical)

    def _ensure_codelist_layers(self, layer: QgsMapLayer) -> None:
        """
        Check if the layer's style contains ValueRelation widgets that reference
        CodeList WFS layers and auto-load any missing ones.

        :param layer: The layer whose style may reference CodeList layers
        """
        needed_layers = self._find_codelist_layer_refs(layer)
        if not needed_layers:
            return

        # Check which CodeList layers are already loaded
        project = QgsProject.instance()
        loaded_names = {l.name() for l in project.mapLayers().values()}

        wfs_url, _ = parse_wfs_data_source(layer)
        if not wfs_url:
            return

        ds = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
        authcfg = ds.authConfigId() or ""

        for codelist_layer_name in needed_layers:
            if codelist_layer_name in loaded_names:
                log(f"CodeList layer '{codelist_layer_name}' already loaded.", Qgis.Info)
                continue

            self._load_codelist_layer(wfs_url, codelist_layer_name, authcfg)

    def _find_codelist_layer_refs(self, layer: QgsMapLayer) -> Set[str]:
        """
        Parse the layer's style to find ValueRelation widgets referencing CodeList layers.

        :param layer: Layer to inspect
        :return: Set of CodeList layer names referenced by ValueRelation widgets
        """
        codelist_refs: Set[str] = set()

        try:
            # Export current style to QDomDocument
            style_doc = QDomDocument("qgis")
            layer.exportNamedStyle(style_doc)

            # Find all editWidget elements with type="ValueRelation".
            # UmeMapCodeListSearch widgets are intentionally skipped here -
            # they query the server directly and don't need WFS lookup layers.
            edit_widgets = style_doc.elementsByTagName("editWidget")
            for i in range(edit_widgets.count()):
                widget = edit_widgets.at(i).toElement()
                if widget.attribute("type") != "ValueRelation":
                    continue

                # Find the LayerName option within this widget's config
                options = widget.elementsByTagName("Option")
                for j in range(options.count()):
                    opt = options.at(j).toElement()
                    if opt.attribute("name") == "LayerName":
                        layer_name = opt.attribute("value")
                        if layer_name and layer_name.startswith("CodeList_"):
                            codelist_refs.add(layer_name)

        except Exception as e:
            log(f"Error parsing style for ValueRelation refs: {e}", Qgis.Warning)

        return codelist_refs

    def _load_codelist_layer(self, wfs_url: str, layer_name: str, authcfg: str) -> None:
        """
        Load a CodeList WFS layer into the project.

        :param wfs_url: WFS server URL
        :param layer_name: CodeList layer name (e.g. 'CodeList_Artnamn_växter')
        :param authcfg: QGIS auth config ID
        """
        uri_parts = [
            f"url='{wfs_url}'",
            f"typename='{layer_name}'",
            "version='2.0.0'",
        ]
        if authcfg:
            uri_parts.append(f"authcfg='{authcfg}'")

        uri = " ".join(uri_parts)

        codelist_layer = QgsVectorLayer(uri, layer_name, "WFS")
        if codelist_layer.isValid():
            # Add as hidden layer (not shown in layer tree by default)
            QgsProject.instance().addMapLayer(codelist_layer, False)

            # Prefetch features in background so ValueRelation completer works
            # when user opens a feature form. Without this, the first form open is slow.
            task = _CodeListPrefetchTask(layer_name, codelist_layer)
            QgsApplication.taskManager().addTask(task)

            log(f"Auto-loading CodeList layer '{layer_name}' in background...", Qgis.Info)
        else:
            log(f"Failed to load CodeList layer '{layer_name}' from '{wfs_url}'.", Qgis.Warning)


class _CodeListPrefetchTask(QgsTask):
    """Background task that prefetches CodeList features into QGIS WFS cache."""

    def __init__(self, layer_name: str, layer: QgsVectorLayer):
        super().__init__(f"Laddar kodlista: {layer_name}")
        self._layer = layer
        self._layer_name = layer_name
        self._count = 0

    def run(self) -> bool:
        """Runs in background thread - iterates all features to populate WFS cache."""
        try:
            for _ in self._layer.getFeatures():
                self._count += 1
                if self.isCanceled():
                    return False
            return True
        except Exception:
            return False

    def finished(self, result: bool) -> None:
        """Called on main thread when task completes."""
        if result:
            log(f"CodeList '{self._layer_name}' loaded ({self._count} values).", Qgis.Info)
        else:
            log(f"CodeList '{self._layer_name}' prefetch failed or cancelled.", Qgis.Warning)
