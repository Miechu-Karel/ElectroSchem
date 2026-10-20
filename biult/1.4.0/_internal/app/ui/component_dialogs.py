"""Małe, niezależne dialogi dokumentu i własnych symboli.

Definicja customowego elementu jest zwykłymi danymi. Opis zachowania nigdy nie
jest uruchamiany jako Python — będzie materiałem dla przyszłego symulatora.
"""

from __future__ import annotations

from uuid import uuid4
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout,
)


class ProjectDialog(QDialog):
    """Rozmiar pierwszego arkusza jest wybierany przed utworzeniem projektu."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        pl = settings.language == "pl"
        self.setWindowTitle("Nowy projekt" if pl else "New project")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit("Nowy projekt" if pl else "New project")
        self.paper = QComboBox()
        self.paper.addItems([f"A{i}" for i in range(6)])
        self.paper.setCurrentText(settings.paper_size)
        self.orientation = QComboBox()
        self.orientation.addItem("Pozioma" if pl else "Landscape", "landscape")
        self.orientation.addItem("Pionowa" if pl else "Portrait", "portrait")
        self.orientation.setCurrentIndex(max(0, self.orientation.findData(settings.orientation)))
        form.addRow("Nazwa:" if pl else "Name:", self.name)
        form.addRow("Format arkusza:" if pl else "Sheet size:", self.paper)
        form.addRow("Orientacja:" if pl else "Orientation:", self.orientation)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class CustomComponentDialog(QDialog):
    """Użytkownik opisuje piny, a program rozmieszcza je na bokach symbolu.

