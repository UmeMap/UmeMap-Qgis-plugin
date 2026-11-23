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
    show_popup(title, message, QMessageBox.Icon.Critical)


def show_success_popup(title: str, message: str) -> None:
    """
    Display a success/info popup dialog.

    :param title: Dialog title
    :param message: Success message to display
    """
    show_popup(title, message, QMessageBox.Icon.Information)


def show_popup(title: str, message: str, icon=QMessageBox.Icon.Information) -> None:
    """
    Display a popup dialog with the given icon type.

    :param title: Dialog title
    :param message: Message to display
    :param icon: QMessageBox icon type (Information, Warning, Critical, Question)
    """
    msg_box = QMessageBox()
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.exec()


def log(message: str, level: Qgis.MessageLevel = Qgis.MessageLevel.Info) -> None:
    """
    Write log messages to both console and QGIS log system.

    :param message: Message to log
    :param level: Log level (Qgis.MessageLevel.Info, Qgis.MessageLevel.Warning, Qgis.MessageLevel.Critical)
    """
    try:
        print(message)
        QgsMessageLog.logMessage(message, "UmeMap", level)
    except Exception:
        # Fallback if logging system is not available
        print(f"[LOG-ERROR] {message}")
