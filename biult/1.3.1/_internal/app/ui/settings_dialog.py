"""Pierwsze uruchomienie i późniejsza konfiguracja używają tego samego formularza."""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget, QScrollArea, QTabWidget,
)

from app.core.settings import AppSettings, default_editor, detected_editors, documents_directory, file_dialog_directory, default_code_directory
from app.ui.i18n import install_ui_language
from app.core.features import AI_AVAILABLE


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None, first_run: bool = False):
        super().__init__(parent)
        self._settings = replace(settings)
        self.first_run = first_run
        self.setMinimumWidth(620)
        root_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget(); scroll.setWidget(body)
        root_layout.addWidget(scroll)
        layout = QVBoxLayout(body)
        self.resize(720, 700)
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
        self.key.setMaxLength(512)
        self.provider = QComboBox()
        self.provider.addItem("Google Gemini", "gemini")
        self.provider.addItem("OpenAI", "openai")
        self.provider.addItem("Local AI (Ollama / LM Studio)", "local")
        self.provider.addItem("None", "none")
        self.provider.setCurrentIndex(max(0, self.provider.findData(settings.ai_provider)))
        self.openai_key = QLineEdit(settings.openai_api_key)
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setMaxLength(512)
        self.openai_model = QLineEdit(settings.openai_model)
        self.openai_model.setMaxLength(100)
        self._provider_keys = {"gemini": settings.api_key, "openai": settings.openai_api_key}
        self._key_provider = "gemini"
        # Model jest szczegółem integracji, nie obowiązkiem użytkownika.
        self.model = QLabel()
        self.ai_consent = QCheckBox()
        self.ai_consent.setChecked(settings.ai_chat_consent or bool(settings.ai_request_consents.get(settings.ai_provider)))
        self.directory = QLineEdit(settings.default_directory or documents_directory())
        self.directory_button = QPushButton("…")
        self.directory_button.setFixedWidth(35)
        self.directory_button.clicked.connect(self._browse_directory)
        directory_row = QWidget()
        directory_layout = QHBoxLayout(directory_row)
        directory_layout.setContentsMargins(0, 0, 0, 0)
        directory_layout.addWidget(self.directory, 1)
        directory_layout.addWidget(self.directory_button)
        self.code_directory=QLineEdit(settings.default_code_directory or default_code_directory())
        self.code_directory_button=QPushButton("…")
        self.code_directory_button.setFixedWidth(35)
        self.code_directory_button.clicked.connect(self._browse_code_directory)
        code_directory_row=QWidget()
        code_directory_layout=QHBoxLayout(code_directory_row)
        code_directory_layout.setContentsMargins(0,0,0,0)
        code_directory_layout.addWidget(self.code_directory,1)
        code_directory_layout.addWidget(self.code_directory_button)
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
                      self.grid, editor_row, self.key, self.model, directory_row, code_directory_row, self.ai_consent, self.author, self.fault_effect, self.window_mode,self.theme):
            label = QLabel()
            self._rows.append(label)
            self.form.addRow(label, field)
        self.norm_note = QLabel()
        self.provider_label = QLabel()
        self.openai_key_label = QLabel()
        self.openai_model_label = QLabel()
        self.form.insertRow(6, self.provider_label, self.provider)
        self.form.setRowVisible(self.model, False)
        self.openai_key.hide()
        self.openai_model.hide()
        self.provider.currentIndexChanged.connect(self._provider_changed)
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
        # Move intact label/field pairs into topical tabs. Keep field objects
        # and translation indices stable so language changes preserve values.
        layout.removeItem(self.form)
        pairs=[]
        while self.form.rowCount():
            row=self.form.takeRow(0)
            pairs.append((row.labelItem.widget() if row.labelItem else None, row.fieldItem.widget()))
        self.settings_tabs=QTabWidget(); layout.addWidget(self.settings_tabs)
        self.tab_forms=[]; pages=[]
        for _ in range(4):
            page=QWidget(); page_layout=QVBoxLayout(page); form=QFormLayout()
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            page_layout.addLayout(form); page_layout.addStretch()
            self.settings_tabs.addTab(page, ""); self.tab_forms.append(form); pages.append(page_layout)
        for label,field in pairs:
            if field is self.model:
                label.hide(); field.hide(); continue
            tab=2 if field in (self.provider,self.key,self.ai_consent) else 3 if field is self.fault_effect else 1 if field in (self.standard,self.paper,self.orientation,self.grid,editor_row,code_directory_row) else 0
            self.tab_forms[tab].addRow(label,field)
        self.form=self.tab_forms[2]
        # Only relevant for the OpenAI provider; keep the configured model
        # visible and editable in the AI settings instead of resetting it.
        self.form.insertRow(1, self.openai_model_label, self.openai_model)
        self.scope_size=QComboBox()
        for key in ('normal','large','huge'): self.scope_size.addItem(key,key)
        self.scope_size.setCurrentIndex(max(0,self.scope_size.findData(settings.scope_size)))
        self.scope_label=QLabel(); self.stop_on_fault=QCheckBox(); self.stop_on_fault.setChecked(settings.stop_on_fault)
        self.tab_forms[3].addRow(self.scope_label,self.scope_size)
        self.tab_forms[3].addRow(self.stop_on_fault)
        from PySide6.QtWidgets import QDoubleSpinBox
        self.scope_volts_div=QDoubleSpinBox(); self.scope_volts_div.setDecimals(3); self.scope_volts_div.setRange(.001,1e6); self.scope_volts_div.setValue(settings.scope_volts_div)
        self.scope_time_div=QDoubleSpinBox(); self.scope_time_div.setDecimals(6); self.scope_time_div.setRange(.000001,100); self.scope_time_div.setValue(settings.scope_time_div)
        self.scope_autoscale=QCheckBox(); self.scope_autoscale.setChecked(settings.scope_autoscale)
        self.scope_volts_label=QLabel(); self.scope_time_label=QLabel()
        self.tab_forms[3].addRow(self.scope_volts_label,self.scope_volts_div); self.tab_forms[3].addRow(self.scope_time_label,self.scope_time_div); self.tab_forms[3].addRow(self.scope_autoscale)
        self.local_url=QLineEdit(settings.local_ai_url); self.local_url.setMaxLength(250)
        self.local_model=QLineEdit(settings.local_ai_model); self.local_model.setMaxLength(200)
        self.local_token=QLineEdit(settings.local_ai_token); self.local_token.setEchoMode(QLineEdit.EchoMode.Password); self.local_token.setMaxLength(2000)
        self.local_token_label=QLabel()
        self.local_model.setPlaceholderText('qwen2.5:7b / installed-model-name')
        self.local_url_label=QLabel(); self.local_model_label=QLabel()
        self.form.insertRow(1,self.local_url_label,self.local_url)
        self.form.insertRow(2,self.local_model_label,self.local_model)
        self.local_tutorial = QPushButton()
        self.rotation_direction=QComboBox()
        self.rotation_direction.addItem('','cw'); self.rotation_direction.addItem('','ccw')
        self.rotation_direction.setCurrentIndex(max(0,self.rotation_direction.findData(settings.rotation_direction)))
        self.rotation_label=QLabel(); self.tab_forms[1].addRow(self.rotation_label,self.rotation_direction)
        self.wires_through_cases=QCheckBox(); self.wires_through_cases.setChecked(settings.wires_through_cases); self.tab_forms[1].addRow(self.wires_through_cases)
        self.local_tutorial.clicked.connect(self._show_local_tutorial)
        self.form.insertRow(3,self.local_token_label,self.local_token)
        self.form.insertRow(4, self.local_tutorial)
        for note,tab in ((self.norm_note,1),(self.fault_note,3),(self.key_note,2)):
            layout.removeWidget(note); pages[tab].insertWidget(1,note)
        if not AI_AVAILABLE:
            # Ukryj całe wiersze (również etykiety), nie tylko same pola.
            for field in (self.key, self.model, self.ai_consent, self.openai_model):
                self.form.setRowVisible(field, False)
                field.setEnabled(False)
            self.key_note.hide()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        root_layout.addWidget(self.buttons)
        self.language.currentIndexChanged.connect(self._translate)
        self._translate()
        self._provider_changed()

    def _provider_changed(self):
        self._provider_keys[self._key_provider] = self.key.text().strip()
        if self._key_provider!=self.provider.currentData():
            provider=self.provider.currentData()
            self.ai_consent.setChecked(bool(self._settings.ai_request_consents.get(provider)) or provider==self._settings.ai_provider and self._settings.ai_chat_consent)
        self._key_provider = self.provider.currentData()
        self.key.setText(self._provider_keys.get(self._key_provider, ""))
        self.form.setRowVisible(self.key, self._key_provider in {'gemini','openai'})
        self.form.setRowVisible(self.openai_model, AI_AVAILABLE and self._key_provider == "openai")
        self.form.setRowVisible(self.local_url,self._key_provider=='local')
        self.form.setRowVisible(self.local_model,self._key_provider=='local')
        self.form.setRowVisible(self.local_token,self._key_provider=='local')
        self.form.setRowVisible(self.local_tutorial,self._key_provider=='local')
        self.local_token_label.setText(self._t('Local API token (optional)','Token lokalnego API (opcjonalny)'))
        self.local_url_label.setText(self._t('Local server URL','Adres lokalnego serwera'))
        self.local_model_label.setText(self._t('Installed local model','Zainstalowany model lokalny'))
        self.form.setRowVisible(self.ai_consent, self._key_provider != "none")
        self._rows[6].setText(self._t("OpenAI key", "Klucz OpenAI") if self._key_provider == "openai" else self._t("Gemini key", "Klucz Gemini"))
        self._local_note()

    def _show_local_tutorial(self):
        from app.ui.local_ai_guide import LocalAIGuide
        LocalAIGuide(self.language.currentData(), self).exec()

    def _local_note(self):
        if self.provider.currentData()=='local':
            self.key_note.setText(self._t('Run a local Chat Completions server and use its displayed port and model ID. Ollama usually uses 11434, LM Studio 1234. HTTP 401 means authentication was rejected: enter a token from LM Studio → Server Settings → Manage Tokens above. Tokens are protected by Windows DPAPI, not saved in projects. No cloud API key is used. ElectroSchem does not download models or start servers.',
                'Uruchom lokalny serwer Chat Completions i wpisz wyświetlany port oraz ID modelu. Ollama zwykle używa 11434, LM Studio 1234. HTTP 401 oznacza odrzucone uwierzytelnianie: wpisz powyżej token z LM Studio → Server Settings → Manage Tokens. Token chroni Windows DPAPI; nie trafia do projektu. Klucz chmurowy nie jest potrzebny. ElectroSchem nie pobiera modeli ani nie uruchamia serwerów.'))
        else:
            self.key_note.setText(self._t('Cloud API keys are protected by Windows DPAPI and never saved in ELS. Conversation, working sheet and library are sent only after consent. API billing is separate from a ChatGPT subscription.','Klucze chmurowego API chroni Windows DPAPI; nie trafiają do ELS. Rozmowa, roboczy arkusz i biblioteka są wysyłane dopiero po zgodzie. Rozliczenia API są oddzielne od abonamentu ChatGPT.'))

    def _t(self, en: str, pl: str) -> str:
        return pl if self.language.currentData() == "pl" else en

    def _translate(self):
        self.rotation_label.setText(self._t('R rotation direction (Ctrl+R: opposite)','Kierunek obrotu R (Ctrl+R: przeciwny)'))
        self.wires_through_cases.setText(self._t('Always show faint wires under cases (hold Shift+S temporarily)','Zawsze pokazuj blade przewody pod obudowami (chwilowo: przytrzymaj Shift+S)'))
        self.rotation_direction.setItemText(0,self._t('Clockwise','Zgodnie z ruchem wskazówek zegara'))
        self.rotation_direction.setItemText(1,self._t('Counterclockwise','Przeciwnie do ruchu wskazówek zegara'))
        self.local_tutorial.setText(self._t('Local AI setup tutorial and hardware advice', 'Tutorial lokalnego AI i dobór sprzętu'))
        self.local_token_label.setText(self._t('Local API token (optional)','Token lokalnego API (opcjonalny)'))
        self.scope_volts_label.setText(self._t('Default V/division','Domyślna skala V/działkę'))
        self.scope_time_label.setText(self._t('Default time/division [s]','Domyślny czas/działkę [s]'))
        self.scope_autoscale.setText(self._t('Automatic voltage and time scales','Automatyczne skale napięcia i czasu oscyloskopu'))
        self.scope_label.setText(self._t('Oscilloscope display size','Wielkość ekranu oscyloskopu'))
        for i,pair in enumerate((('Normal (480 × 260)','Normalny (480 × 260)'),('Large (640 × 350)','Duży (640 × 350)'),('Very large (800 × 440)','Bardzo duży (800 × 440)'))): self.scope_size.setItemText(i,self._t(*pair))
        self.stop_on_fault.setText(self._t('Stop simulation on component failure','Zatrzymaj symulację przy awarii elementu'))
        if hasattr(self,"settings_tabs"):
            for index,pair in enumerate((("General","Ogólne"),("Editor and code","Edytor i kod"),("AI","AI"),("Simulation","Symulacja"))):
                self.settings_tabs.setTabText(index,self._t(*pair))
        self.provider.setItemText(self.provider.findData('none'), self._t("None", "Brak"))
        self.provider.setItemText(self.provider.findData('local'),self._t('Local AI (Ollama / LM Studio)','Lokalne AI (Ollama / LM Studio)'))
        self.provider_label.setText(self._t("AI provider", "Dostawca AI"))
        self.local_url_label.setText(self._t('Local server URL','Adres lokalnego serwera'))
        self.local_model_label.setText(self._t('Installed local model','Zainstalowany model lokalny'))
        self.openai_key_label.setText(self._t("OpenAI API key (optional)", "Klucz API OpenAI (opcjonalny)"))
        self.openai_model_label.setText(self._t("OpenAI model", "Model OpenAI"))
        install_ui_language(self.language.currentData())
        self.setWindowTitle(self._t("Welcome to ElectroSchem" if self.first_run else "Settings",
                                   "Witaj w ElectroSchem" if self.first_run else "Ustawienia"))
        self.intro.setText(self._t("The editor works offline. Cloud AI requires Internet; local AI requires a running local model.",
                                  "Edytor działa offline. Chmurowe AI wymaga internetu; lokalne AI wymaga uruchomionego modelu lokalnego."))
        labels = [("Language", "Język"), ("Drawing profile", "Profil rysunkowy"),
                  ("Default sheet", "Domyślny arkusz"), ("Default orientation", "Domyślna Orientacja"),
                  ("Grid", "Siatka"), ("Code editor", "Edytor kodu"),
                  ("Gemini API key (optional)", "Klucz API Gemini (opcjonalny)"),
                  ("Gemini model", "Model Gemini"), ("Default folder", "Domyślny folder"), ("Default code folder", "Domyślny folder kodów"), ("AI privacy", "Prywatność AI"),
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
        self.key.setPlaceholderText(self._t("Enter the selected provider's API key", "Wpisz klucz API wybranego dostawcy"))
        self.model.setText(self._t("Automatic — detected from Gemini API", "Automatyczny — wykrywany przez API Gemini"))
        self.ai_consent.setText(self._t("Remember consent for the selected AI provider", "Zapamiętana zgoda dla wybranego dostawcy AI"))
        self.ai_consent.setToolTip(self._t("Uncheck to ask for consent before the next chat request. PDF transfers are confirmed separately.", "Odznacz, aby zapytać o zgodę przed następną wiadomością. Wysyłanie PDF potwierdza się osobno."))
        self.norm_note.setText(self._t(
            "EN / PN / ISO use IEC-style resistors and rectangular logic gates. IEEE/ANSI uses zigzag resistors and distinctive logic gates. ISO specifies the drawing-sheet profile. These are selected drawing conventions, not certified standards compliance.",
            "EN / PN / ISO używają rezystorów i bramek prostokątnych w stylu IEC. IEEE/ANSI używa rezystorów zygzakowych i bramek o kształtach charakterystycznych. ISO określa profil arkusza. To wybrane konwencje rysunkowe, nie certyfikat zgodności z normami."))
        self.key_note.setText(self._t(
            'Get a key at <a href="https://aistudio.google.com/apikey">Google AI Studio</a>. The key is protected with Windows DPAPI and never saved in ELS. AI sends your selected project data and optional PDF to Google only after confirmation; provider fees may apply.',
            'Klucz uzyskasz w <a href="https://aistudio.google.com/apikey">Google AI Studio</a>. Klucz jest chroniony Windows DPAPI i nie trafia do ELS. AI wysyła wybrane dane projektu i opcjonalny PDF do Google dopiero po potwierdzeniu; operator może naliczać opłaty.'))
        self.key_note.setText(self._t(
            'Keys: <a href="https://aistudio.google.com/apikey">Gemini</a> or <a href="https://platform.openai.com/api-keys">OpenAI</a>. Keys are protected with Windows DPAPI and never included in ELS. The selected provider receives chat, working sheet and library only after consent. API billing is separate from ChatGPT subscriptions.',
            'Klucze: <a href="https://aistudio.google.com/apikey">Gemini</a> lub <a href="https://platform.openai.com/api-keys">OpenAI</a>. Klucze chroni Windows DPAPI; nie trafiają do ELS. Wybrany dostawca otrzymuje czat, roboczy arkusz i bibliotekę dopiero po zgodzie. Rozliczenia API są oddzielne od abonamentu ChatGPT.'))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self._t("Start" if self.first_run else "Save", "Rozpocznij" if self.first_run else "Zapisz"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("Cancel", "Anuluj"))
        self._rows[6].setText(self._t("OpenAI key", "Klucz OpenAI") if self.provider.currentData() == "openai" else self._t("Gemini key", "Klucz Gemini"))
        self._local_note()

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
        code_directory=Path(self.code_directory.text().strip() or default_code_directory()).expanduser()
        existing=next((p for p in (code_directory,*code_directory.parents) if p.exists()),None)
        if not code_directory.is_absolute() or (existing is not None and not existing.is_dir()):
            QMessageBox.warning(self,self._t("Code folder","Folder kodów"),self._t(
                "Choose an absolute code-folder path. It will be created when code is generated.",
                "Wybierz bezwzględną ścieżkę folderu kodów. Folder powstanie przy tworzeniu kodu."))
            return
        self._provider_keys[self._key_provider] = self.key.text().strip()
        key = self._provider_keys.get("gemini", "")
        if self.provider.currentData()=='local':
            try:
                from app.services.local_ai import endpoint,body
                endpoint(self.local_url.text()); body(self.local_model.text(),'','')
            except ValueError as error:
                from app.services.local_ai import localized_error
                QMessageBox.warning(self,self._t('Local AI','Lokalne AI'),localized_error(str(error),self.language.currentData())); return
        openai_key = self._provider_keys.get("openai", "")
        if openai_key and (not openai_key.isascii() or any(c.isspace() for c in openai_key)):
            QMessageBox.warning(self, "OpenAI", self._t("Invalid API key.", "Niepoprawny klucz API."))
            return
        openai_model = self.openai_model.text().strip()
        if self.provider.currentData() == "openai" and not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", openai_model):
            QMessageBox.warning(self, "OpenAI", self._t(
                "Enter a valid OpenAI model ID (letters, numbers, dot, underscore or hyphen).",
                "Wpisz poprawne ID modelu OpenAI (litery, cyfry, kropka, podkreślenie lub łącznik)."))
            return
        if AI_AVAILABLE and key and (not key.isascii() or any(character.isspace() for character in key)):
            QMessageBox.warning(self, "Gemini", self._t("The API key must contain ASCII characters without whitespace.", "Klucz API musi zawierać znaki ASCII bez białych znaków."))
            return
        self._settings = AppSettings(
            language=self.language.currentData(), standard=self.standard.currentText(),
            paper_size=self.paper.currentText(), orientation=self.orientation.currentData(),
            grid_visible=self.grid.isChecked(), editor_path=self.editor.currentData() or "",
            api_key=key if AI_AVAILABLE else self._settings.api_key,
            ai_provider=self.provider.currentData(),
            local_ai_url=self.local_url.text().strip(),local_ai_model=self.local_model.text().strip(),
            local_ai_token=self.local_token.text().strip(),
            rotation_direction=self.rotation_direction.currentData(),
            wires_through_cases=self.wires_through_cases.isChecked(),
            openai_api_key=openai_key,
            openai_model=openai_model,
            gemini_model="auto" if AI_AVAILABLE else self._settings.gemini_model, setup_complete=True,
            default_display_names=dict(self._settings.default_display_names),
            default_component_values=dict(self._settings.default_component_values),
            favorite_components=deepcopy(self._settings.favorite_components),
            default_directory=str(directory),
            default_code_directory=str(code_directory),
            default_author=self.author.text().strip(), dramatic_faults=self.fault_effect.currentData()=="mega",
            fault_effect=self.fault_effect.currentData(),theme=self.theme.currentData(),
            window_mode=self.window_mode.currentData(),
            scope_size=self.scope_size.currentData(),stop_on_fault=self.stop_on_fault.isChecked(),
            scope_volts_div=self.scope_volts_div.value(),scope_time_div=self.scope_time_div.value(),scope_autoscale=self.scope_autoscale.isChecked(),
            ai_request_consents={k:v for k,v in self._settings.ai_request_consents.items() if self.ai_consent.isChecked() or k!=self.provider.currentData()},
            ai_chat_consent=self.ai_consent.isChecked() if AI_AVAILABLE else self._settings.ai_chat_consent,
        )
        self.accept()

    def _browse_code_directory(self):
        start=Path(self.code_directory.text().strip() or default_code_directory()).expanduser()
        start=next((p for p in (start,*start.parents) if p.is_dir()),Path(documents_directory()))
        path=QFileDialog.getExistingDirectory(self,self._t("Default code folder","Domyślny folder kodów"),str(start))
        if path: self.code_directory.setText(path)

    def result_settings(self) -> AppSettings:
        """Kopia uniemożliwia zmianę aktywnych ustawień przez anulowany formularz."""
        return replace(self._settings)

    def reject(self):
        install_ui_language(self._settings.language)
        super().reject()
