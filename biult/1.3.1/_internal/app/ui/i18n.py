"""Wspólne tłumaczenia Qt niezależne od języka systemu i instalacji PySide.

Nie tłumaczymy nazw wpisanych przez użytkownika ani sygnałów typu GND/SPI.
Translator obejmuje standardowe przyciski, menu tekstowe i dialogi plików.
Jest utrzymywany przez QApplication, żeby Python nie usunął go po zmianie języka.
"""
from PySide6.QtCore import QTranslator, Qt
from PySide6.QtWidgets import QApplication

QT_PL = {
    "Yes": "Tak", "&Yes": "&Tak", "No": "Nie", "&No": "&Nie",
    "Yes to All": "Tak dla wszystkich", "&Yes to All": "Tak dla &wszystkich",
    "No to All": "Nie dla wszystkich", "N&o to All": "Nie dla w&szystkich",
    "OK": "OK", "Cancel": "Anuluj", "&Cancel": "&Anuluj", "Close": "Zamknij", "&Close": "&Zamknij",
    "Save": "Zapisz", "&Save": "&Zapisz", "Save All": "Zapisz wszystko",
    "Discard": "Odrzuć", "&Discard": "&Odrzuć", "Don't Save": "Nie zapisuj",
    "Apply": "Zastosuj", "Reset": "Przywróć", "Restore Defaults": "Przywróć domyślne",
    "Help": "Pomoc", "Open": "Otwórz", "&Open": "&Otwórz", "Retry": "Ponów", "Abort": "Przerwij", "Ignore": "Ignoruj",
    "Show Details...": "Pokaż szczegóły…", "Hide Details...": "Ukryj szczegóły…",
    "Show Details…": "Pokaż szczegóły…", "Hide Details…": "Ukryj szczegóły…",
    "Select All": "Zaznacz wszystko", "Select &All": "Zaznacz &wszystko",
    "Undo": "Cofnij", "&Undo": "&Cofnij", "Redo": "Ponów", "&Redo": "&Ponów",
    "Cut": "Wytnij", "Cu&t": "Wy&tnij", "Copy": "Kopiuj", "&Copy": "&Kopiuj",
    "Paste": "Wklej", "&Paste": "&Wklej", "Delete": "Usuń", "&Delete": "&Usuń",
    "File name:": "Nazwa pliku:", "File &name:": "&Nazwa pliku:", "Files of type:": "Typ plików:",
    "Look in:": "Szukaj w:", "Save in:": "Zapisz w:", "Directory:": "Folder:", "Choose": "Wybierz",
    "Name": "Nazwa", "Size": "Rozmiar", "Type": "Typ", "Date Modified": "Data modyfikacji",
    "File": "Plik", "Folder": "Folder", "File Folder": "Folder plików", "Computer": "Komputer",
    "New Folder": "Nowy folder", "Create New Folder": "Utwórz nowy folder", "New &Folder": "Nowy &folder",
    "Back": "Wstecz", "Forward": "Dalej", "Parent Directory": "Folder nadrzędny",
    "List View": "Widok listy", "Detail View": "Widok szczegółów", "List": "Lista", "Details": "Szczegóły",
    "Rename": "Zmień nazwę", "&Rename": "Zmień &nazwę", "Show hidden files": "Pokaż ukryte pliki",
    "All Files (*)": "Wszystkie pliki (*)", "All files (*)": "Wszystkie pliki (*)",
    "%1 already exists.\nDo you want to replace it?": "%1 już istnieje.\nCzy chcesz go zastąpić?",
    "Confirm Save As": "Potwierdź zapis jako", "File not found.\nPlease verify the correct file name was given.": "Nie znaleziono pliku.\nSprawdź podaną nazwę pliku.",
}


class PolishQtTranslator(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        if context.startswith("Q"):
            return QT_PL.get(sourceText, sourceText)
        return sourceText


def install_ui_language(language):
    app = QApplication.instance()
    if app is None:
        return
    # Natywne okna systemowe ignorują język aplikacji. Qt używa tego samego
    # stylu PL/EN dla formularzy plików i pozostałych okien ElectroSchem.
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    previous = getattr(app, "_electroschem_translator", None)
    if previous:
        app.removeTranslator(previous)
        previous.deleteLater()
    app._electroschem_translator = None
    if language == "pl":
        translator = PolishQtTranslator(app)
        app.installTranslator(translator)
        app._electroschem_translator = translator
