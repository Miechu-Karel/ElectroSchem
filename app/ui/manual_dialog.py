"""Structured, bilingual offline user manual."""
from html import escape
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout


class ManualDialog(QDialog):
    def __init__(self, language="en", parent=None):
        super().__init__(parent)
        pl=language=="pl"
        def t(en,polish): return polish if pl else en
        self.setWindowTitle(t("Usage Instructions","Instrukcja Obsługi")); self.resize(760,640)
        layout=QVBoxLayout(self); self.browser=QTextBrowser()
        shortcuts=[
            ("S","Select","Zaznaczanie"),("D","Draw wire","Rysuj połączenia"),
            ("X","Delete tool","Narzędzie usuwania"),
            ("Del","Delete selection","Usuń zaznaczenie"),("R","Rotate component","Obróć element"),
            ("Ctrl+Z","Undo","Cofnij"),("Ctrl+Y / Ctrl+Shift+Z","Redo","Ponów"),
            ("Ctrl+S","Save","Zapisz"),("Ctrl+Shift+S","Save as","Zapisz jako"),
            ("Ctrl+N","New project","Nowy projekt"),("Ctrl+O","Open project","Otwórz projekt"),
            ("Ctrl+D","Duplicate selection","Duplikuj zaznaczenie"),
            ("Ctrl+X","Cut selection","Wytnij zaznaczenie"),("Ctrl+C","Copy selection","Kopiuj zaznaczenie"),
            ("Ctrl+V","Paste at cursor","Wklej przy kursorze"),
            ("H","Selected object information","Informacje o zaznaczonym obiekcie"),
            ("F5","Simulation sandbox","Sandbox symulacji")]
        html="<h1>"+escape(self.windowTitle())+"</h1><h2>"+t("Keyboard shortcuts","Skróty klawiszowe")+"</h2>"
        html+="<table width='100%' cellspacing='0' cellpadding='6' border='1'><tr><th>"+t("Shortcut","Skrót")+"</th><th>"+t("Action","Działanie")+"</th></tr>"
        html+="".join("<tr><td><b>"+escape(key)+"</b></td><td>"+escape(t(en,polish))+"</td></tr>" for key,en,polish in shortcuts)+"</table>"
        sections=[
            ("Adding components","Dodawanie elementów",[
                ("Press Ctrl+A, release, then A to open all categories.","Naciśnij Ctrl+A, puść klawisze, a potem A, aby otworzyć wszystkie kategorie."),
                ("After Ctrl+A: E = electronics, S = sensors, I = ICs, C = custom components, M = microcontrollers.","Po Ctrl+A: E = elementy elektroniczne, S = czujniki, I = układy scalone, C = własne elementy, M = mikrokontrolery."),
                ("Shift+A, then S adds a sheet.","Shift+A, a potem S dodaje arkusz.")]),
            ("Mouse and selection","Mysz i zaznaczanie",[
                ("Left-click selects an object. Double-click opens its properties.","LPM wybiera obiekt. Dwuklik otwiera właściwości."),
                ("Hold the middle mouse button to pan the view.","Przytrzymaj kółko myszy, aby przesuwać widok."),
                ("Drag with the right button to select a rectangle. Right-click cancels a wire in progress.","Przeciągnij PPM, aby zaznaczyć prostokątem. PPM anuluje rysowane połączenie."),
                ("Drag a selected object to move the whole group, including free wire nodes. Duplicates are offset by one grid square.","Przeciągnij zaznaczony obiekt, aby przesunąć całą grupę, także wolne węzły przewodów. Duplikat jest przesunięty o kratkę.")]),
            ("Sheets and project information","Arkusze i dane projektu",[
                ("Double-click the title, author or sheet name in the drawing table to edit directly. Enter confirms; Shift+Enter adds a line.","Dwuklik tytułu, autora lub nazwy arkusza w tabliczce uruchamia edycję. Enter zatwierdza, Shift+Enter dodaje linię."),
                ("Double-click a sheet tab to rename or delete it. Undo restores deleted sheets.","Dwuklik zakładki arkusza pozwala zmienić nazwę lub usunąć arkusz. Cofnij przywraca usunięty arkusz."),
                ("Components and wires stay inside the drawing area; comments may also be placed in margins.","Elementy i przewody muszą być w obszarze rysowania. Komentarze można umieszczać także na marginesach."),
                ("Save as and export suggest the current project title as the filename.","Zapisz jako i eksport proponują nazwę pliku zgodną z tytułem projektu.")]),
            ("Simulation","Symulacja",[
                ("Settings offers light/dark themes and Gentle, Medium or Strong fault effects. Strong is the default. Gentle or Medium is recommended for people with photosensitive epilepsy. Esc cancels effects and sound.","Ustawienia pozwalają wybrać motyw jasny/ciemny oraz efekty awarii Delikatny, Średni lub Mocny. Domyślny jest Mocny. Dla osób z epilepsją światłoczułą zalecany jest tryb Delikatny lub Średni. Esc przerywa efekty i dźwięk."),
                ("The window mode applies to the editor and simulator. Maximized is the default. Exported drawings always use a light background.","Tryb okna dotyczy edytora i symulatora. Domyślnie okna są zmaksymalizowane. Eksportowane rysunki zawsze mają jasne tło."),
                ("Set electrical values in properties before starting. Remember values saves defaults for new components across sessions.","Przed startem ustaw wartości we właściwościach. Zapamiętaj wartości zapisuje ustawienia nowych elementów pomiędzy sesjami."),
                ("F5 opens a separate sandbox. Reload from editor imports schematic changes; Reset restarts the sandbox copy.","F5 otwiera osobny sandbox. Pobierz z edytora wczytuje zmiany schematu, a Resetuj rozpoczyna symulację kopii od nowa."),
                ("100% time scale targets real time; 50% makes one simulated second last two real seconds if the computer keeps up.","Skala 100% oznacza docelowy czas rzeczywisty. Przy 50% sekunda symulacji trwa dwie sekundy rzeczywiste, jeśli komputer nadąża."),
                ("Click Input or switches to change state. Run after a fault resumes healthy circuits.","Kliknij Input lub przełącznik, aby zmienić stan. Uruchom po awarii wznawia sprawne obwody."),
                ("Fault effects are gentle and silent by default. Intense flash and sound are opt-in; avoid them with photosensitivity or hearing sensitivity.","Efekty awarii są domyślnie łagodne i bezgłośne. Intensywny błysk i huk są opcjonalne. Nie włączaj ich przy nadwrażliwości na światło lub dźwięk.")]),
            ("Board code","Kod mikrokontrolerów",[
                ("Properties > Create and Assign Code creates an Arduino Uno/Nano .ino sketch or Python board code in the default code folder selected in Settings. Edit Code opens the assigned file. Assign Existing Code links a file without copying it; Detach Code removes the link, not the file. Reload from editor compiles .ino locally and imports code changes.","Właściwości > Utwórz i Przypisz Kod tworzy szkic .ino Arduino Uno/Nano lub kod Pythona płytki w domyślnym folderze kodów wybranym w ustawieniach. Edytuj Kod otwiera przypisany plik. Przypisz Istniejący Kod wskazuje plik bez kopiowania; Odłącz Kod usuwa powiązanie, nie plik. Pobierz z edytora kompiluje .ino lokalnie i wczytuje zmiany kodu."),
                ("Python supports GPIO, RPLCD and smbus LCD writes, functions and local helper modules, not an entire OS or every Python library. Firmware also supports HEX for Uno/Nano and UF2 for Pico.","Python obsługuje GPIO, zapis do LCD przez RPLCD i smbus, funkcje i lokalne moduły pomocnicze, nie cały system ani każdą bibliotekę Pythona. Firmware przyjmuje także HEX dla Uno/Nano i UF2 dla Pico."),
                ("Device camera preview starts only after session consent. Stop revokes consent and releases the camera; no microphone, recording or transfer is enabled.","Podgląd kamery urządzenia uruchamia się tylko po zgodzie w sesji. Zatrzymaj cofa zgodę i zwalnia kamerę; mikrofon, nagrywanie i wysyłanie obrazu nie są włączane."),
                ("Restart loads the assigned program from the beginning. Start/Pause controls execution. Full limitations: docs/SIMULATION.md.","Restart wczytuje przypisany program od początku. Start i Pauza sterują wykonaniem. Pełne ograniczenia: docs/SIMULATION.md.")])]
        for en,polish,items in sections:
            html+="<h2>"+t(en,polish)+"</h2><ul>"+"".join("<li>"+escape(t(a,b))+"</li>" for a,b in items)+"</ul>"
        self.browser.setHtml(html); layout.addWidget(self.browser)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(t("Close","Zamknij"))
        buttons.rejected.connect(self.reject); layout.addWidget(buttons)
