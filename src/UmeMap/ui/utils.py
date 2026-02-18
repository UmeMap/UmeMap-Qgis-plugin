# -*- coding: utf-8 -*-
"""
UI Utilities - Helper functions for UI operations.
"""

from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import Qgis, QgsMessageLog


def show_error_popup(title: str, message: str) -> None:
    """
    Display an error popup dialog.

    :param title: Dialog title
    :param message: Error message to display
    """
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.exec_()


def log(message: str, level: Qgis.MessageLevel = Qgis.Info) -> None:
    """
    Write log messages to both console and QGIS log system.

    :param message: Message to log
    :param level: Log level (Qgis.Info, Qgis.Warning, Qgis.Critical)
    """
    try:
        print(message)
        QgsMessageLog.logMessage(message, "UmeMap", level)
    except Exception:
        # Fallback if logging system is not available
        print(f"[LOG-ERROR] {message}")
