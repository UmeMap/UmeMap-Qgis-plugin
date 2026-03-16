# -*- coding: utf-8 -*-
"""
CodeList Config Widget - Configuration UI shown in Layer Properties.

This widget is displayed when the user selects UmeMapCodeListSearch
as the editor widget type in the Layer Properties dialog. The actual
configuration (wfs_url, codelist_guid) is set by the server via
GetVectorStyle, so this config widget is informational only.
"""

from qgis.gui import QgsEditorConfigWidget
from qgis.PyQt.QtWidgets import QVBoxLayout, QLabel


class UmeMapCodeListConfigWidget(QgsEditorConfigWidget):
    """Configuration widget for UmeMapCodeListSearch editor widget."""

    def __init__(self, layer, fieldIdx, parent):
        """
        Initialize the config widget.

        :param layer: The vector layer
        :param fieldIdx: The field index
        :param parent: Parent widget
        """
        super().__init__(layer, fieldIdx, parent)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("UmeMap CodeList Search Widget"))
        layout.addWidget(QLabel("Configured via server style (GetVectorStyle)."))
        layout.addWidget(QLabel("Parameters: wfs_url, codelist_guid"))
        self.setLayout(layout)

    def config(self):
        """
        Return the current configuration.

        :return: Configuration dictionary
        """
        return {}

    def setConfig(self, config):
        """
        Set configuration from existing config dictionary.

        :param config: Configuration dictionary
        """
        pass
