# coding=utf-8
"""Dialog test.

Copyright (c) 2022-2026 UmeMap - MIT License
"""

__author__ = 'marcus.lindh@umea.se'
__date__ = '2022-06-10'
__copyright__ = 'Copyright 2022-2026, UmeMap'

import unittest

from qgis.PyQt.QtWidgets import QDialogButtonBox, QDialog

from UmeMap.ui.dialogs import UmeMapDialog

from utilities import get_qgis_app
QGIS_APP = get_qgis_app()


class UmeMapDialogTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.dialog = UmeMapDialog(None)

    def tearDown(self):
        """Runs after each test."""
        self.dialog = None

    def test_dialog_ok(self):
        """Test we can click OK."""
        button = self.dialog.button_box.button(QDialogButtonBox.Ok)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Accepted)

    def test_dialog_cancel(self):
        """Test we can click cancel."""
        button = self.dialog.button_box.button(QDialogButtonBox.Cancel)
        button.click()
        result = self.dialog.result()
        self.assertEqual(result, QDialog.Rejected)

if __name__ == "__main__":
    suite = unittest.makeSuite(UmeMapDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
