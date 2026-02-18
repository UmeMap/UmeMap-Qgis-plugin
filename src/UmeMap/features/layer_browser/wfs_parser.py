"""
WFS GetCapabilities parser with keywords support.

Parses ows:Keywords from WFS GetCapabilities to extract
folder hierarchy information for layer organization.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re

from ...ui.utils import log


@dataclass
class WfsLayerInfo:
    """Information about a WFS layer extracted from GetCapabilities."""
    name: str
    title: str
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    crs: str = "EPSG:4326"
    bbox_wgs84: Optional[Tuple[float, float, float, float]] = None  # minx, miny, maxx, maxy
    geometry_type: str = "Unknown"  # Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon

    @property
    def folder_path(self) -> Optional[str]:
        """
        Get the folder path from keywords.

        Keywords are expected in format: ["Kultur och fritid", "Kultur och fritid/Rekreation"]
        Returns the longest (most specific) path.
        """
        if not self.keywords:
            return None
        # Filter keywords that look like paths (contain /)
        path_keywords = [kw for kw in self.keywords if '/' in kw]
        if path_keywords:
            return max(path_keywords, key=len)
        # If no path keywords, return the longest single keyword
        return max(self.keywords, key=len) if self.keywords else None


class WfsCapabilitiesParser:
    """Parser for WFS GetCapabilities XML with keywords support."""

    # XML namespaces for different WFS versions
    NS = {
        'wfs20': 'http://www.opengis.net/wfs/2.0',
        'wfs11': 'http://www.opengis.net/wfs',
        'wfs10': 'http://www.opengis.net/wfs',
        'ows11': 'http://www.opengis.net/ows/1.1',
        'ows10': 'http://www.opengis.net/ows',
        'gml': 'http://www.opengis.net/gml',
    }

    def __init__(self):
        """Initialize the parser."""
        self._cache: Dict[str, Dict[str, WfsLayerInfo]] = {}

    def parse_capabilities(self, xml_data: bytes) -> Dict[str, WfsLayerInfo]:
        """
        Parse GetCapabilities XML and extract layer information.

        Args:
            xml_data: Raw XML bytes from GetCapabilities response

        Returns:
            Dictionary mapping layer names to WfsLayerInfo
        """
        try:
            root = ET.fromstring(xml_data)
            return self._parse_feature_types(root)
        except ET.ParseError as e:
            log(f"[Layer Browser] Error parsing XML: {e}")
            return {}

    def get_cached_layers(self, url: str) -> Optional[Dict[str, WfsLayerInfo]]:
        """
        Get cached layers for a URL.

        Args:
            url: Base WFS service URL

        Returns:
            Cached layers or None
        """
        return self._cache.get(self._normalize_url(url))

    def cache_layers(self, url: str, layers: Dict[str, WfsLayerInfo]) -> None:
        """
        Cache layers for a URL.

        Args:
            url: Base WFS service URL
            layers: Layer dictionary to cache
        """
        self._cache[self._normalize_url(url)] = layers

    def clear_cache(self, url: str = None) -> None:
        """
        Clear the capabilities cache.

        Args:
            url: Specific URL to clear, or None for all
        """
        if url:
            normalized = self._normalize_url(url)
            self._cache.pop(normalized, None)
        else:
            self._cache.clear()

    def build_folder_tree(self, layers: Dict[str, WfsLayerInfo]) -> Dict[str, List[WfsLayerInfo]]:
        """
        Build a folder tree structure from layers.

        Args:
            layers: Dictionary of layer name to WfsLayerInfo

        Returns:
            Dictionary mapping folder paths to lists of layers
        """
        tree: Dict[str, List[WfsLayerInfo]] = {}

        for layer in layers.values():
            folder_path = layer.folder_path
            if folder_path:
                if folder_path not in tree:
                    tree[folder_path] = []
                tree[folder_path].append(layer)
            else:
                # Layers without keywords go to root
                if '' not in tree:
                    tree[''] = []
                tree[''].append(layer)

        return tree

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for caching (remove query params)."""
        # Simple normalization - just get base URL
        if '?' in url:
            url = url.split('?')[0]
        return url.rstrip('/')

    def _parse_feature_types(self, root: ET.Element) -> Dict[str, WfsLayerInfo]:
        """Parse all FeatureType elements from GetCapabilities."""
        layers = {}

        # Try to find FeatureTypeList
        feature_type_list = None

        # WFS 2.0
        feature_type_list = root.find('{http://www.opengis.net/wfs/2.0}FeatureTypeList')

        # WFS 1.1
        if feature_type_list is None:
            feature_type_list = root.find('{http://www.opengis.net/wfs}FeatureTypeList')

        # No namespace
        if feature_type_list is None:
            feature_type_list = root.find('FeatureTypeList')

        if feature_type_list is None:
            log("[Layer Browser] No FeatureTypeList found in GetCapabilities")
            return layers

        # Find all FeatureType elements
        for feature_type in self._find_feature_types(feature_type_list):
            layer_info = self._parse_feature_type(feature_type)
            if layer_info and layer_info.name:
                layers[layer_info.name] = layer_info

        return layers

    def _find_feature_types(self, parent: ET.Element) -> List[ET.Element]:
        """Find all FeatureType elements under parent."""
        elements = []

        # Try WFS 2.0 namespace
        elements = parent.findall('{http://www.opengis.net/wfs/2.0}FeatureType')

        # Try WFS 1.1/1.0 namespace
        if not elements:
            elements = parent.findall('{http://www.opengis.net/wfs}FeatureType')

        # Try without namespace
        if not elements:
            elements = parent.findall('FeatureType')

        return elements

    def _parse_feature_type(self, element: ET.Element) -> Optional[WfsLayerInfo]:
        """Parse a single FeatureType element."""
        try:
            # Get name
            name = self._get_element_text(element, [
                '{http://www.opengis.net/wfs/2.0}Name',
                '{http://www.opengis.net/wfs}Name',
                'Name'
            ])

            if not name:
                return None

            # Get title
            title = self._get_element_text(element, [
                '{http://www.opengis.net/wfs/2.0}Title',
                '{http://www.opengis.net/wfs}Title',
                'Title'
            ]) or name

            # Get abstract
            abstract = self._get_element_text(element, [
                '{http://www.opengis.net/wfs/2.0}Abstract',
                '{http://www.opengis.net/wfs}Abstract',
                'Abstract'
            ]) or ""

            # Get CRS
            crs = self._parse_crs(element)

            # Get keywords
            keywords = self._parse_keywords(element)

            # Get bounding box
            bbox = self._parse_bbox(element)

            return WfsLayerInfo(
                name=name,
                title=title,
                abstract=abstract,
                keywords=keywords,
                crs=crs,
                bbox_wgs84=bbox
            )

        except Exception as e:
            log(f"[Layer Browser] Error parsing FeatureType: {e}")
            return None

    def _get_element_text(self, parent: ET.Element, paths: List[str]) -> str:
        """Get text from first matching element path."""
        for path in paths:
            el = parent.find(path)
            if el is not None and el.text:
                return el.text.strip()
        return ""

    def _parse_keywords(self, element: ET.Element) -> List[str]:
        """
        Parse ows:Keywords from FeatureType.

        Expected XML structure:
        <ows:Keywords>
            <ows:Keyword>Kultur och fritid</ows:Keyword>
            <ows:Keyword>Kultur och fritid/Rekreation</ows:Keyword>
        </ows:Keywords>
        """
        keywords = []

        # Try different namespace variants for Keywords element
        keywords_elem = None
        for path in [
            '{http://www.opengis.net/ows/1.1}Keywords',
            '{http://www.opengis.net/ows}Keywords',
            'Keywords'
        ]:
            keywords_elem = element.find(path)
            if keywords_elem is not None:
                break

        if keywords_elem is None:
            return keywords

        # Find all Keyword elements
        for kw_path in [
            '{http://www.opengis.net/ows/1.1}Keyword',
            '{http://www.opengis.net/ows}Keyword',
            'Keyword'
        ]:
            for kw in keywords_elem.findall(kw_path):
                if kw.text:
                    keywords.append(kw.text.strip())
            if keywords:
                break

        return keywords

    def _parse_crs(self, element: ET.Element) -> str:
        """
        Parse CRS from FeatureType.

        Converts URN format (urn:ogc:def:crs:EPSG::3006) to EPSG format (EPSG:3006).
        """
        crs_text = self._get_element_text(element, [
            '{http://www.opengis.net/wfs/2.0}DefaultCRS',
            '{http://www.opengis.net/wfs}DefaultSRS',
            'DefaultCRS',
            'DefaultSRS'
        ])

        if not crs_text:
            return "EPSG:4326"

        # Already EPSG format
        if crs_text.upper().startswith("EPSG:"):
            return crs_text.upper()

        # Convert URN format: urn:ogc:def:crs:EPSG::3006 -> EPSG:3006
        match = re.search(r'EPSG::?(\d+)', crs_text, re.IGNORECASE)
        if match:
            return f"EPSG:{match.group(1)}"

        return "EPSG:4326"

    def _parse_bbox(self, element: ET.Element) -> Optional[Tuple[float, float, float, float]]:
        """
        Parse WGS84 bounding box from FeatureType.

        Returns tuple of (minx, miny, maxx, maxy) or None.
        """
        bbox_elem = None
        for path in [
            '{http://www.opengis.net/ows/1.1}WGS84BoundingBox',
            '{http://www.opengis.net/ows}WGS84BoundingBox',
            'WGS84BoundingBox'
        ]:
            bbox_elem = element.find(path)
            if bbox_elem is not None:
                break

        if bbox_elem is None:
            return None

        try:
            lower = None
            upper = None

            for path in [
                '{http://www.opengis.net/ows/1.1}LowerCorner',
                '{http://www.opengis.net/ows}LowerCorner',
                'LowerCorner'
            ]:
                el = bbox_elem.find(path)
                if el is not None and el.text:
                    lower = el.text.strip()
                    break

            for path in [
                '{http://www.opengis.net/ows/1.1}UpperCorner',
                '{http://www.opengis.net/ows}UpperCorner',
                'UpperCorner'
            ]:
                el = bbox_elem.find(path)
                if el is not None and el.text:
                    upper = el.text.strip()
                    break

            if lower and upper:
                lower_parts = lower.split()
                upper_parts = upper.split()
                if len(lower_parts) >= 2 and len(upper_parts) >= 2:
                    return (
                        float(lower_parts[0]),
                        float(lower_parts[1]),
                        float(upper_parts[0]),
                        float(upper_parts[1])
                    )
        except (ValueError, IndexError):
            pass

        return None


