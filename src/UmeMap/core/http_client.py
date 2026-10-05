# -*- coding: utf-8 -*-
"""
HTTP Client - Blocking HTTP requests through the QGIS network stack.

Requests go through QgsNetworkAccessManager, so SSL certificates are verified
against the system's trusted certificates and the SSL server exceptions in the
QGIS authentication manager, and the proxy settings in QGIS are used.

Redirects are followed here rather than by Qt/QGIS, so the method, body and
headers (e.g. the API key) are kept on the redirected request.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from qgis.PyQt.QtCore import QEventLoop, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.core import QgsNetworkAccessManager


# HTTP status codes meaning the server (or the proxy in front of it) is down
UNREACHABLE_STATUS_CODES = (502, 503, 504)

REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)
MAX_REDIRECTS = 5


@dataclass
class HttpResponse:
    """Result of an HTTP request."""
    status_code: int  # 0 if no HTTP response was received
    content: bytes
    error: str  # Why no response was received, empty otherwise
    timed_out: bool = False

    @property
    def unreachable(self) -> bool:
        """True if the server itself could not be reached (no response, bad gateway etc.)."""
        return self.status_code == 0 or self.status_code in UNREACHABLE_STATUS_CODES

    def json(self) -> Any:
        """Parse the response body as JSON."""
        return json.loads(self.content.decode("utf-8"))

    def describe_error(self) -> str:
        """Short description of why the request failed, for the QGIS log."""
        if self.timed_out:
            return "timeout"
        if self.status_code == 0:
            return self.error or "connection error"
        return f"HTTP {self.status_code}"


def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> HttpResponse:
    """
    Send a blocking GET request.

    :param url: Request URL
    :param headers: HTTP headers, e.g. from AuthManager.get_headers_from_layer
    :param timeout: Timeout in seconds
    :return: The response, status_code 0 if the server could not be reached
    """
    return _send("GET", url, None, headers or {}, timeout)


def http_post(url: str, data: bytes, headers: Optional[Dict[str, str]] = None, timeout: int = 30,
              content_type: str = "application/xml") -> HttpResponse:
    """
    Send a blocking POST request.

    :param url: Request URL
    :param data: Request body
    :param headers: HTTP headers, e.g. from AuthManager.get_headers_from_layer
    :param timeout: Timeout in seconds
    :param content_type: Content-Type of the body
    :return: The response, status_code 0 if the server could not be reached
    """
    return _send("POST", url, data, dict(headers or {}, **{"Content-Type": content_type}), timeout)


def _send(method: str, url: str, data: Optional[bytes], headers: Dict[str, str], timeout: int) -> HttpResponse:
    request_url = QUrl(url)
    for _ in range(MAX_REDIRECTS + 1):
        reply = _send_once(method, request_url, data, headers, timeout)
        try:
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            status_code = int(status) if status else 0
            location = reply.rawHeader(b"Location").data().decode("utf-8", errors="ignore")

            if status_code in REDIRECT_STATUS_CODES and location:
                request_url = reply.url().resolved(QUrl(location))
                if status_code == 303:
                    method, data = "GET", None
                continue

            error = reply.error()
            return HttpResponse(
                status_code=status_code,
                content=bytes(reply.readAll()),
                error="" if status_code else reply.errorString(),
                timed_out=not status_code and error in _TIMEOUT_ERRORS,
            )
        finally:
            reply.deleteLater()

    return HttpResponse(status_code=0, content=b"", error=f"more than {MAX_REDIRECTS} redirects")


def _send_once(method: str, url: QUrl, data: Optional[bytes], headers: Dict[str, str],
               timeout: int) -> QNetworkReply:
    """Send one request and wait for the reply without letting Qt follow redirects."""
    request = QNetworkRequest(url)
    for name, value in headers.items():
        request.setRawHeader(str(name).encode("utf-8"), str(value).encode("utf-8"))
    request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.ManualRedirectPolicy)
    request.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.AlwaysNetwork)
    if hasattr(request, "setTransferTimeout"):  # Qt 5.15+
        request.setTransferTimeout(timeout * 1000)

    nam = QgsNetworkAccessManager.instance()
    reply = nam.post(request, data or b"") if method == "POST" else nam.get(request)

    if not reply.isFinished():
        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        loop.exec_(QEventLoop.ExcludeUserInputEvents)
    return reply


# Errors reported when a request is aborted because it took too long
_TIMEOUT_ERRORS = tuple(
    getattr(QNetworkReply, name) for name in ("OperationCanceledError", "TimeoutError")
    if hasattr(QNetworkReply, name)
)
