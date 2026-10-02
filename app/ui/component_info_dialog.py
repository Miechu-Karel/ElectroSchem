"""Małe, przewijalne okno informacji H; nigdy nie zmienia projektu."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout
from app.libraries.built_in import item_name
from app.libraries.catalog_text import catalog_text
from app.libraries.component_info import explanation
from app.libraries.pin_info import pin_explanation
from html import escape
from urllib.parse import urlsplit


class ComponentInfoDialog(QDialog):
    def __init__(self, component, definition, language="en", custom=None, parent=None):
        super().__init__(parent)
        pl = language == "pl"
        self.setWindowTitle(("Informacje o elemencie" if pl else "Component information") + ": " + item_name(definition, language))
        self.resize(700, 600)
        layout = QVBoxLayout(self)
        browser = self.browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        def text(value): return escape(str(value)).replace("\n","<br>")
        # Every catalogue/custom value is escaped. Only HTTP(S) links are active.
        html="<h2>"+text(item_name(definition,language))+"</h2><p>"+text(component.reference)+"</p>"
        html+="<h3>"+("Działanie" if pl else "Operation")+"</h3><p>"+text(explanation(definition,language,custom))+"</p>"
        html+="<p><b>"+("Wariant: " if pl else "Variant: ")+"</b>"+text(catalog_text(definition.variant,language))+"<br>"
        html+=("Zakres pinów: " if pl else "Pin scope: ")+text(catalog_text(definition.pin_scope,language))+"</p>"
        url=definition.source_url
        try: valid=urlsplit(url).scheme in {"http","https"} and bool(urlsplit(url).netloc)
        except ValueError: valid=False
        html+="<p><b>"+("Dokumentacja: " if pl else "Documentation: ")+"</b>"
        html+=("<a href='"+escape(url,quote=True)+"'>"+("Otwórz dokumentację" if pl else "Open documentation")+"</a>" if valid else text(url or ("Brak linku" if pl else "No link")))+"</p>"
        html+="<h3>"+("Wyprowadzenia" if pl else "Pin functions")+"</h3><table width='100%' border='1' cellspacing='0' cellpadding='5'>"
        html+="<tr><th>Pin</th><th>"+("Sygnał" if pl else "Signal")+"</th><th>"+("Funkcja" if pl else "Function")+"</th></tr>"
        for pin in definition.pins:
            role=("Opis pinu użytkownika; sprawdź opis własnego elementu." if pl else "User-defined pin; consult the custom component description.") if custom else pin_explanation(definition,pin,language)
            html+="<tr><td>"+text(pin.number)+"</td><td>"+text(pin.name)+"</td><td>"+text(role)+"</td></tr>"
        html+="</table><p>"+("Numery dotyczą wariantu z biblioteki. Sprawdź obudowę przed podłączeniem." if pl else "Numbers refer to the library variant. Verify your package before wiring.")+"</p>"
        from app.libraries.simulation_catalog import behavior_for
        model=behavior_for(definition) if not custom else None
        if model:
            html+="<h3>"+("Symulacja i ograniczenia" if pl else "Simulation and limitations")+"</h3><p>"+text(model.note_pl if pl else model.note_en)+"</p>"
            if model.parameters:
                html+="<ul>"
                for parameter in model.parameters:
                    html+="<li>"+text(parameter.pl if pl else parameter.en)+": "+text(component.properties.get(parameter.key,parameter.default))+"</li>"
                html+="</ul>"
        browser.setHtml(html)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Zamknij" if pl else "Close")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
