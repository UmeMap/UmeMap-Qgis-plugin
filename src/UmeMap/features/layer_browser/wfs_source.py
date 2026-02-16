"""
WFS Source data model.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class WfsSource:
    """
    Represents a configured WFS data source.

    Attributes:
        id: Unique identifier (UUID)
        name: User-friendly display name
        url: Base WFS service URL
        version: Preferred WFS version (default: 2.0.0)
        authcfg: QGIS authentication config ID (optional)
        enabled: Whether the source is active
        last_refresh: Timestamp of last successful refresh
    """
    name: str
    url: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "2.0.0"
    authcfg: Optional[str] = None
    enabled: bool = True
    last_refresh: Optional[datetime] = None

    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        # Ensure URL doesn't have trailing slash
        self.url = self.url.rstrip('/')

        # Ensure version is valid
        valid_versions = ("1.0.0", "1.1.0", "2.0.0")
        if self.version not in valid_versions:
            self.version = "2.0.0"

    def get_capabilities_url(self) -> str:
        """
        Build the GetCapabilities URL for this source.

        Returns:
            Full URL for GetCapabilities request
        """
        separator = '&' if '?' in self.url else '?'
        return f"{self.url}{separator}SERVICE=WFS&REQUEST=GetCapabilities&VERSION={self.version}"

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'version': self.version,
            'authcfg': self.authcfg,
            'enabled': self.enabled,
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'WfsSource':
        """
        Create WfsSource from dictionary.

        Args:
            data: Dictionary with source data

        Returns:
            WfsSource instance
        """
        last_refresh = None
        if data.get('last_refresh'):
            try:
                last_refresh = datetime.fromisoformat(data['last_refresh'])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            url=data.get('url', ''),
            version=data.get('version', '2.0.0'),
            authcfg=data.get('authcfg'),
            enabled=data.get('enabled', True),
            last_refresh=last_refresh,
        )
