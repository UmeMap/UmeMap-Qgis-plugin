# -*- coding: utf-8 -*-
"""
Authentication Manager - Handles extraction of auth headers from QGIS layers.
"""

from typing import Dict

from qgis.core import QgsApplication, QgsAuthMethodConfig, QgsDataSourceUri, QgsMapLayer


class AuthManager:
    """Manages authentication for UmeMap API requests."""

    @staticmethod
    def get_headers_from_layer(layer: QgsMapLayer) -> Dict[str, str]:
        """
        Extract HTTP headers from the layer's authentication configuration.

        :param layer: QGIS map layer with potential auth configuration
        :return: Dictionary of HTTP headers
        """
        headers = {}

        try:
            ds = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
            auth_cfg = ds.authConfigId()

            if not auth_cfg:
                return headers

            auth_manager = QgsApplication.authManager()
            if not auth_manager:
                return headers

            # Get the authentication configuration
            auth_config = QgsAuthMethodConfig()
            auth_manager.loadAuthenticationConfig(auth_cfg, auth_config, True)

            # Extract all headers from the configuration map
            config_map = auth_config.configMap()
            for key, value in config_map.items():
                headers[key] = value

        except Exception:
            # Silently fail - caller should handle missing headers
            pass

        return headers
