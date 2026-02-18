# -*- coding: utf-8 -*-
"""
UmeMap Dialogs - UI dialogs for the plugin.
"""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets


# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'UmeMap_dialog_base.ui'))


class UmeMapDialog(QtWidgets.QDialog, FORM_CLASS):
    """Dialog for UmeMap connection configuration."""

    def __init__(self, parent=None):
        """Constructor."""
        super(UmeMapDialog, self).__init__(parent)
        self.setupUi(self)
