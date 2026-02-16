# -*- coding: utf-8 -*-
"""
UmeMap QGIS Plugin - Layer management for UmeMap WFS servers.

Copyright (c) 2022 UmeMap
Licensed under the MIT License. See LICENSE file for details.

This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load UmeMap class from file UmeMap.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .plugin import UmeMap

    return UmeMap(iface)
