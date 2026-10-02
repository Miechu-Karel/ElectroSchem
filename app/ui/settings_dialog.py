"""Pierwsze uruchomienie i późniejsza konfiguracja używają tego samego formularza."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from app.core.settings import AppSettings, default_editor, detected_editors, documents_directory, file_dialog_directory
from app.ui.i18n import install_ui_language
from app.core.features import AI_AVAILABLE


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None, first_run: bool = False):
        super().__init__(parent)
        self._settings = replace(settings)
        self.first_run = first_run
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)
        self.intro = QLabel()
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("Polski", "pl")
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        self.standard = QComboBox()
        self.standard.addItems(["EN", "PN", "ISO", "IEEE/ANSI"])
        self.standard.setCurrentText(settings.standard)
        self.paper = QComboBox()
        self.paper.addItems([f"A{i}" for i in range(6)])
        self.paper.setCurrentText(settings.paper_size)
        self.orientation = QComboBox()
        self.orientation.addItem("Landscape", "landscape")
        self.orientation.addItem("Portrait", "portrait")
        self.orientation.setCurrentIndex(max(0, self.orientation.findData(settings.orientation)))
        self.grid = QCheckBox()
        self.grid.setChecked(settings.grid_visible)
        self.editor = QComboBox()
        self.editor.setMinimumContentsLength(27)
        for name, path in detected_editors():
            self.editor.addItem(name, path)
        if settings.editor_path and self.editor.findData(settings.editor_path) < 0:
            self.editor.addItem(settings.editor_path, settings.editor_path)
        self.editor.setCurrentIndex(max(0, self.editor.findData(settings.editor_path or default_editor())))
        self.editor_browse = QPushButton("…")
        self.editor_browse.setFixedWidth(35)
        self.editor_browse.clicked.connect(self._browse_editor)
        editor_row = QWidget()
        editor_layout = QHBoxLayout(editor_row)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.editor, 1)
        editor_layout.addWidget(self.editor_browse)
        self.key = QLineEdit(settings.api_key)
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setMaxLength(256)
        # Model jest szczegółem integracji, nie obowiązkiem użytkownika.
        self.model = QLabel()
        self.ai_consent = QCheckBox()
        self.ai_consent.setChecked(settings.ai_chat_consent)
        self.directory = QLineEdit(settings.default_directory or documents_directory())
        self.directory_button = QPushButton("…")
        self.directory_button.setFixedWidth(35)
        self.directory_button.clicked.connect(self._browse_directory)
        directory_row = QWidget()
        directory_layout = QHBoxLayout(directory_row)
        directory_layout.setContentsMargins(0, 0, 0, 0)
        directory_layout.addWidget(self.directory, 1)
        directory_layout.addWidget(self.directory_button)
        self._rows = []
        self.author = QLineEdit(settings.default_author)
        self.author.setMaxLength(250)
        from app.ui.effects import fault_effect
        self.fault_effect=QComboBox()
        for key in ("mini","medium","mega"): self.fault_effect.addItem(key,key)
        self.fault_effect.setCurrentIndex(self.fault_effect.findData(fault_effect(settings)))
        self.theme=QComboBox()
        for key in ("light","dark"): self.theme.addItem(key,key)
        self.theme.setCurrentIndex(max(0,self.theme.findData(settings.theme)))
        self.window_mode=QComboBox()
        for key in ("windowed","maximized","fullscreen"): self.window_mode.addItem(key,key)
        self.window_mode.setCurrentIndex(max(0,self.window_mode.findData(settings.window_mode)))
        for field in (self.language, self.standard, self.paper, self.orientation,
                      self.grid, editor_row, self.key, self.model, directory_row, self.ai_consent, self.author, self.fault_effect, self.window_mode,self.theme):
            label = QLabel()
            self._rows.append(label)
            self.form.addRow(label, field)
        self.norm_note = QLabel()
        self.norm_note.setWordWrap(True)
        layout.addWidget(self.norm_note)
        self.fault_note = QLabel()
        self.fault_note.setWordWrap(True)
        layout.addWidget(self.fault_note)
        self.key_note = QLabel()
        self.key_note.setWordWrap(True)
        self.key_note.setOpenExternalLinks(True)
        self.key_note.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.key_note)
        if not AI_AVAILABLE:
            # Ukryj całe wiersze (również etykiety), nie tylko same pola.
            for field in (self.key, self.model, self.ai_consent):
                self.form.setRowVisible(field, False)
                field.setEnabled(False)
            self.key_note.hide()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.language.currentIndexChanged.connect(self._translate)
        self._translate()

    def _t(self, en: str, pl: str) -> str:
        return pl if self.language.currentData() == "pl" else en

    def _translate(self):
        install_ui_language(self.language.currentData())
        self.setWindowTitle(self._t("Welcome to ElectroSchem" if self.first_run else "Settings",
                                   "Witaj w ElectroSchem" if self.first_run else "Ustawienia"))
        self.intro.setText(self._t("Choose your editor preferences. The application works offline.",
                                  "Wybierz ustawienia edytora. Aplikacja działa offline."))
        labels = [("Language", "Język"), ("Drawing profile", "Profil rysunkowy"),
                  ("Default sheet", "Domyślny arkusz"), ("Default orientation", "Domyślna Orientacja"),
                  ("Grid", "Siatka"), ("Code editor", "Edytor kodu"),
                  ("Gemini API key (optional)", "Klucz API Gemini (opcjonalny)"),
                  ("Gemini model", "Model Gemini"), ("Default folder", "Domyślny folder"), ("AI privacy", "Prywatność AI"),
                  ("Username", "Nazwa użytkownika"), ("Fault effects", "Efekty awarii"), ("Window mode", "Tryb okna"),("Theme","Motyw")]
        for label, texts in zip(self._rows, labels):
            label.setText(self._t(*texts))
        self.orientation.setItemText(0, self._t("Landscape", "Pozioma"))
        self.orientation.setItemText(1, self._t("Portrait", "Pionowa"))
        for i,pair in enumerate((("Windowed","W oknie"),("Maximized","Zmaksymalizowane"),("Fullscreen","Pełny ekran"))):
            self.window_mode.setItemText(i,self._t(*pair))
        self.grid.setText(self._t("Line grid (unchecked: subtle dots)", "Siatka liniowa (odznaczone: delikatne punkty)"))
        for i,pair in enumerate((("Gentle","Delikatny"),("Medium","Średni"),("Strong","Mocny"))): self.fault_effect.setItemText(i,self._t(*pair))
        for i,pair in enumerate((("Light","Jasny"),("Dark","Ciemny"))): self.theme.setItemText(i,self._t(*pair))
        self.fault_note.setText(self._t("Gentle or Medium is recommended for people with photosensitive epilepsy.", "Dla osób z epilepsją światłoczułą zalecany jest tryb Delikatny lub Średni."))
        self.key.setPlaceholderText(self._t("Leave empty to disable AI", "Pozostaw puste, aby wyłączyć AI"))
        self.model.setText(self._t("Automatic — detected from Gemini API", "Automatyczny — wykrywany przez API Gemini"))
        self.ai_consent.setText(self._t("Remember consent to send chat and schematic to Google", "Zapamiętana zgoda na wysyłanie czatu i schematu do Google"))
        self.ai_consent.setToolTip(self._t("Uncheck to ask for consent before the next chat request. PDF transfers are confirmed separately.", "Odznacz, aby zapytać o zgodę przed następną wiadomością. Wysyłanie PDF potwierdza się osobno."))
        self.norm_note.setText(self._t(
            "EN / PN / ISO use IEC-style resistors and rectangular logic gates. IEEE/ANSI uses zigzag resistors and distinctive logic gates. ISO specifies the drawing-sheet profile. These are selected drawing conventions, not certified standards compliance.",
            "EN / PN / ISO używają rezystorów i bramek prostokątnych w stylu IEC. IEEE/ANSI używa rezystorów zygzakowych i bramek o kształtach charakterystycznych. ISO określa profil arkusza. To wybrane konwencje rysunkowe, nie certyfikat zgodności z normami."))
        self.key_note.setText(self._t(
            'Get a key at <a href="https://aistudio.google.com/apikey">Google AI Studio</a>. The key is protected with Windows DPAPI and never saved in ELS. AI sends your selected project data and optional PDF to Google only after confirmation; provider fees may apply.',
            'Klucz uzyskasz w <a href="https://aistudio.google.com/apikey">Google AI Studio</a>. Klucz jest chroniony Windows DPAPI i nie trafia do ELS. AI wysyła wybrane dane projektu i opcjonalny PDF do Google dopiero po potwierdzeniu; operator może naliczać opłaty.'))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("Start" if self.first_run else "Save", "Rozpocznij" if self.first_run else "Zapisz"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("Cancel", "Anuluj"))

    def _browse_editor(self):
        path, _ = QFileDialog.getOpenFileName(self, self._t("Select code editor", "Wybierz edytor kodu"), file_dialog_directory(self._settings), "Programs (*.exe);;All files (*)")
        if path:
            if self.editor.findData(path) < 0:
                self.editor.addItem(path, path)
            self.editor.setCurrentIndex(self.editor.findData(path))

    def _browse_directory(self):
        path = QFileDialog.getExistingDirectory(self, self._t("Default folder", "Domyślny folder"), self.directory.text() or documents_directory())
        if path:
            self.directory.setText(path)

    def _accept(self):
        directory = Path(self.directory.text().strip() or documents_directory()).expanduser()
        if not directory.is_absolute() or not directory.is_dir():
            QMessageBox.warning(self, self._t("Folder", "Folder"), self._t("Select an existing folder.", "Wybierz istniejący folder."))
            return
        key = self.key.text().strip()
        if AI_AVAILABLE and key and (not key.isascii() or any(character.isspace() for character in key)):
            QMessageBox.warning(self, "Gemini", self._t("The API key must contain ASCII characters without whitespace.", "Klucz API musi zawierać znaki ASCII bez białych znaków."))
            return
        self._settings = AppSettings(
            language=self.language.currentData(), standard=self.standard.currentText(),
            paper_size=self.paper.currentText(), orientation=self.orientation.currentData(),
            grid_visible=self.grid.isChecked(), editor_path=self.editor.currentData() or "",
            api_key=self.key.text().strip() if AI_AVAILABLE else self._settings.api_key,
            gemini_model="auto" if AI_AVAILABLE else self._settings.gemini_model, setup_complete=True,
            default_display_names=dict(self._settings.default_display_names),
            default_component_values=dict(self._settings.default_component_values),
            default_directory=str(directory),
            default_author=self.author.text().strip(), dramatic_faults=self.fault_effect.currentData()=="mega",
            fault_effect=self.fault_effect.currentData(),theme=self.theme.currentData(),
            window_mode=self.window_mode.currentData(),
            ai_chat_consent=self.ai_consent.isChecked() if AI_AVAILABLE else self._settings.ai_chat_consent,
        )
        self.accept()

    def result_settings(self) -> AppSettings:
        """Kopia uniemożliwia zmianę aktywnych ustawień przez anulowany formularz."""
        return replace(self._settings)

    def reject(self):
        install_ui_language(self._settings.language)
        super().reject()
