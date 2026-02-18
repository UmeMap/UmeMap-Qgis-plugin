# -*- coding: utf-8 -*-
"""
UmeMap API Client - HTTP communication with UmeMap server.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import requests

from qgis.PyQt.QtXml import QDomDocument


@dataclass
class ApiResponse:
    """Response structure from UmeMap API."""
    status: str
    data: Optional[Dict]
    message: str
    code: str


class UmeMapApiClient:
    """Client for communicating with UmeMap server API."""

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize API client.

        :param base_url: Base URL of the UmeMap WFS server
        :param headers: Optional HTTP headers for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {}

    @staticmethod
    def is_umemap_server(wfs_url: str) -> bool:
        """
        Check if WFS server is a UmeMap server.

        :param wfs_url: Base URL of the WFS server
        :return: True if server is UmeMap, False otherwise
        """
        try:
            url = wfs_url.rstrip('/') + "?request=ServerInfo"
            resp = requests.get(url, verify=False, timeout=10)
            server_info = resp.json()
            return server_info.get("softwareName") == "UmeMap"
        except Exception:
            return False

    def get_vector_style(self, layer_name: str) -> Optional[QDomDocument]:
        """
        Fetch vector style (QML) from UmeMap server.

        :param layer_name: Name of the WFS layer
        :return: QDomDocument with style, or None if failed
        """
        try:
            url = f"{self.base_url}?REQUEST=GetVectorStyle&TYPENAME={layer_name}"
            response = requests.get(url, headers=self.headers, verify=False, timeout=30)

            if response.status_code != 200:
                return None

            style_doc = QDomDocument("qgis")
            if not style_doc.setContent(response.content):
                return None

            return style_doc

        except Exception:
            return None

    def save_vector_style(self, layer_name: str, qml_data: bytes) -> ApiResponse:
        """
        Save vector style (QML) to UmeMap server.

        :param layer_name: Name of the WFS layer
        :param qml_data: QML file content as bytes
        :return: ApiResponse with result
        """
        url = f"{self.base_url}?request=SaveVectorStyle&typename={layer_name}"

        try:
            response = requests.post(
                url,
                data=qml_data,
                headers=self.headers,
                verify=False,
                allow_redirects=False,
                timeout=30
            )

            # Handle redirect
            if response.status_code == 302:
                new_url = response.headers.get('Location')
                if new_url:
                    response = requests.post(
                        new_url,
                        data=qml_data,
                        headers=self.headers,
                        verify=False,
                        allow_redirects=False,
                        timeout=30
                    )

            # Handle authentication error
            if response.status_code == 401:
                return ApiResponse(
                    status="error",
                    data=None,
                    message="The API key is invalid or missing. Please check your authentication configuration.",
                    code="AUTH_ERROR"
                )

            # Handle success
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    return ApiResponse(**response_data)
                except Exception as e:
                    return ApiResponse(
                        status="error",
                        data=None,
                        message=f"Error interpreting response: {str(e)}",
                        code="PARSE_ERROR"
                    )

            # Handle other errors
            try:
                response_data = response.json()
                return ApiResponse(**response_data)
            except Exception:
                return ApiResponse(
                    status="error",
                    data=None,
                    message=f"An error occurred. HTTP status code: {response.status_code}",
                    code="HTTP_ERROR"
                )

        except requests.exceptions.Timeout:
            return ApiResponse(
                status="error",
                data=None,
                message="Request timed out",
                code="TIMEOUT"
            )
        except Exception as e:
            return ApiResponse(
                status="error",
                data=None,
                message=str(e),
                code="UNKNOWN_ERROR"
            )
