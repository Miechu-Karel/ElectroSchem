"""Właściwości na żądanie: nie zajmują stale miejsca obok arkusza."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QVBoxLayout, QScrollArea, QWidget, QSizePolicy, QFrame
from PySide6.QtGui import QTextOption
from app.core.units import parse_value
from app.core.led_colors import LED_COLORS, color_key
from app.libraries.built_in import item_name
from app.libraries.catalog_text import catalog_text
from app.libraries.simulation_catalog import behavior_for
from app.ui.wrapping_label import WrappingLabel


class ComponentPropertiesDialog(QDialog):
    def __init__(self, component, definition, language="en", parent=None):
        super().__init__(parent)
        self.component, self.definition = component, definition
        self.pl = language == "pl"
        self.values = None
        self.setWindowTitle(self.t("Component properties", "Właściwości elementu"))
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        # Dodatkowe parametry nie mogą wypchnąć przycisku Zapisz poza ekran.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.form_scroll = scroll
        body = QWidget()
        body_layout = QVBoxLayout(body)
        fields = QWidget()
        fields.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form = QFormLayout(fields)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setVerticalSpacing(8)
        body_layout.addWidget(fields, 0, Qt.AlignmentFlag.AlignTop)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.resize(600, 720)
        reference = QLabel(component.reference)
        reference.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("ID:", reference)
        if definition:
            title = WrappingLabel(item_name(definition, language))
            title.setWordWrap(True)
            form.addRow(self.t("Type:", "Typ:"), title)
        self.name = QPlainTextEdit(component.display_name)
        self.name.setFixedHeight(56)
        self.name.setPlaceholderText(item_name(definition, language) if definition else "")
        self.show_name = QCheckBox(self.t("Show name", "Wyświetlaj nazwę"))
        self.show_name.setChecked(component.show_name)
        self.save_default_name = QCheckBox(self.t("Remember this name for new components", "Zapamiętaj nazwę dla nowych elementów"))
        from app.core.component_defaults import nominal_value
        self.value = QLineEdit(component.value or nominal_value(definition)[0])
        self.value.setMaxLength(100)
        self.value.setPlaceholderText("300 / 1k / 4.7µF")
        self.unit = QLineEdit(component.unit or (definition.default_unit if definition else ""))
        self.unit.setMaxLength(20)
        self.show_value = QCheckBox(self.t("Show value", "Wyświetlaj wartość"))
        self.show_value.setChecked(component.show_value)
        self._has_primary_value = bool(definition and definition.default_unit)
        self._extra_key = "voltage" if definition and definition.symbol in {"capacitor", "polar_capacitor"} else ("color" if definition and definition.symbol == "led" else "")
        self.extra_value = QLineEdit(component.properties.get(self._extra_key, "")) if self._extra_key else None
        self._original_color = component.properties.get("color", "")
        if self._extra_key == "color":
            self.extra_value.deleteLater()
            self.extra_value = QComboBox()
            self.extra_value.setPlaceholderText(self.t("Choose colour", "Wybierz kolor"))
            for key, en, pl in LED_COLORS:
                self.extra_value.addItem(self.t(en, pl), key)
            self.extra_value.setCurrentIndex(self.extra_value.findData(color_key(self._original_color)))
            if self._original_color and not color_key(self._original_color):
                # Nie kasujemy nieznanych historycznych wpisów przy samej
                # edycji nazwy. Nowy kolor można wybrać tylko z listy.
                self.extra_value.setPlaceholderText(str(self._original_color))
        self.extra_unit = QLineEdit("V") if self._extra_key == "voltage" else None
        if self.extra_unit is not None:
            # Starsze ELS zapisują napięcie jako „25 V”. Zachowujemy zgodność
            # pliku, ale w formularzu liczba i jednostka są zawsze osobne.
            self.extra_unit.setMaxLength(20)
            self.extra_value.setMaxLength(100)
            self.normalize_extra_value()
            self.extra_value.editingFinished.connect(self.normalize_extra_value)
            self.extra_unit.editingFinished.connect(self.normalize_extra_value)
        self.extra_show = QCheckBox(self.t("Show additional value", "Wyświetlaj dodatkową wartość")) if self._extra_key else None
        if self.extra_show:
            self.extra_show.setChecked(bool(component.properties.get("show_" + self._extra_key, True)))
            if self._extra_key == "voltage":
                self.extra_value.setPlaceholderText("25")
        self.value.editingFinished.connect(self.normalize_value)
        self.unit.editingFinished.connect(self.normalize_value)
        self.description = QLineEdit(component.properties.get("description", ""))
        form.addRow(self.t("Display name:", "Wyświetlana nazwa:"), self.name)
        form.addRow("", self.show_name)
        form.addRow("", self.save_default_name)
        # Element bez zdefiniowanej wartości (np. moduł, złącze, bramka)
        # nie dostaje pustych, mylących pól „Value/Unit”.
        if self._has_primary_value:
            labels = {"Ω": ("Resistance:", "Rezystancja:"), "F": ("Capacitance:", "Pojemność:"),
                      "H": ("Inductance:", "Indukcyjność:"), "V": ("Voltage:", "Napięcie:"),
                      "Hz": ("Frequency:", "Częstotliwość:")}
            form.addRow(self.t(*labels.get(definition.default_unit, ("Value:", "Wartość:"))), self.value)
            form.addRow(self.t("Unit:", "Jednostka:"), self.unit)
            form.addRow("", self.show_value)
        if self.extra_value is not None:
            label = self.t("Voltage:", "Napięcie:") if self._extra_key == "voltage" else self.t("Colour:", "Kolor:")
            form.addRow(label, self.extra_value)
            if self.extra_unit is not None:
                form.addRow(self.t("Unit:", "Jednostka:"), self.extra_unit)
            form.addRow("", self.extra_show)
        self.simulation_fields = {}
        self.save_default_values = QCheckBox(self.t("Remember these values for new components", "Zapamiętaj wartości dla nowych elementów"))
        from app.libraries.emulator_catalog import profile_for
        if profile_for(definition):
            from PySide6.QtWidgets import QPushButton
            from PySide6.QtGui import QIcon
            from pathlib import Path
            self.edit_code_button = QPushButton()
            self.edit_code_button.setIcon(QIcon(str(Path(__file__).resolve().parents[2]/"Ikonki"/"Edytuj Kod.png")))
            self.edit_code_button.clicked.connect(lambda: self._edit_board_code(parent))
            form.addRow(self.edit_code_button)
            self.assign_code_button=QPushButton(self.t("Assign Existing Code","Przypisz Istniejący Kod"))
            self.assign_code_button.setEnabled(hasattr(parent,"assign_component_code"))
            self.assign_code_button.clicked.connect(lambda: self._assign_board_code(parent))
            form.addRow(self.assign_code_button)
            # A Windows path is one long word to QLabel. Use an anywhere-wrapped,
            # selectable text view so it cannot force the whole form offscreen.
            self.code_path_label=QPlainTextEdit()
            self.code_path_label.setReadOnly(True)
            self.code_path_label.setFrameShape(QFrame.Shape.NoFrame)
            self.code_path_label.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
            self.code_path_label.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.code_path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            self.code_path_label.setFixedHeight(self.fontMetrics().lineSpacing()*3+8)
            form.addRow(self.code_path_label)
            self._refresh_code_label()
            if hasattr(parent,"edit_component_code_folder"):
                self.code_folder_button=QPushButton(self.t("Create / open code folder…","Utwórz / otwórz folder kodu…"))
                self.code_folder_button.clicked.connect(lambda: self._edit_board_code(parent,folder=True))
                form.addRow(self.code_folder_button)
        model = behavior_for(definition)
        if model:
            for parameter in model.parameters:
                raw = str(component.properties.get(parameter.key, parameter.default))
                if parameter.choices:
                    field = QComboBox()
                    for key, en, pl in parameter.choices:
                        field.addItem(self.t(en, pl), key)
                    field.setCurrentIndex(max(0, field.findData(raw)))
                else:
                    field = QLineEdit(raw)
                    field.setMaxLength(100)
                    field.setPlaceholderText(parameter.unit)
                self.simulation_fields[parameter.key] = field
                form.addRow(self.t(parameter.en, parameter.pl) + " (sim):", field)
            if model.note_en:
                note = WrappingLabel(self.t(model.note_en, model.note_pl))
                note.setWordWrap(True)
                form.addRow(note)
        if self._has_primary_value or self._extra_key or (model and model.parameters):
            form.addRow("", self.save_default_values)
        form.addRow(self.t("Description:", "Opis:"), self.description)
        if definition:
            details = WrappingLabel(catalog_text(definition.variant, language) + "\n" + catalog_text(definition.pin_scope, language))
            details.setWordWrap(True)
            form.addRow(self.t("Variant:", "Wariant:"), details)
            if not definition.verified:
                warning = WrappingLabel(self.t("Verify the pinout against your exact board or package before use.",
                                       "Sprawdź piny z dokumentacją swojej płytki lub obudowy przed użyciem."))
                warning.setWordWrap(True)
                layout.addWidget(warning)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(self.t("Save", "Zapisz"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.t("Cancel", "Anuluj"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        # Keep short forms compact. The scroll area's stretch absorbs spare
        # height instead of stretching every QLabel row into a giant gap.
        self.resize(640, min(720, max(360, fields.sizeHint().height()+120)))

    def t(self, en, pl):
        return pl if self.pl else en

    def normalize_value(self):
        """Przedrostek wpisany przy liczbie przenosi się do osobnej jednostki."""
        try:
            value, unit = parse_value(self.value.text(), self.unit.text())
        except ValueError:
            return False
        self.value.setText(value)
        self.unit.setText(unit)
        return True

    def normalize_extra_value(self):
        try:
            number, unit = parse_value(self.extra_value.text(), self.extra_unit.text())
            if not unit.endswith("V"):
                raise ValueError("Expected voltage")
        except ValueError:
            return False
        self.extra_value.setText(number)
        self.extra_unit.setText(unit)
        return True

    def _edit_board_code(self,parent,folder=False):
        if folder: parent.edit_component_code_folder(self.component)
        else: parent.edit_component_code(self.component)
        self._sync_code_fields()

    def _assign_board_code(self,parent):
        if self.component.properties.get("sim_source", "").strip():
            parent.detach_component_code(self.component)
        else:
            parent.assign_component_code(self.component)
        self._sync_code_fields()

    def _refresh_code_label(self):
        source=self.component.properties.get("sim_source","").strip()
        self.edit_code_button.setText(self.t("Edit Code","Edytuj Kod") if source else
                                      self.t("Create and Assign Code","Utwórz i Przypisz Kod"))
        self.edit_code_button.setToolTip(source)
        from pathlib import Path
        from PySide6.QtGui import QIcon
        self.assign_code_button.setText(self.t("Detach Code","Odłącz Kod") if source else
                                       self.t("Assign Existing Code","Przypisz Istniejący Kod"))
        self.assign_code_button.setIcon(QIcon(str(Path(__file__).resolve().parents[2]/"Ikonki"/"Usuń v2.png")) if source else QIcon())
        parent=self.parent()
        self.assign_code_button.setEnabled(hasattr(parent,"detach_component_code" if source else "assign_component_code"))
        self.code_path_label.setPlainText(self.t("Assigned code: ","Przypisany kod: ")+source if source else "")
        self.code_path_label.setToolTip(source)
        self.code_path_label.setVisible(bool(source))

    def _sync_code_fields(self):
        self._refresh_code_label()
        # Saving this already-open dialog must not restore the old source link.
        for key in ("sim_source","sim_mode"):
            field=self.simulation_fields.get(key)
            value=self.component.properties.get(key)
            if field is not None and value is not None:
                if isinstance(field,QComboBox): field.setCurrentIndex(max(0,field.findData(value)))
                else: field.setText(value)

    def accept(self):
        if self.extra_unit is not None and not self.normalize_extra_value():
            QMessageBox.warning(self, self.windowTitle(), self.t("Enter a voltage, e.g. 25 V.", "Podaj napięcie, np. 25 V."))
            return
        if self._has_primary_value and not self.normalize_value():
            QMessageBox.warning(self, self.windowTitle(), self.t("Use a numeric value, e.g. 300, 1k, 4.7µF.", "Podaj wartość liczbową, np. 300, 1k, 4.7µF."))
            return
        extra = ((self.extra_value.currentData() or self._original_color) if self._extra_key == "color"
                 else self.extra_value.text().strip() if self.extra_value is not None else "")
        if extra and self.extra_unit is not None:
            extra += " " + self.extra_unit.text()
        self.values = dict(display_name=self.name.toPlainText().strip()[:2000], show_name=self.show_name.isChecked(),
                           value=self.value.text() if self._has_primary_value else "",
                           unit=self.unit.text() if self._has_primary_value else "",
                           show_value=self.show_value.isChecked() if self._has_primary_value else False,
                           extra_key=self._extra_key,
                           extra_value=extra,
                           extra_show=self.extra_show.isChecked() if self.extra_show is not None else False)
        self.values["simulation_properties"] = {
            key: field.currentData() if isinstance(field, QComboBox) else field.text().strip()
            for key, field in self.simulation_fields.items()}
        super().accept()
