"""
Layer tree model for displaying WFS sources and layers in a hierarchical view.
"""

from enum import IntEnum
from typing import Dict, List, Optional

from qgis.PyQt.QtCore import Qt, QSortFilterProxyModel
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QIcon
from qgis.core import QgsApplication

from .wfs_source import WfsSource
from .wfs_parser import WfsLayerInfo, WfsDescribeFeatureTypeParser


class ItemRole(IntEnum):
    """Custom data roles for tree items."""
    ItemType = Qt.UserRole + 1        # 'source', 'folder', 'layer'
    SourceId = Qt.UserRole + 2        # WfsSource.id
    LayerName = Qt.UserRole + 3       # WFS typename
    LayerTitle = Qt.UserRole + 4      # Human-readable title
    LayerAbstract = Qt.UserRole + 5   # Description
    WfsUrl = Qt.UserRole + 6          # Service URL
    AuthCfg = Qt.UserRole + 7         # Auth config ID
    Crs = Qt.UserRole + 8             # Default CRS
    Keywords = Qt.UserRole + 9        # Original keywords list
    FolderPath = Qt.UserRole + 10     # Full folder path
    GeometryType = Qt.UserRole + 11   # Geometry type: Point, LineString, Polygon, etc.


class LayerTreeModel(QStandardItemModel):
    """
    Model for displaying WFS sources and layers in a tree view.

    Structure:
    - Source (root level)
      - Folder (from keywords path)
        - Subfolder
          - Layer
      - Layer (without keywords)
    """

    def __init__(self, parent=None):
        """Initialize the model."""
        super().__init__(parent)
        self._source_items: Dict[str, QStandardItem] = {}
        self._icons: Dict[str, QIcon] = {}

    def clear(self) -> None:
        """Clear the model and reset the source items tracking dict."""
        super().clear()
        self._source_items.clear()

    def set_icons(self, icons: Dict[str, QIcon]) -> None:
        """
        Set icons for different item types.

        Args:
            icons: Dictionary with keys 'source', 'folder', 'folder_open', 'layer'
        """
        self._icons = icons

    def add_wfs_source(self, source: WfsSource, layers: Dict[str, WfsLayerInfo]) -> None:
        """
        Add a WFS source with its layers to the model.

        Args:
            source: WfsSource instance
            layers: Dictionary of layer name to WfsLayerInfo
        """
        # Remove existing source item if present
        self.remove_wfs_source(source.id)

        # Create source item
        source_item = QStandardItem(source.name)
        source_item.setData('source', ItemRole.ItemType)
        source_item.setData(source.id, ItemRole.SourceId)
        source_item.setData(source.url, ItemRole.WfsUrl)
        source_item.setData(source.authcfg, ItemRole.AuthCfg)
        source_item.setToolTip(source.url)
        source_item.setEditable(False)

        if 'source' in self._icons:
            source_item.setIcon(self._icons['source'])

        # Build folder structure and add layers
        self._build_layer_tree(source_item, source, layers)

        # Add to model
        self.appendRow(source_item)
        self._source_items[source.id] = source_item

    def remove_wfs_source(self, source_id: str) -> None:
        """
        Remove a WFS source from the model.

        Args:
            source_id: ID of source to remove
        """
        if source_id in self._source_items:
            item = self._source_items[source_id]
            index = self.indexFromItem(item)
            if index.isValid():
                self.removeRow(index.row())
            del self._source_items[source_id]

    def refresh_source(self, source: WfsSource, layers: Dict[str, WfsLayerInfo]) -> None:
        """
        Refresh a source's layers.

        Args:
            source: WfsSource instance
            layers: Updated layer dictionary
        """
        # Simply re-add the source (which removes old one first)
        self.add_wfs_source(source, layers)

    def get_source_item(self, source_id: str) -> Optional[QStandardItem]:
        """Get the item for a source."""
        return self._source_items.get(source_id)

    def get_layer_info_from_index(self, index) -> Optional[Dict]:
        """
        Get layer info from a model index.

        Args:
            index: QModelIndex

        Returns:
            Dictionary with layer info or None
        """
        item_type = index.data(ItemRole.ItemType)
        if item_type != 'layer':
            return None

        return {
            'name': index.data(ItemRole.LayerName),
            'title': index.data(ItemRole.LayerTitle),
            'abstract': index.data(ItemRole.LayerAbstract),
            'url': index.data(ItemRole.WfsUrl),
            'authcfg': index.data(ItemRole.AuthCfg),
            'crs': index.data(ItemRole.Crs),
            'source_id': index.data(ItemRole.SourceId),
        }

    def _build_layer_tree(self, source_item: QStandardItem, source: WfsSource,
                          layers: Dict[str, WfsLayerInfo]) -> None:
        """Build the folder/layer tree under a source item.

        Sorting order:
        1. Folders first (with their layers), sorted alphabetically
        2. Layers without keywords last, sorted alphabetically
        """
        # Group layers by folder path
        folder_layers: Dict[str, List[WfsLayerInfo]] = {}
        root_layers: List[WfsLayerInfo] = []  # Layers without keywords

        for layer in layers.values():
            folder_path = layer.folder_path or ''
            if folder_path:
                if folder_path not in folder_layers:
                    folder_layers[folder_path] = []
                folder_layers[folder_path].append(layer)
            else:
                root_layers.append(layer)

        # Create folder items cache
        folder_items: Dict[str, QStandardItem] = {'': source_item}

        # 1. Add folders first (sorted alphabetically)
        sorted_paths = sorted(folder_layers.keys())

        for folder_path in sorted_paths:
            # Ensure folder exists
            self._ensure_folder(source_item, folder_path, folder_items, source)

            # Add layers to folder
            parent_item = folder_items[folder_path]
            for layer in sorted(folder_layers[folder_path], key=lambda l: l.title):
                layer_item = self._create_layer_item(layer, source)
                parent_item.appendRow(layer_item)

        # 2. Add layers without keywords last (sorted alphabetically)
        for layer in sorted(root_layers, key=lambda l: l.title):
            layer_item = self._create_layer_item(layer, source)
            source_item.appendRow(layer_item)

    def _ensure_folder(self, source_item: QStandardItem, folder_path: str,
                       folder_items: Dict[str, QStandardItem], source: WfsSource) -> QStandardItem:
        """
        Ensure a folder path exists, creating parent folders as needed.

        Args:
            source_item: Source root item
            folder_path: Full folder path (e.g., "Kultur och fritid/Rekreation")
            folder_items: Cache of created folder items
            source: WfsSource for metadata

        Returns:
            The folder item for the given path
        """
        if folder_path in folder_items:
            return folder_items[folder_path]

        # Split path and ensure parent exists
        parts = folder_path.split('/')
        current_path = ''
        current_parent = source_item

        for part in parts:
            if current_path:
                current_path = f"{current_path}/{part}"
            else:
                current_path = part

            if current_path not in folder_items:
                # Create folder item
                folder_item = QStandardItem(part)
                folder_item.setData('folder', ItemRole.ItemType)
                folder_item.setData(source.id, ItemRole.SourceId)
                folder_item.setData(source.url, ItemRole.WfsUrl)
                folder_item.setData(source.authcfg, ItemRole.AuthCfg)
                folder_item.setData(current_path, ItemRole.FolderPath)
                folder_item.setEditable(False)

                if 'folder' in self._icons:
                    folder_item.setIcon(self._icons['folder'])

                current_parent.appendRow(folder_item)
                folder_items[current_path] = folder_item

            current_parent = folder_items[current_path]

        return current_parent

    def _create_layer_item(self, layer: WfsLayerInfo, source: WfsSource) -> QStandardItem:
        """Create a tree item for a layer."""
        item = QStandardItem(layer.title)
        item.setData('layer', ItemRole.ItemType)
        item.setData(source.id, ItemRole.SourceId)
        item.setData(layer.name, ItemRole.LayerName)
        item.setData(layer.title, ItemRole.LayerTitle)
        item.setData(layer.abstract, ItemRole.LayerAbstract)
        item.setData(source.url, ItemRole.WfsUrl)
        item.setData(source.authcfg, ItemRole.AuthCfg)
        item.setData(layer.crs, ItemRole.Crs)
        item.setData(layer.keywords, ItemRole.Keywords)
        item.setData(layer.geometry_type, ItemRole.GeometryType)
        item.setEditable(False)

        # Build tooltip
        tooltip_parts = [f"<b>{layer.title}</b>"]
        if layer.abstract:
            # Truncate long abstracts
            abstract = layer.abstract[:200] + "..." if len(layer.abstract) > 200 else layer.abstract
            tooltip_parts.append(f"<br/>{abstract}")
        tooltip_parts.append(f"<br/><i>CRS: {layer.crs}</i>")
        tooltip_parts.append(f"<br/><i>Name: {layer.name}</i>")
        if layer.geometry_type and layer.geometry_type != "Unknown":
            tooltip_parts.append(f"<br/><i>Geometri: {layer.geometry_type}</i>")
        item.setToolTip("".join(tooltip_parts))

        # Set icon based on geometry type
        icon = self._get_geometry_icon(layer.geometry_type)
        item.setIcon(icon)

        return item

    def _get_geometry_icon(self, geometry_type: str) -> QIcon:
        """Get Material Symbol icon for a geometry type."""
        icon_map = {
            'Point': 'point',
            'MultiPoint': 'point',
            'LineString': 'line',
            'MultiLineString': 'line',
            'Polygon': 'polygon',
            'MultiPolygon': 'polygon',
        }
        icon_key = icon_map.get(geometry_type, 'layer')
        if icon_key in self._icons:
            return self._icons[icon_key]
        return self._icons.get('layer', QIcon())

    def update_layer_geometry_type(self, layer_name: str, geometry_type: str) -> None:
        """
        Update the geometry type and icon for a layer.

        Args:
            layer_name: WFS typename
            geometry_type: Geometry type string
        """
        # Find and update the layer item
        for source_id, source_item in self._source_items.items():
            self._update_layer_in_tree(source_item, layer_name, geometry_type)

    def _update_layer_in_tree(self, parent: QStandardItem, layer_name: str, geometry_type: str) -> bool:
        """Recursively find and update a layer in the tree."""
        for row in range(parent.rowCount()):
            child = parent.child(row)
            if child is None:
                continue

            item_type = child.data(ItemRole.ItemType)

            if item_type == 'layer':
                if child.data(ItemRole.LayerName) == layer_name:
                    # Update geometry type
                    child.setData(geometry_type, ItemRole.GeometryType)
                    # Update icon
                    icon = self._get_geometry_icon(geometry_type)
                    child.setIcon(icon)
                    # Update tooltip
                    tooltip = child.toolTip()
                    if "<i>Geometri:" not in tooltip:
                        tooltip += f"<br/><i>Geometri: {geometry_type}</i>"
                    child.setToolTip(tooltip)
                    return True

            elif item_type == 'folder':
                if self._update_layer_in_tree(child, layer_name, geometry_type):
                    return True

        return False


class LayerFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model for filtering the layer tree.

    Shows folders that contain matching layers, and all matching layers.
    """

    def __init__(self, parent=None):
        """Initialize the filter proxy model."""
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """
        Determine if a row should be shown.

        Sources and folders are shown if they have matching children.
        Layers are shown if they match the filter.
        """
        index = self.sourceModel().index(source_row, 0, source_parent)
        item_type = index.data(ItemRole.ItemType)

        # Always show sources (they'll be hidden if no children match)
        if item_type == 'source':
            return self._has_matching_children(index)

        # Show folders if they have matching children
        if item_type == 'folder':
            return self._has_matching_children(index)

        # For layers, check name and title
        if item_type == 'layer':
            filter_text = self.filterRegularExpression().pattern().lower()
            if not filter_text:
                return True

            layer_name = (index.data(ItemRole.LayerName) or "").lower()
            layer_title = (index.data(ItemRole.LayerTitle) or "").lower()

            return filter_text in layer_name or filter_text in layer_title

        return True

    def _has_matching_children(self, parent_index) -> bool:
        """Check if a parent index has any matching children."""
        model = self.sourceModel()
        for row in range(model.rowCount(parent_index)):
            child_index = model.index(row, 0, parent_index)
            child_type = child_index.data(ItemRole.ItemType)

            if child_type == 'layer':
                filter_text = self.filterRegularExpression().pattern().lower()
                if not filter_text:
                    return True

                layer_name = (child_index.data(ItemRole.LayerName) or "").lower()
                layer_title = (child_index.data(ItemRole.LayerTitle) or "").lower()

                if filter_text in layer_name or filter_text in layer_title:
                    return True

            elif child_type == 'folder':
                if self._has_matching_children(child_index):
                    return True

        return not self.filterRegularExpression().pattern()  # Show all if no filter
