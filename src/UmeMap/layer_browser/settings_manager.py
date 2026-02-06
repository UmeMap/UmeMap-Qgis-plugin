"""
Settings manager for persistent storage of WFS sources.
"""

from typing import List, Optional
from qgis.core import QgsSettings

from .wfs_source import WfsSource


class SettingsManager:
    """
    Manages persistent storage of plugin settings using QgsSettings.

    Settings are stored under the 'UmeMapLayerBrowser' prefix.
    """

    PREFIX = "UmeMapLayerBrowser"

    def __init__(self):
        """Initialize the settings manager."""
        self._settings = QgsSettings()

    def save_source(self, source: WfsSource) -> None:
        """
        Save a WFS source to settings.

        Args:
            source: WfsSource to save
        """
        base = f"{self.PREFIX}/sources/{source.id}"
        self._settings.setValue(f"{base}/name", source.name)
        self._settings.setValue(f"{base}/url", source.url)
        self._settings.setValue(f"{base}/version", source.version)
        self._settings.setValue(f"{base}/authcfg", source.authcfg or "")
        self._settings.setValue(f"{base}/enabled", source.enabled)
        if source.last_refresh:
            self._settings.setValue(f"{base}/last_refresh", source.last_refresh.isoformat())
        else:
            self._settings.remove(f"{base}/last_refresh")

    def load_sources(self) -> List[WfsSource]:
        """
        Load all WFS sources from settings.

        Returns:
            List of WfsSource instances
        """
        sources = []
        self._settings.beginGroup(f"{self.PREFIX}/sources")

        for source_id in self._settings.childGroups():
            source_data = {
                'id': source_id,
                'name': self._settings.value(f"{source_id}/name", ""),
                'url': self._settings.value(f"{source_id}/url", ""),
                'version': self._settings.value(f"{source_id}/version", "2.0.0"),
                'authcfg': self._settings.value(f"{source_id}/authcfg", "") or None,
                'enabled': self._settings.value(f"{source_id}/enabled", True, type=bool),
                'last_refresh': self._settings.value(f"{source_id}/last_refresh", None),
            }

            # Only add sources with valid URL
            if source_data['url']:
                sources.append(WfsSource.from_dict(source_data))

        self._settings.endGroup()
        return sources

    def remove_source(self, source_id: str) -> None:
        """
        Remove a WFS source from settings.

        Args:
            source_id: ID of source to remove
        """
        self._settings.remove(f"{self.PREFIX}/sources/{source_id}")

    def get_source(self, source_id: str) -> Optional[WfsSource]:
        """
        Get a specific WFS source by ID.

        Args:
            source_id: ID of source to get

        Returns:
            WfsSource or None if not found
        """
        base = f"{self.PREFIX}/sources/{source_id}"
        url = self._settings.value(f"{base}/url", "")

        if not url:
            return None

        source_data = {
            'id': source_id,
            'name': self._settings.value(f"{base}/name", ""),
            'url': url,
            'version': self._settings.value(f"{base}/version", "2.0.0"),
            'authcfg': self._settings.value(f"{base}/authcfg", "") or None,
            'enabled': self._settings.value(f"{base}/enabled", True, type=bool),
            'last_refresh': self._settings.value(f"{base}/last_refresh", None),
        }

        return WfsSource.from_dict(source_data)

    # Plugin preferences

    def get_auto_refresh(self) -> bool:
        """Get auto-refresh preference."""
        return self._settings.value(f"{self.PREFIX}/preferences/auto_refresh", False, type=bool)

    def set_auto_refresh(self, value: bool) -> None:
        """Set auto-refresh preference."""
        self._settings.setValue(f"{self.PREFIX}/preferences/auto_refresh", value)

    def get_expand_on_start(self) -> bool:
        """Get expand-on-start preference."""
        return self._settings.value(f"{self.PREFIX}/preferences/expand_on_start", True, type=bool)

    def set_expand_on_start(self, value: bool) -> None:
        """Set expand-on-start preference."""
        self._settings.setValue(f"{self.PREFIX}/preferences/expand_on_start", value)

    def get_show_empty_folders(self) -> bool:
        """Get show-empty-folders preference."""
        return self._settings.value(f"{self.PREFIX}/preferences/show_empty_folders", False, type=bool)

    def set_show_empty_folders(self, value: bool) -> None:
        """Set show-empty-folders preference."""
        self._settings.setValue(f"{self.PREFIX}/preferences/show_empty_folders", value)
