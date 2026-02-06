# -*- coding: utf-8 -*-
"""
UmeMap QGIS Plugin - Main plugin class.

UmeMap layer management is a plugin which helps with styles for vector layers
that come from a UmeMap server and form management.
"""

import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject

# Initialize Qt resources from file resources.py
from .resources import *

# Import modules
from .style_manager import StyleService, StyleActions
from .ui import UmeMapDialog


class UmeMap:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """
        Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'UmeMap_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&UmeMap layer managment')

        # Check if plugin was started the first time in current QGIS session
        self.first_start = None

        # Initialize services
        self.style_service = StyleService(self.tr)
        self.style_actions = StyleActions(iface, self.tr)

        # Connect signals
        QgsProject.instance().layerWasAdded.connect(self.style_service.on_layer_added)

    def tr(self, message):
        """
        Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString
        :returns: Translated version of message.
        :rtype: QString
        """
        return QCoreApplication.translate('UmeMap', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """
        Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action.
        :param text: Text that should be shown in menu items for this action.
        :param callback: Function to be called when the action is triggered.
        :param enabled_flag: A flag indicating if the action should be enabled.
        :param add_to_menu: Flag indicating whether to add to menu.
        :param add_to_toolbar: Flag indicating whether to add to toolbar.
        :param status_tip: Optional text to show in popup on hover.
        :param whats_this: Optional text for status bar on hover.
        :param parent: Parent widget for the new action.
        :returns: The action that was created.
        :rtype: QAction
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Register style management context menu
        self.style_actions.register()

        # Will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # Unregister style actions
        self.style_actions.unregister()

        # Remove toolbar actions
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&UmeMap layer managment'),
                action)
            self.iface.removeToolBarIcon(action)

        # Disconnect signals
        try:
            QgsProject.instance().layerWasAdded.disconnect(self.style_service.on_layer_added)
        except Exception:
            pass

    def run(self):
        """Run method that performs all the real work."""
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = UmeMapDialog()

        # Show the dialog
        self.dlg.show()

        # Run the dialog event loop
        result = self.dlg.exec_()

        # See if OK was pressed
        if result:
            # Do something useful here
            pass
