# -*- coding: utf-8 -*-
"""
UmeMap QGIS Plugin - Main plugin class.

UmeMap layer management is a plugin which helps with styles for vector layers
that come from a UmeMap server and form management.
"""

import os.path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject
from qgis.gui import QgsDockWidget

# Initialize Qt resources from file resources.py
from .resources import *

# Import modules
from .style_manager import StyleService, StyleActions
from .layer_browser import BrowserDock
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

        # Layer browser dock (created in initGui)
        self.browser_dock = None

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

    def _cleanup_stale_artifacts(self):
        """Remove any leftover UI artifacts from a previous plugin installation.

        When a plugin is reinstalled without restarting QGIS, the old unload()
        may not have run completely, leaving orphaned actions and dock widgets.
        """
        main_window = self.iface.mainWindow()

        # Remove stale dock widgets from a previous instance
        for dock in main_window.findChildren(QgsDockWidget, 'UmeMapLayerBrowserDock'):
            self.iface.removeDockWidget(dock)
            dock.deleteLater()

        # Remove stale toolbar icons and menu entries
        # Find actions by their text to catch orphans from previous instances
        web_menu = self.iface.webMenu()
        if web_menu:
            plugin_menu = None
            for action in web_menu.actions():
                menu = action.menu()
                if menu and self.menu in action.text():
                    plugin_menu = menu
                    break
            if plugin_menu:
                for action in plugin_menu.actions():
                    self.iface.removePluginWebMenu(self.menu, action)
                    self.iface.removeToolBarIcon(action)

    def _toggle_browser_dock(self, checked):
        """Toggle the layer browser dock visibility."""
        if self.browser_dock:
            self.browser_dock.setVisible(checked)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Clean up any stale artifacts from a previous plugin installation
        self._cleanup_stale_artifacts()

        # Register style management context menu
        self.style_actions.register()

        # Setup layer browser dock widget
        self.browser_dock = BrowserDock(self.iface)
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.browser_dock)
        self.browser_dock.hide()

        # Add toggle action for layer browser
        icon_path = os.path.join(self.plugin_dir, 'icons', 'browser.svg')
        self.add_action(
            icon_path,
            text=self.tr('UmeMap Layer Browser'),
            callback=self._toggle_browser_dock,
            parent=self.iface.mainWindow(),
            add_to_toolbar=True,
            add_to_menu=True,
        )

        # Sync action checked state with dock visibility
        if self.actions:
            browser_action = self.actions[-1]
            browser_action.setCheckable(True)
            self.browser_dock.visibilityChanged.connect(browser_action.setChecked)

        # Deferred loading of saved sources (after event loop starts)
        QTimer.singleShot(0, self.browser_dock.load_sources)

        # Will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # Unregister style actions
        self.style_actions.unregister()

        # Remove layer browser dock
        if self.browser_dock:
            self.iface.removeDockWidget(self.browser_dock)
            self.browser_dock.deleteLater()
            self.browser_dock = None

        # Remove toolbar actions and menu entries
        for action in self.actions:
            self.iface.removePluginWebMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
            action.deleteLater()
        self.actions.clear()

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
