"""
Dialog for adding/editing WFS sources.
"""

from typing import Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QLabel,
    QDialogButtonBox, QGroupBox, QMessageBox
)
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QUrl
from qgis.gui import QgsAuthConfigSelect
from qgis.core import QgsApplication, QgsNetworkAccessManager

from .wfs_source import WfsSource


class SourceDialog(QDialog):
    """
    Dialog for adding or editing a WFS source.

    Allows configuration of:
    - Name (display name)
    - URL (WFS service endpoint)
    - Version (1.0.0, 1.1.0, 2.0.0)
    - Authentication (via QGIS auth system)
    """

    def __init__(self, parent=None, source: Optional[WfsSource] = None):
        """
        Initialize the dialog.

        Args:
            parent: Parent widget
            source: Existing source to edit, or None for new source
        """
        super().__init__(parent)
        self.source = source
        self._test_reply = None

        self._setup_ui()
        self._populate_fields()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Lägg till WFS-källa" if not self.source else "Redigera WFS-källa")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Connection details group
        connection_group = QGroupBox("Anslutningsdetaljer")
        form_layout = QFormLayout(connection_group)

        # Name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("T.ex. UmeMap WFS")
        form_layout.addRow("Namn:", self.name_input)

        # URL input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/wfs")
        form_layout.addRow("URL:", self.url_input)

        # Version selector
        self.version_combo = QComboBox()
        self.version_combo.addItems(["2.0.0", "1.1.0", "1.0.0"])
        self.version_combo.setToolTip(
            "WFS 2.0.0 rekommenderas för stöd av keywords/mapphierarki"
        )
        form_layout.addRow("Version:", self.version_combo)

        layout.addWidget(connection_group)

        # Authentication group
        auth_group = QGroupBox("Autentisering")
        auth_layout = QVBoxLayout(auth_group)

        auth_label = QLabel(
            "Välj en sparad autentiseringskonfiguration eller lämna tomt för "
            "anonyma anslutningar."
        )
        auth_label.setWordWrap(True)
        auth_layout.addWidget(auth_label)

        self.auth_select = QgsAuthConfigSelect(self, "wfs")
        auth_layout.addWidget(self.auth_select)

        layout.addWidget(auth_group)

        # Test connection button
        test_layout = QHBoxLayout()
        test_layout.addStretch()

        self.test_button = QPushButton("Testa anslutning")
        self.test_button.clicked.connect(self._test_connection)
        test_layout.addWidget(self.test_button)

        self.test_status = QLabel()
        test_layout.addWidget(self.test_status)

        layout.addLayout(test_layout)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_fields(self) -> None:
        """Populate fields from existing source."""
        if not self.source:
            return

        self.name_input.setText(self.source.name)
        self.url_input.setText(self.source.url)

        # Set version
        version_index = self.version_combo.findText(self.source.version)
        if version_index >= 0:
            self.version_combo.setCurrentIndex(version_index)

        # Set auth config
        if self.source.authcfg:
            self.auth_select.setConfigId(self.source.authcfg)

    def _on_accept(self) -> None:
        """Handle OK button click."""
        # Validate
        if not self._validate():
            return

        self.accept()

    def _validate(self) -> bool:
        """
        Validate input fields.

        Returns:
            True if valid, False otherwise
        """
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validering", "Namn krävs.")
            self.name_input.setFocus()
            return False

        if not url:
            QMessageBox.warning(self, "Validering", "URL krävs.")
            self.url_input.setFocus()
            return False

        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            QMessageBox.warning(
                self,
                "Validering",
                "URL måste börja med http:// eller https://"
            )
            self.url_input.setFocus()
            return False

        return True

    def get_source(self) -> Optional[WfsSource]:
        """
        Get the configured WFS source.

        Returns:
            WfsSource instance or None
        """
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        version = self.version_combo.currentText()
        authcfg = self.auth_select.configId() or None

        if not name or not url:
            return None

        # If editing, preserve ID
        if self.source:
            return WfsSource(
                id=self.source.id,
                name=name,
                url=url,
                version=version,
                authcfg=authcfg,
                enabled=True
            )
        else:
            return WfsSource(
                name=name,
                url=url,
                version=version,
                authcfg=authcfg,
                enabled=True
            )

    def _test_connection(self) -> None:
        """Test the WFS connection."""
        url = self.url_input.text().strip()
        if not url:
            self.test_status.setText("Ange URL först")
            return

        version = self.version_combo.currentText()
        authcfg = self.auth_select.configId()

        # Build GetCapabilities URL
        separator = '&' if '?' in url else '?'
        test_url = f"{url}{separator}SERVICE=WFS&REQUEST=GetCapabilities&VERSION={version}"

        self.test_button.setEnabled(False)
        self.test_status.setText("Testar...")

        # Create request
        request = QNetworkRequest(QUrl(test_url))

        # Use redirect policy compatible with both Qt 5 and Qt 6
        try:
            request.setAttribute(
                QNetworkRequest.RedirectPolicyAttribute,
                QNetworkRequest.NoLessSafeRedirectPolicy
            )
        except AttributeError:
            request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)

        # Add auth if configured
        if authcfg:
            auth_manager = QgsApplication.authManager()
            auth_manager.updateNetworkRequest(request, authcfg)

        # Send request
        nam = QgsNetworkAccessManager.instance()
        self._test_reply = nam.get(request)
        self._test_reply.finished.connect(self._on_test_finished)

    def _on_test_finished(self) -> None:
        """Handle test connection response."""
        self.test_button.setEnabled(True)

        if not self._test_reply:
            return

        reply = self._test_reply
        self._test_reply = None

        if reply.error():
            error_msg = reply.errorString()
            self.test_status.setText(f"Fel: {error_msg[:50]}")
            self.test_status.setStyleSheet("color: red;")
            reply.deleteLater()
            return

        # Check for valid WFS response
        content = bytes(reply.readAll())
        reply.deleteLater()

        if b'WFS_Capabilities' in content or b'FeatureTypeList' in content:
            self.test_status.setText("Anslutningen lyckades!")
            self.test_status.setStyleSheet("color: green;")
        else:
            self.test_status.setText("Inget giltigt WFS-svar")
            self.test_status.setStyleSheet("color: orange;")
