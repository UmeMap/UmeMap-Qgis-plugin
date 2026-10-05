# -*- coding: utf-8 -*-
"""
Translations - Dictionary based translator for the plugin's UI strings.

Source strings are written in English and translated with tr()/QCoreApplication.translate
using the 'UmeMap' context. Translations are kept here as plain Python so no Qt
build step (lrelease) is needed to produce .qm files.
"""

from typing import Dict, Optional

from qgis.PyQt.QtCore import QTranslator


TRANSLATION_CONTEXT = "UmeMap"

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "sv": {
        "&UmeMap layer managment": "&UmeMap lagerhantering",
        "UmeMap": "UmeMap",
        "UmeMap Layer Browser": "UmeMap Layer Browser",

        # Save style
        "Save Style To UmeMap": "Spara stil till UmeMap",
        "Save styles - Error": "Spara stil - Fel",
        "No active layer selected.": "Inget aktivt lager är valt.",
        "Save": "Spara",
        "Saved styles": "Stilen har sparats",
        "Authentication error": "Autentiseringsfel",
        "The API key is invalid or missing. Please check your authentication configuration.":
            "API-nyckeln är ogiltig eller saknas. Kontrollera autentiseringskonfigurationen.",
        "Could not parse WFS data source": "Kunde inte tolka WFS-datakällan",
        "Server is not a UmeMap server": "Servern är inte en UmeMap-server",

        # Update style
        "Update Style From UmeMap": "Uppdatera stil från UmeMap",
        "Update Styles On All UmeMap Layers": "Uppdatera stil på alla UmeMap-lager",
        "Update style": "Uppdatera stil",
        "Update style - Error": "Uppdatera stil - Fel",
        "The layer is not a UmeMap layer.": "Lagret är inte ett UmeMap-lager.",
        "Style updated on '{0}'.": "Stilen har uppdaterats på '{0}'.",
        "Could not update style on '{0}'. See the UmeMap log for details.":
            "Kunde inte uppdatera stilen på '{0}'. Se UmeMap-loggen för detaljer.",
        "No UmeMap layers in the project.": "Det finns inga UmeMap-lager i projektet.",
        "Update the style on {0} UmeMap layers from the server?\n\n"
        "Symbology and other settings made in QGIS will be replaced.":
            "Vill du uppdatera stilen på {0} UmeMap-lager från servern?\n\n"
            "Symbologi och andra inställningar som gjorts i QGIS ersätts.",
        "Style updated on {0} of {1} UmeMap layers.": "Stilen har uppdaterats på {0} av {1} UmeMap-lager.",

        # Update attribute settings
        "Update Attribute Settings From UmeMap": "Uppdatera attributinställningar från UmeMap",
        "Update Attribute Settings On All UmeMap Layers": "Uppdatera attributinställningar på alla UmeMap-lager",
        "Update attribute settings": "Uppdatera attributinställningar",
        "Update attribute settings - Error": "Uppdatera attributinställningar - Fel",
        "Attribute settings updated on '{0}'.": "Attributinställningarna har uppdaterats på '{0}'.",
        "Could not update attribute settings on '{0}'. "
        "The layer keeps its current settings, see the UmeMap log for details.":
            "Kunde inte uppdatera attributinställningarna på '{0}'. "
            "Lagret behåller sina nuvarande inställningar, se UmeMap-loggen för detaljer.",
        "Attribute settings updated on {0} of {1} UmeMap layers.":
            "Attributinställningarna har uppdaterats på {0} av {1} UmeMap-lager.",
        "Attribute settings updated on {0} of {1} UmeMap layers. See the UmeMap log for details.":
            "Attributinställningarna har uppdaterats på {0} av {1} UmeMap-lager. Se UmeMap-loggen för detaljer.",
    },
}


class DictTranslator(QTranslator):
    """QTranslator that looks up translations in a Python dictionary."""

    def __init__(self, messages: Dict[str, str], parent=None):
        super().__init__(parent)
        self._messages = messages

    def translate(self, context: str, source_text: str, disambiguation: Optional[str] = None, n: int = -1) -> Optional[str]:
        # None becomes a null QString, which tells Qt that this translator has no
        # translation. An empty string would be used as the translation and blank
        # out texts in the whole QGIS UI.
        if context != TRANSLATION_CONTEXT:
            return None
        return self._messages.get(source_text)

    def isEmpty(self) -> bool:
        return not self._messages


def create_translator(locale: str, parent=None) -> Optional[DictTranslator]:
    """
    Create a translator for the given locale, or None if there is no translation.

    :param locale: Locale code, e.g. 'sv' or 'sv_SE'
    :param parent: Qt parent object
    """
    messages = TRANSLATIONS.get((locale or "")[0:2])
    if not messages:
        return None
    return DictTranslator(messages, parent)