class WfsDescribeFeatureTypeParser:
    """Parser for WFS DescribeFeatureType to extract geometry types."""

    # GML type to geometry type mapping
    GEOMETRY_TYPE_MAP = {
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

    @classmethod
    def parse_geometry_type(cls, xml_data: bytes) -> str:
        """
        Parse DescribeFeatureType response to extract geometry type.

        Args:
            xml_data: Raw XML bytes from DescribeFeatureType response

        Returns:
            Geometry type string: Point, LineString, Polygon, etc.
        """
        try:
            root = ET.fromstring(xml_data)
            return cls._find_geometry_type(root)
        except ET.ParseError as e:
            log(f"[Layer Browser] Error parsing DescribeFeatureType: {e}")
            return "Unknown"

    @classmethod
    def _find_geometry_type(cls, root: ET.Element) -> str:
        """Find geometry type from XSD schema elements."""
        # Search for xsd:element with geometry type
        namespaces = [
            '{http://www.w3.org/2001/XMLSchema}',
            '{http://www.w3.org/2001/XMLSchema-instance}',
            ''
        ]

        for ns in namespaces:
            # Find all element definitions
            for element in root.iter(f'{ns}element'):
                element_type = element.get('type', '')

                # Check if this is a geometry element
                for gml_type, geom_type in cls.GEOMETRY_TYPE_MAP.items():
                    if gml_type in element_type:
                        return geom_type

        return "Unknown"

    @classmethod
    def geometry_type_to_icon_path(cls, geometry_type: str) -> str:
        """
        Map geometry type to QGIS icon path.

        Args:
            geometry_type: Geometry type string

        Returns:
            QGIS theme icon path
        """
        icon_map = {
            'Point': '/mIconPointLayer.svg',
            'MultiPoint': '/mIconPointLayer.svg',
            'LineString': '/mIconLineLayer.svg',
            'MultiLineString': '/mIconLineLayer.svg',
            'Polygon': '/mIconPolygonLayer.svg',
            'MultiPolygon': '/mIconPolygonLayer.svg',
            'Geometry': '/mIconVector.svg',
        }
        return icon_map.get(geometry_type, '/mIconVector.svg')
