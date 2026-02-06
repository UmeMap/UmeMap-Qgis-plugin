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
        ds = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
        url = str(ds.encodedUri(), 'UTF-8')

        wfs_url = None
        layer_name = None

        for value in url.split("&"):
            vals = value.split("=")
            if len(vals) >= 2:
                if vals[0] == "url":
                    wfs_url = vals[1]
                elif vals[0] == "typename":
                    layer_name = vals[1]

        # Remove possible query parameters from URL
        if wfs_url:
            wfs_url = wfs_url.split("?")[0]

        return wfs_url, layer_name

    except Exception:
        return None, None
