"""
Browser dock widget for UmeMap Layer Browser.

Uses QgsNetworkAccessManager for async HTTP requests to avoid blocking
the QGIS UI during WFS GetCapabilities and DescribeFeatureType fetching.
"""

import os
import re
import sip
import xml.etree.ElementTree as ET
from typing import Dict, Optional

from qgis.PyQt.QtCore import Qt, QRegularExpression, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget,
    QTreeView, QLineEdit, QToolBar, QAction,
    QMenu, QLabel, QMessageBox, QAbstractItemView, QApplication
)
from qgis.PyQt.QtGui import QIcon, QDrag
from qgis.gui import QgsDockWidget
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsApplication,
    QgsNetworkAccessManager, QgsAuthMethodConfig,
    QgsMimeDataUtils
)
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl

from ...ui.utils import log
from .wfs_source import WfsSource
from .wfs_parser import WfsCapabilitiesParser, WfsLayerInfo, WfsDescribeFeatureTypeParser
from .layer_tree_model import LayerTreeModel, LayerFilterProxyModel, ItemRole
from .settings_manager import SettingsManager

# Network request timeout in milliseconds (30 seconds)
REQUEST_TIMEOUT_MS = 30000


class WfsLayerTreeView(QTreeView):
    """
    Custom QTreeView with drag-and-drop support for WFS layers.

    Allows dragging layers to QGIS Layers panel.
    """

    def __init__(self, parent=None):
        """Initialize the tree view."""
        super().__init__(parent)
        self.drag_start_pos = None
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)

    def mousePressEvent(self, event):
        """Record drag start position on mouse press."""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Start drag operation when mouse moves with left button held."""
        if not (event.buttons() & Qt.LeftButton):
            return

        if self.drag_start_pos is None:
            return

        # Check minimum drag distance
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        # Get item at drag start position
        index = self.indexAt(self.drag_start_pos)
        if not index.isValid():
            return

        # Only drag layer items
        item_type = index.data(ItemRole.ItemType)
        if item_type != 'layer':
            return

        self._perform_drag(index)

    def _perform_drag(self, proxy_index):
        """Execute drag operation with QGIS-compatible mime data."""
        # Get source model index through proxy
        proxy_model = self.model()
        if hasattr(proxy_model, 'mapToSource'):
            source_index = proxy_model.mapToSource(proxy_index)
        else:
            source_index = proxy_index

        # Get layer info
        source_model = proxy_model.sourceModel() if hasattr(proxy_model, 'sourceModel') else proxy_model
        layer_info = source_model.get_layer_info_from_index(source_index)
        if not layer_info:
            return

        # Build WFS URI
        uri_parts = [
            f"url='{layer_info['url']}'",
            f"typename='{layer_info['name']}'",
            f"version='2.0.0'",
            f"srsname='{layer_info['crs']}'"
        ]
        if layer_info.get('authcfg'):
            uri_parts.append(f"authcfg='{layer_info['authcfg']}'")

        uri = ' '.join(uri_parts)

        # Create QGIS layer URI for mime data
        layer_uri = QgsMimeDataUtils.Uri()
        layer_uri.layerType = "vector"
        layer_uri.providerKey = "WFS"
        layer_uri.name = layer_info['title']
        layer_uri.uri = uri

        # Create mime data
        mime_data = QgsMimeDataUtils.encodeUriList([layer_uri])

        # Start drag
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.CopyAction)


class BrowserDock(QgsDockWidget):
    """
    Dockable browser panel for WFS layers.

    Displays WFS sources and their layers organized by keywords hierarchy.
    Layers added via this browser will trigger the layerWasAdded signal,
    which StyleService.on_layer_added() listens to for auto-applying styles.
    """

    # Signals
    layer_added = pyqtSignal(str)  # Emits layer name when added to map

    def __init__(self, iface, parent=None):
        """
        Initialize the browser dock.

        Args:
            iface: QGIS interface instance
            parent: Parent widget
        """
        super().__init__("UmeMap Layer Browser", parent)
        self.iface = iface
        self.setObjectName("UmeMapLayerBrowserDock")

        # Initialize components
        self.settings = SettingsManager()
        self.parser = WfsCapabilitiesParser()
        self.model = LayerTreeModel(self)
        self.proxy_model = LayerFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        # Track pending requests for timeout handling
        self._pending_requests: Dict[str, WfsSource] = {}
        self._pending_replies: Dict[str, object] = {}

        # Setup UI
        self._setup_ui()
        self._setup_actions()
        self._setup_icons()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup the dock widget UI."""
        # Main widget and layout
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(self.toolbar.iconSize())
        layout.addWidget(self.toolbar)

        # Search/filter input
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(4, 4, 4, 4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search layers...")
        self.search_input.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_input)

        layout.addLayout(search_layout)

        # Tree view with drag-and-drop support
        self.tree_view = WfsLayerTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_view.setExpandsOnDoubleClick(False)  # We handle double-click ourselves
        layout.addWidget(self.tree_view)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 4px;")
        layout.addWidget(self.status_label)

        self.setWidget(main_widget)

    def _setup_actions(self) -> None:
        """Setup toolbar actions."""
        # Add source action
        self.action_add_source = QAction("Add source", self)
        self.action_add_source.setToolTip("Add a new WFS source")
        self.toolbar.addAction(self.action_add_source)

        # Remove source action
        self.action_remove_source = QAction("Remove source", self)
        self.action_remove_source.setToolTip("Remove selected WFS source")
        self.toolbar.addAction(self.action_remove_source)

        self.toolbar.addSeparator()

        # Refresh action
        self.action_refresh = QAction("Refresh", self)
        self.action_refresh.setToolTip("Refresh all sources")
        self.toolbar.addAction(self.action_refresh)

    def _setup_icons(self) -> None:
        """Setup Material Symbols icons for actions and tree items."""
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons')

        icons = {
            'source': QIcon(os.path.join(icons_dir, 'source.svg')),
            'folder': QIcon(os.path.join(icons_dir, 'folder.svg')),
            'layer': QIcon(os.path.join(icons_dir, 'layer_vector.svg')),
            'point': QIcon(os.path.join(icons_dir, 'point.svg')),
            'line': QIcon(os.path.join(icons_dir, 'line.svg')),
            'polygon': QIcon(os.path.join(icons_dir, 'polygon.svg')),
        }

        self.model.set_icons(icons)

        # Action icons
        self.action_add_source.setIcon(QIcon(os.path.join(icons_dir, 'add.svg')))
        self.action_remove_source.setIcon(QIcon(os.path.join(icons_dir, 'remove.svg')))
        self.action_refresh.setIcon(QIcon(os.path.join(icons_dir, 'refresh.svg')))

    def _connect_signals(self) -> None:
        """Connect signals and slots."""
        # Actions
        self.action_add_source.triggered.connect(self._on_add_source)
        self.action_remove_source.triggered.connect(self._on_remove_source)
        self.action_refresh.triggered.connect(self._on_refresh_all)

        # Tree view
        self.tree_view.doubleClicked.connect(self._on_double_click)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)

        # Search input
        self.search_input.textChanged.connect(self._on_filter_changed)

    def load_sources(self) -> None:
        """Load all saved sources and fetch their capabilities."""
        sources = self.settings.load_sources()

        if not sources:
            self._update_status("No sources configured")
            return

        self._update_status(f"Loading {len(sources)} source(s)...")

        for source in sources:
            if source.enabled:
                self._fetch_capabilities(source)

    def _fetch_capabilities(self, source: WfsSource) -> None:
        """
        Fetch GetCapabilities for a source asynchronously.

        Args:
            source: WfsSource to fetch capabilities for
        """
        url = source.get_capabilities_url()

        # Create request
        request = QNetworkRequest(QUrl(url))

        # Use redirect policy compatible with both Qt 5 and Qt 6
        try:
            # Qt 5.9+ / Qt 6
            request.setAttribute(
                QNetworkRequest.RedirectPolicyAttribute,
                QNetworkRequest.NoLessSafeRedirectPolicy
            )
        except AttributeError:
            # Fallback for older Qt 5 versions
            request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)

        # Add auth if configured
        if source.authcfg:
            auth_manager = QgsApplication.authManager()
            auth_manager.updateNetworkRequest(request, source.authcfg)

        # Track this request
        self._pending_requests[url] = source

        # Send request
        nam = QgsNetworkAccessManager.instance()
        reply = nam.get(request)
        self._pending_replies[url] = reply
        reply.finished.connect(lambda: self._on_capabilities_received(reply, source))

        # Setup timeout
        QTimer.singleShot(REQUEST_TIMEOUT_MS, lambda: self._on_request_timeout(url, reply))

    def _on_request_timeout(self, url: str, reply) -> None:
        """Abort request if still pending after timeout."""
        if sip.isdeleted(reply):
            self._pending_requests.pop(url, None)
            self._pending_replies.pop(url, None)
            return
        if url in self._pending_requests and not reply.isFinished():
            log(f"[Layer Browser] Request timeout for: {url}")
            reply.abort()

    def _on_capabilities_received(self, reply, source: WfsSource) -> None:
        """Handle GetCapabilities response."""
        url = reply.url().toString()

        # Remove from pending
        self._pending_requests.pop(url, None)
        self._pending_replies.pop(url, None)

        if reply.error():
            error_msg = reply.errorString()
            log(f"[Layer Browser] Error fetching {source.name}: {error_msg}")
            self._update_status(f"Error: {source.name} - {error_msg}")
            reply.deleteLater()
            return

        # Parse capabilities
        xml_data = bytes(reply.readAll())
        reply.deleteLater()

        layers = self.parser.parse_capabilities(xml_data)
        self.parser.cache_layers(source.url, layers)

        # Add to model
        self.model.add_wfs_source(source, layers)

        # Update status
        layer_count = len(layers)
        self._update_status(f"{source.name}: {layer_count} layers loaded")

        # Expand source node if setting is enabled
        if self.settings.get_expand_on_start():
            source_item = self.model.get_source_item(source.id)
            if source_item:
                index = self.model.indexFromItem(source_item)
                proxy_index = self.proxy_model.mapFromSource(index)
                self.tree_view.expand(proxy_index)

        # Fetch geometry types for all layers (async)
        self._fetch_geometry_types(source, list(layers.keys()))

    def _fetch_geometry_types(self, source: WfsSource, layer_names: list) -> None:
        """
        Fetch DescribeFeatureType for layers to get geometry types.

        Args:
            source: WfsSource
            layer_names: List of layer names to fetch
        """
        if not layer_names:
            return

        # Build DescribeFeatureType URL for all layers at once
        type_names = ','.join(layer_names)
        separator = '&' if '?' in source.url else '?'
        url = f"{source.url}{separator}SERVICE=WFS&REQUEST=DescribeFeatureType&VERSION={source.version}&TYPENAME={type_names}"

        # Create request
        request = QNetworkRequest(QUrl(url))

        # Use redirect policy compatible with both Qt 5 and Qt 6
        try:
            request.setAttribute(
                QNetworkRequest.RedirectPolicyAttribute,
                QNetworkRequest.NoLessSafeRedirectPolicy
            )
        except AttributeError:
            request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)

        # Add auth if configured
        if source.authcfg:
            auth_manager = QgsApplication.authManager()
            auth_manager.updateNetworkRequest(request, source.authcfg)

        # Send request
        nam = QgsNetworkAccessManager.instance()
        reply = nam.get(request)
        reply.finished.connect(lambda: self._on_describe_feature_type_received(reply, source, layer_names))

        # Setup timeout
        QTimer.singleShot(REQUEST_TIMEOUT_MS, lambda: self._on_geometry_timeout(reply))

    def _on_geometry_timeout(self, reply) -> None:
        """Abort geometry type request if still pending after timeout."""
        if sip.isdeleted(reply):
            return
        if not reply.isFinished():
            log("[Layer Browser] Geometry type request timeout")
            reply.abort()

    def _on_describe_feature_type_received(self, reply, source: WfsSource, layer_names: list) -> None:
        """Handle DescribeFeatureType response."""
        if reply.error():
            # Silently ignore errors - geometry types are optional
            reply.deleteLater()
            return

        xml_data = bytes(reply.readAll())
        reply.deleteLater()

        # Parse geometry types from the XSD schema
        self._parse_and_update_geometry_types(xml_data, source, layer_names)

    def _parse_and_update_geometry_types(self, xml_data: bytes, source: WfsSource, layer_names: list) -> None:
        """Parse geometry types from DescribeFeatureType and update the model."""
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return

        # XSD namespaces
        xsd_ns = '{http://www.w3.org/2001/XMLSchema}'

        # Find all complexType elements (one per layer)
        for complex_type in root.findall(f'.//{xsd_ns}complexType'):
            type_name = complex_type.get('name', '')

            # Match layer name (remove "Type" suffix if present)
            matched_layer = None
            for layer_name in layer_names:
                if type_name.startswith(layer_name) or layer_name in type_name:
                    matched_layer = layer_name
                    break

            if not matched_layer:
                continue

            # Find geometry element within this complexType
            for element in complex_type.findall(f'.//{xsd_ns}element'):
                element_type = element.get('type', '')

                # Check if this is a geometry element
                geometry_type = self._detect_geometry_type(element_type)
                if geometry_type and geometry_type != "Unknown":
                    # Update the layer in the model
                    self.model.update_layer_geometry_type(matched_layer, geometry_type)
                    break

    def _detect_geometry_type(self, element_type: str) -> str:
        """Detect geometry type from XSD element type."""
        type_map = {
            'PointPropertyType': 'Point',
            'MultiPointPropertyType': 'MultiPoint',
            'LineStringPropertyType': 'LineString',
            'CurvePropertyType': 'LineString',
            'MultiLineStringPropertyType': 'MultiLineString',
            'MultiCurvePropertyType': 'MultiLineString',
            'PolygonPropertyType': 'Polygon',
            'SurfacePropertyType': 'Polygon',
            'MultiPolygonPropertyType': 'MultiPolygon',
            'MultiSurfacePropertyType': 'MultiPolygon',
            'GeometryPropertyType': 'Geometry',
        }

        for gml_type, geom_type in type_map.items():
            if gml_type in element_type:
                return geom_type

        return "Unknown"

    def _on_add_source(self) -> None:
        """Handle add source action."""
        from .source_dialog import SourceDialog

        dialog = SourceDialog(self)
        if dialog.exec_():
            source = dialog.get_source()
            if source:
                # Save and load the new source
                self.settings.save_source(source)
                self._fetch_capabilities(source)

    def _on_remove_source(self) -> None:
        """Handle remove source action."""
        index = self.tree_view.currentIndex()
        if not index.isValid():
            return

        # Get source index (find root)
        source_index = index
        while source_index.parent().isValid():
            source_index = source_index.parent()

        source_id = source_index.data(ItemRole.SourceId)
        source_name = source_index.data(Qt.DisplayRole)

        if not source_id:
            return

        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Remove source",
            f"Do you want to remove the source '{source_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if result == QMessageBox.Yes:
            self.settings.remove_source(source_id)
            self.model.remove_wfs_source(source_id)
            self.parser.clear_cache()
            self._update_status(f"Source '{source_name}' removed")

    def _on_refresh_all(self) -> None:
        """Handle refresh all action."""
        self.parser.clear_cache()
        self.model.clear()

        sources = self.settings.load_sources()
        self._update_status(f"Refreshing {len(sources)} source(s)...")

        for source in sources:
            if source.enabled:
                self._fetch_capabilities(source)

    def _on_double_click(self, index) -> None:
        """Handle double-click on tree item."""
        # Map proxy index to source model
        source_index = self.proxy_model.mapToSource(index)
        item_type = source_index.data(ItemRole.ItemType)

        if item_type == 'layer':
            self._add_layer_to_map(source_index)
        elif item_type in ('source', 'folder'):
            # Toggle expansion
            if self.tree_view.isExpanded(index):
                self.tree_view.collapse(index)
            else:
                self.tree_view.expand(index)

    def _on_context_menu(self, pos) -> None:
        """Handle context menu request."""
        index = self.tree_view.indexAt(pos)
        if not index.isValid():
            return

        source_index = self.proxy_model.mapToSource(index)
        item_type = source_index.data(ItemRole.ItemType)

        menu = QMenu(self)

        if item_type == 'layer':
            action_add = menu.addAction("Add to map")
            action_add.triggered.connect(lambda: self._add_layer_to_map(source_index))

            menu.addSeparator()

            action_props = menu.addAction("Properties...")
            action_props.triggered.connect(lambda: self._show_layer_properties(source_index))

        elif item_type == 'folder':
            action_add_all = menu.addAction("Add all layers")
            action_add_all.triggered.connect(lambda: self._add_folder_layers(source_index))

        elif item_type == 'source':
            action_refresh = menu.addAction("Refresh")
            action_refresh.triggered.connect(lambda: self._refresh_source(source_index))

            menu.addSeparator()

            action_edit = menu.addAction("Edit...")
            action_edit.triggered.connect(lambda: self._edit_source(source_index))

            action_remove = menu.addAction("Remove")
            action_remove.triggered.connect(self._on_remove_source)

        if not menu.isEmpty():
            menu.exec_(self.tree_view.viewport().mapToGlobal(pos))

    def _on_filter_changed(self, text: str) -> None:
        """Handle filter text change."""
        self.proxy_model.setFilterRegularExpression(QRegularExpression(text))

        # Expand all when filtering
        if text:
            self.tree_view.expandAll()

    def _add_layer_to_map(self, index) -> None:
        """Add a layer to the map."""
        layer_info = self.model.get_layer_info_from_index(index)
        if not layer_info:
            return

        # Build WFS URI
        uri_parts = [
            f"url='{layer_info['url']}'",
            f"typename='{layer_info['name']}'",
            f"version='2.0.0'",
            f"srsname='{layer_info['crs']}'"
        ]

        if layer_info.get('authcfg'):
            uri_parts.append(f"authcfg='{layer_info['authcfg']}'")

        uri = ' '.join(uri_parts)

        # Create and add layer
        layer = QgsVectorLayer(uri, layer_info['title'], 'WFS')

        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self._update_status(f"Added: {layer_info['title']}")
            self.layer_added.emit(layer_info['title'])
        else:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not add layer '{layer_info['title']}'.\n"
                "Check the connection and try again."
            )

    def _add_folder_layers(self, folder_index) -> None:
        """Add all layers in a folder to the map."""
        model = self.model
        row_count = model.rowCount(folder_index)

        added = 0
        for row in range(row_count):
            child_index = model.index(row, 0, folder_index)
            item_type = child_index.data(ItemRole.ItemType)

            if item_type == 'layer':
                self._add_layer_to_map(child_index)
                added += 1
            elif item_type == 'folder':
                # Recursive for subfolders
                self._add_folder_layers(child_index)

        if added > 0:
            self._update_status(f"Added {added} layers")

    def _refresh_source(self, index) -> None:
        """Refresh a single source."""
        source_id = index.data(ItemRole.SourceId)
        source = self.settings.get_source(source_id)

        if source:
            self.parser.clear_cache(source.url)
            self.model.remove_wfs_source(source_id)
            self._fetch_capabilities(source)

    def _edit_source(self, index) -> None:
        """Edit a source."""
        source_id = index.data(ItemRole.SourceId)
        source = self.settings.get_source(source_id)

        if not source:
            return

        from .source_dialog import SourceDialog

        dialog = SourceDialog(self, source)
        if dialog.exec_():
            updated_source = dialog.get_source()
            if updated_source:
                # Preserve ID
                updated_source.id = source_id

                # Save and reload
                self.settings.save_source(updated_source)
                self.parser.clear_cache(source.url)
                self.model.remove_wfs_source(source_id)
                self._fetch_capabilities(updated_source)

    @staticmethod
    def _format_description(text: str) -> str:
        """Format description text: convert newlines to <br/> and URLs to clickable links."""
        if not text:
            return 'No description'
        # Escape HTML entities first
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Convert URLs to clickable links
        url_pattern = r'(https?://[^\s,)]+)'
        text = re.sub(url_pattern, r'<a href="\1">\1</a>', text)
        # Convert newlines to <br/>
        text = text.replace('\n', '<br/>')
        return text

    def _show_layer_properties(self, index) -> None:
        """Show layer properties dialog."""
        layer_info = self.model.get_layer_info_from_index(index)
        if not layer_info:
            return

        description = self._format_description(layer_info['abstract'])

        info_text = f"""
<b>{layer_info['title']}</b><br/>
<br/>
<b>Name:</b> {layer_info['name']}<br/>
<b>CRS:</b> {layer_info['crs']}<br/>
<b>URL:</b> {layer_info['url']}<br/>
<br/>
<b>Description:</b><br/>
{description}
"""
        QMessageBox.information(self, "Layer properties", info_text)

    def _update_status(self, message: str) -> None:
        """Update status bar message."""
        self.status_label.setText(message)
