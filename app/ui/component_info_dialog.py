"""Małe, przewijalne okno informacji H; nigdy nie zmienia projektu."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout
from app.libraries.built_in import item_name
from app.libraries.catalog_text import catalog_text
from app.libraries.component_info import explanation


class ComponentInfoDialog(QDialog):
    def __init__(self, component, definition, language="en", custom=None, parent=None):
        super().__init__(parent)
        pl = language == "pl"
        self.setWindowTitle(("Informacje o elemencie" if pl else "Component information") + " — " + item_name(definition, language))
        self.resize(520, 350)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        # PlainText: customowy opis pozostaje danymi, nie HTML ani kodem.
        browser.setPlainText(item_name(definition, language) + "\n" + component.reference + "\n\n" +
            explanation(definition, language, custom) + "\n\n" +
            ("Wariant: " if pl else "Variant: ") + catalog_text(definition.variant, language) + "\n" +
            ("Zakres pinów: " if pl else "Pin scope: ") + catalog_text(definition.pin_scope, language) + "\n\n" +
            ("Dokumentacja: " if pl else "Documentation: ") + (definition.source_url or "—"))
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Zamknij" if pl else "Close")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
