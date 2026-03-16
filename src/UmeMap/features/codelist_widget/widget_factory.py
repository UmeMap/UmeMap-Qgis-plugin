# -*- coding: utf-8 -*-
"""
CodeList Widget Factory - Registers the UmeMapCodeListSearch editor widget.

This factory creates the custom editor widget that provides searchable
autocomplete for large CodeLists via lazy-loading from the UmeMap server.
"""

from qgis.gui import QgsEditorWidgetFactory

from .config_widget import UmeMapCodeListConfigWidget
from .widget_wrapper import UmeMapCodeListWidgetWrapper


class UmeMapCodeListWidgetFactory(QgsEditorWidgetFactory):
    """Factory for creating UmeMapCodeListSearch editor widgets."""

    def __init__(self):
        """Initialize the factory with the widget display name."""
        super().__init__("UmeMap CodeList Search")

    def create(self, layer, fieldIdx, editor, parent):
        """
        Create a new widget wrapper instance.

        :param layer: The vector layer
        :param fieldIdx: The field index
        :param editor: The editor widget (may be None)
        :param parent: Parent widget
        :return: New UmeMapCodeListWidgetWrapper instance
        """
        return UmeMapCodeListWidgetWrapper(layer, fieldIdx, editor, parent)

    def configWidget(self, layer, fieldIdx, parent):
        """
        Create a configuration widget for the Layer Properties dialog.

        :param layer: The vector layer
        :param fieldIdx: The field index
        :param parent: Parent widget
        :return: New UmeMapCodeListConfigWidget instance
        """
        return UmeMapCodeListConfigWidget(layer, fieldIdx, parent)
