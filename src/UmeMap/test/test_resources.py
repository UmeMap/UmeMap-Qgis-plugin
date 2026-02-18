# coding=utf-8
"""Resources test.

Copyright (c) 2022-2026 UmeMap - MIT License
"""

__author__ = 'marcus.lindh@umea.se'
__date__ = '2022-06-10'
__copyright__ = 'Copyright 2022-2026, UmeMap'

import unittest

from qgis.PyQt.QtGui import QIcon


class UmeMapResourcesTest(unittest.TestCase):
    """Test resources work."""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_icon_png(self):
        """Test that the plugin icon loads correctly."""
        path = ':/plugins/UmeMap/icon.png'
        icon = QIcon(path)
        self.assertFalse(icon.isNull())

if __name__ == "__main__":
    suite = unittest.makeSuite(UmeMapResourcesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