Odstęp pinów i rozmiary są wielokrotnością kratki 20 jednostek sceny. Zwiększamy
zbyt małą obudowę automatycznie, zamiast układać podpisy jeden na drugim.
"""

    def __init__(self, language="en", parent=None, definition=None):
        super().__init__(parent)
        self.pl = language == "pl"
        self.definition = None
        self.original = deepcopy(definition)
        self.setWindowTitle(self.tr_text("Create custom component", "Utwórz własny element"))
        self.resize(620, 640)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        # Jedna nazwa jest źródłem prawdy. Interfejs angielski może używać
        # nazwy użytkownika bez wymuszania drugiego, sztucznego tłumaczenia.
        # QTextEdit pozwala również na wielolinijkową nazwę elementu.
        self.name = QTextEdit()
        self.name.setMaximumHeight(55)
        # Kompatybilność z wtyczkami/testami starszej wersji: pole istnieje
        # jako nieużywany alias, lecz nie jest prezentowane użytkownikowi.
        self.english_name = QLineEdit()
        self.english_name.setVisible(False)
        self.width = QSpinBox()
        self.width.setRange(4, 100)
        self.width.setValue(8)
        self.height = QSpinBox()
        self.height.setRange(4, 100)
        self.height.setValue(6)
        form.addRow(self.tr_text("Name:", "Nazwa:"), self.name)
        form.addRow(self.tr_text("Width (grid squares):", "Szerokość (kratki):"), self.width)
        form.addRow(self.tr_text("Height (grid squares):", "Wysokość (kratki):"), self.height)
        layout.addLayout(form)
        layout.addWidget(QLabel(self.tr_text("Pins — order is retained in the project:", "Piny — kolejność jest zachowywana w projekcie:")))
        self.pins = QTableWidget(0, 3)
        self.pins.setHorizontalHeaderLabels([self.tr_text("Number", "Numer"), self.tr_text("Name", "Nazwa"), self.tr_text("Side", "Strona")])
        self.pins.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.pins)
        pin_buttons = QHBoxLayout()
        add = QPushButton(self.tr_text("Add pin", "Dodaj pin"))
        remove = QPushButton(self.tr_text("Remove selected pin", "Usuń wybrany pin"))
        add.clicked.connect(lambda: self.add_pin())
        remove.clicked.connect(lambda: self.pins.removeRow(self.pins.currentRow()) if self.pins.currentRow() >= 0 else None)
        pin_buttons.addWidget(add)
        pin_buttons.addWidget(remove)
        layout.addLayout(pin_buttons)
        self.description = QTextEdit()
        self.description.setMaximumHeight(75)
        self.description.setPlaceholderText(self.tr_text("Description / datasheet notes", "Opis / uwagi z dokumentacji"))
        self.behavior = QTextEdit()
        self.behavior.setMaximumHeight(75)
        self.behavior.setPlaceholderText(self.tr_text("Behavior description for future simulation (not executable code)", "Opis działania dla przyszłej symulacji (nie wykonywalny kod)"))
        layout.addWidget(self.description)
        layout.addWidget(self.behavior)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if definition:
            self.setWindowTitle(self.tr_text("Edit custom component", "Edytuj własny element"))
            self.name.setPlainText(definition["name"])
            self.width.setMinimum(2)
            self.height.setMinimum(2)
            self.width.setValue(int(definition["width"] / 20))
            self.height.setValue(int(definition["height"] / 20))
            self.description.setPlainText(definition.get("description", ""))
            self.behavior.setPlainText(definition.get("behavior", ""))
            for pin in definition["pins"]:
                side = self.pin_side(pin, definition)
                self.add_pin(pin["name"], side)
                self.pins.item(self.pins.rowCount()-1, 0).setText(pin["number"])
            layout.addWidget(QLabel(self.tr_text(
                "Changes apply to all instances. Removed or renumbered pins disconnect their wires.",
                "Zmiany dotyczą wszystkich kopii. Usunięte lub przenumerowane piny odłączą przewody.")))
        else:
            self.add_pin("VCC", "left")
            self.add_pin("GND", "left")
            self.add_pin("OUT", "right")

    @staticmethod
    def pin_side(pin, definition):
        if pin["x"] == -definition["width"]/2:
            return "left"
        if pin["x"] == definition["width"]/2:
            return "right"
        return "top" if pin["y"] == -definition["height"]/2 else "bottom"

    def tr_text(self, en, pl):
        return pl if self.pl else en

    def add_pin(self, name=None, side="left"):
        row = self.pins.rowCount()
        self.pins.insertRow(row)
        self.pins.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.pins.setItem(row, 1, QTableWidgetItem(name or f"PIN{row + 1}"))
        selector = QComboBox()
        for en, pl, key in [("Left", "Lewa", "left"), ("Right", "Prawa", "right"), ("Top", "Góra", "top"), ("Bottom", "Dół", "bottom")]:
            selector.addItem(self.tr_text(en, pl), key)
        selector.setCurrentIndex(max(0, selector.findData(side)))
        self.pins.setCellWidget(row, 2, selector)

    def accept(self):
        name = self.name.toPlainText().strip()
        name_en = name
        if not name:
            QMessageBox.warning(self, self.windowTitle(), self.tr_text("Enter a component name.", "Podaj nazwę elementu."))
            return
        raw = []
        numbers = set()
        for row in range(self.pins.rowCount()):
            number_item, name_item = self.pins.item(row, 0), self.pins.item(row, 1)
            number = number_item.text().strip() if number_item else ""
            pin_name = name_item.text().strip() if name_item else ""
            if not number or not pin_name or number in numbers:
                QMessageBox.warning(self, self.windowTitle(), self.tr_text("Every pin needs a unique number and a name.", "Każdy pin wymaga unikatowego numeru i nazwy."))
                return
            numbers.add(number)
            raw.append({"number": number, "name": pin_name, "side": self.pins.cellWidget(row, 2).currentData()})
        counts = {side: sum(pin["side"] == side for pin in raw) for side in ("left", "right", "top", "bottom")}
        # Parzysta liczba kratek utrzymuje zarówno obrys, jak i końcówki na siatce.
        cols = max(self.width.value(), max(counts["top"], counts["bottom"]) + 2)
        rows = max(self.height.value(), max(counts["left"], counts["right"]) + 2)
        width, height = (cols + cols % 2) * 20, (rows + rows % 2) * 20
        cursors = dict.fromkeys(counts, 0)
        for pin in raw:
            side = pin["side"]
            offset = (cursors[side] - counts[side] // 2) * 20
            cursors[side] += 1
            if side in ("left", "right"):
                pin["x"] = (-1 if side == "left" else 1) * width / 2
                pin["y"] = offset
            else:
                pin["x"] = offset
                pin["y"] = (-1 if side == "top" else 1) * height / 2
        prefix = "Cus" + "".join(word[:3].title() for word in name_en.split())
        self.definition = {
            "id": f"custom-{uuid4()}", "name": name, "name_en": name_en,
            "category": "Własne", "reference_prefix": prefix, "pins": raw,
            "width": width, "height": height, "symbol": "module",
            "description": self.description.toPlainText().strip(),
            "behavior": self.behavior.toPlainText().strip(),
        }
        if self.original:
            # To nadal ta sama definicja: ID, oznaczenia i metadane importu
            # nie mogą zmieniać się podczas edycji nazwy lub opisu.
            original = self.original
            same_geometry = (self.width.value()*20 == original["width"] and
                             self.height.value()*20 == original["height"] and
                             len(raw) == len(original["pins"]) and
                             all(new["number"] == old["number"] and
                                 new["side"] == self.pin_side(old, original)
                                 for new, old in zip(raw, original["pins"])))
            if same_geometry:
                self.definition["width"], self.definition["height"] = original["width"], original["height"]
                for new, old in zip(raw, original["pins"]):
                    new["x"], new["y"] = old["x"], old["y"]
            self.definition = {**deepcopy(original), **self.definition,
                               "id": original["id"],
                               "reference_prefix": original.get("reference_prefix", original.get("prefix", "Cus"))}
        # Ta sama walidacja obowiązuje ręczny edytor, AI i import ELS. Nie
        # wypuszczamy z dialogu np. symbolu bez pinów lub z powielonym numerem.
        from app.libraries.built_in import validate_custom_definition
        try:
            self.definition = validate_custom_definition(self.definition)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            self.definition = None
            return
        super().accept()
