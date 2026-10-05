# -*- coding: utf-8 -*-
"""
UmeMap API Client - HTTP communication with UmeMap server.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple

from qgis.PyQt.QtXml import QDomDocument

from .http_client import http_get, http_post


def parse_style_document(content: bytes) -> Tuple[Optional[QDomDocument], str]:
    """
    Parse a QML style returned by GetVectorStyle.

    A response that is not a QGIS style with field configuration (e.g. an error
    page) is rejected, so it never replaces the layer's last known settings.

    :param content: Raw response body
    :return: (document, "") if valid, (None, reason) otherwise
    """
    style_doc = QDomDocument("qgis")
    result = style_doc.setContent(content)
    # setContent returns (success, errorMsg, errorLine, errorColumn)
    if isinstance(result, tuple):
        if not result[0]:
            return None, f"invalid XML: {result[1]}"
    elif not result:
        return None, "invalid XML"

    root = style_doc.documentElement()
    if root.tagName() != "qgis":
        return None, f"unexpected root element '{root.tagName()}'"
    if root.firstChildElement("fieldConfiguration").isNull():
        return None, "style has no field configuration"

    return style_doc, ""


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
        return UmeMapApiClient.check_umemap_server(wfs_url)[0] is True

    @staticmethod
    def check_umemap_server(wfs_url: str) -> Tuple[Optional[bool], str]:
        """
        Check if WFS server is a UmeMap server, telling a server that answered
        apart from one that could not be reached.

        :param wfs_url: Base URL of the WFS server
        :return: (True/False, "") when the server answered, (None, reason) when it could not be reached
        """
        response = http_get(wfs_url.rstrip('/') + "?request=ServerInfo", timeout=10)

        if response.status_code == 0 or response.status_code >= 500:
            return None, response.describe_error()

        try:
            server_info = response.json()
            return server_info.get("softwareName") == "UmeMap", ""
        except Exception:
            return False, ""

    def get_vector_style(self, layer_name: str) -> Optional[QDomDocument]:
        """
        Fetch vector style (QML) from UmeMap server.

        :param layer_name: Name of the WFS layer
        :return: QDomDocument with style, or None if failed
        """
        content, _, _ = self.fetch_vector_style(layer_name)
        if content is None:
            return None
        return parse_style_document(content)[0]

    def fetch_vector_style(self, layer_name: str) -> Tuple[Optional[bytes], str, bool]:
        """
        Fetch the raw vector style (QML) from UmeMap server.

        :param layer_name: Name of the WFS layer
        :return: (content, "", False) on success, (None, reason, unreachable) if failed, where
            unreachable is True when the server itself can't be reached (timeout, connection
            error, bad gateway/unavailable) rather than failing for this layer only
        """
        url = f"{self.base_url}?REQUEST=GetVectorStyle&TYPENAME={layer_name}"
        response = http_get(url, headers=self.headers, timeout=30)

        if response.status_code != 200:
            return None, response.describe_error(), response.unreachable

        return response.content, "", False

    def save_vector_style(self, layer_name: str, qml_data: bytes) -> ApiResponse:
        """
        Save vector style (QML) to UmeMap server.

        :param layer_name: Name of the WFS layer
        :param qml_data: QML file content as bytes
        :return: ApiResponse with result
        """
        url = f"{self.base_url}?request=SaveVectorStyle&typename={layer_name}"

        # Redirects are followed by the QGIS network stack with the same method and body
        response = http_post(url, qml_data, headers=self.headers, timeout=30)

        if response.timed_out:
            return ApiResponse(
                status="error",
                data=None,
                message="Request timed out",
                code="TIMEOUT"
            )

        if response.status_code == 0:
            return ApiResponse(
                status="error",
                data=None,
                message=response.describe_error(),
                code="UNKNOWN_ERROR"
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
