# -*- coding: utf-8 -*-
"""
XML Utilities - Safe parsing of XML from WFS servers.

XML attacks (entity expansion such as "billion laughs", external entities)
all need a DTD. WFS responses never contain one, so documents with a DTD are
rejected before they reach the parser, like defusedxml does, without adding
defusedxml as a dependency to the plugin.
"""

import re
# XML is only parsed through parse_xml, which rejects DTDs
import xml.etree.ElementTree as ET  # nosec B405

__all__ = ["ET", "parse_xml"]

_DTD_PATTERN = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def parse_xml(xml_data: bytes) -> ET.Element:
    """
    Parse XML received from a server.

    :param xml_data: Raw XML bytes
    :return: The root element
    :raises ET.ParseError: If the XML is invalid or contains a DTD
    """
    if _DTD_PATTERN.search(_as_text(xml_data)):
        raise ET.ParseError("XML with a DTD (DOCTYPE/ENTITY declaration) is not accepted")

    # Safe: DTDs, which XML entity attacks need, are rejected above
    return ET.fromstring(xml_data)  # nosec B314


def _as_text(xml_data: bytes) -> str:
    """Decode the XML for the DTD check, handling UTF-16 documents as well."""
    if xml_data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return xml_data.decode("utf-16", errors="ignore")
    if xml_data.startswith(b"\x00"):
        return xml_data.decode("utf-16-be", errors="ignore")
    if b"\x00" in xml_data[:4]:
        return xml_data.decode("utf-16-le", errors="ignore")
    return xml_data.decode("utf-8", errors="ignore")
