# -*- coding: utf-8 -*-
"""
WFS Utilities - Parsing WFS data sources.
"""

from typing import Tuple, Optional

from qgis.core import QgsDataSourceUri, QgsMapLayer


def parse_wfs_data_source(layer: QgsMapLayer) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract WFS URL and layer name from a QGIS layer's data source.

    :param layer: QGIS map layer (expected to be WFS)
    :return: Tuple of (wfs_url, layer_name), both None if parsing fails
    """
    try:
        provider = layer.dataProvider()
        if not provider:
            return None, None

        ds = QgsDataSourceUri(provider.dataSourceUri())

        wfs_url = ds.param("url")
        layer_name = ds.param("typename")

        # Remove possible query parameters from URL
        if wfs_url:
            wfs_url = wfs_url.split("?")[0]

        return wfs_url, layer_name

    except Exception:
        return None, None


def build_wfs_layer_uri(url: str, typename: str, crs: Optional[str] = None,
                        authcfg: Optional[str] = None, restrict_to_view: bool = True) -> str:
    """
    Build a QGIS WFS provider URI for a layer.

    :param url: WFS service URL
    :param typename: WFS typename (layer name)
    :param crs: Optional CRS to request features in, e.g. 'EPSG:3006'
    :param authcfg: Optional QGIS auth config ID
    :param restrict_to_view: Only fetch features overlapping the current map view
        (QGIS "Only request features overlapping the view extent"). Without it the
        whole layer is downloaded, which can be hundreds of thousands of features.
    :return: URI string for QgsVectorLayer(uri, name, 'WFS')
    """
    uri_parts = [
        f"url='{url}'",
        f"typename='{typename}'",
        "version='2.0.0'",
    ]
    if crs:
        uri_parts.append(f"srsname='{crs}'")
    if restrict_to_view:
        uri_parts.append("restrictToRequestBBOX='1'")
    if authcfg:
        uri_parts.append(f"authcfg='{authcfg}'")

    return " ".join(uri_parts)
