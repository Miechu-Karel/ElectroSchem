"""Boczny czat schematu: rozmowa i przegląd zmian obok edytora.

Panel nie jest modalny, więc dokument może zmienić się podczas pracy sieci.
Każda propozycja pamięta dokładny stan oraz ID arkusza. Nie można zastosować
starej odpowiedzi do nowego projektu lub po ręcznej zmianie schematu.
"""
from copy import deepcopy
import json

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
    QScrollArea, QFrame, QComboBox, QProgressBar, QMessageBox,
)

from app.services.gemini import GeminiClient, request_body, validate_proposal
from app.services.proposals import apply_proposal
from app.libraries.built_in import get_definition, item_name
from app.core.settings import remember_chat_consent
from app.core.models import Project
from app.ui.ai_preview import AiPreview


class ChatInput(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if not event.isAutoRepeat():
                self.submitted.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class AiPanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.history = []
        self._proposal = None
        self._snapshot = None
        self._sheet_id = None
        self._pending_prompt = ""
        self._request_mode = "build"
        self._consented = False
        self._busy = False
        self._candidate = None
        self._last_request = None
        self._retry_history = []
        self.setObjectName("aiPanel")
        self.setMinimumWidth(345)
        self.setStyleSheet("""
            QWidget#aiPanel { background: #f5f7fb; }
            QFrame#aiCard { background: #ffffff; border: 1px solid #cedde8; border-radius: 8px; }
            QFrame#userMessage { background: #e9f3ff; border: 1px solid #cfdef0; border-radius: 8px; }
            QFrame#assistantMessage { background: #ffffff; border: 1px solid #e0e7ef; border-radius: 8px; }
            QLabel { background: transparent; border: none; }
            QPushButton { padding: 6px 9px; border: 1px solid #cbd8e5; border-radius: 5px; background: #fff; }
            QPushButton:hover { background: #e5effa; }
            QPushButton:disabled { color: #91a1b1; background: #f2f5f8; }
            QPushButton#aiPrimary { background: #1765ab; color: white; border: 1px solid #1765ab; }
            QPushButton#aiPrimary:disabled { background: #9bb6d0; border-color: #9bb6d0; }
            QPlainTextEdit { background: white; border: 1px solid #adc3d9; border-radius: 7px; padding: 7px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(9)
        header = QHBoxLayout()
        self.new_button = QPushButton()
        self.new_button.clicked.connect(self.new_chat)
        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(lambda: self.window.show_settings())
        self.pdf_button = QPushButton("PDF")
        self.pdf_button.clicked.connect(self.window.show_datasheet_ai)
        header.addWidget(self.new_button)
        header.addStretch()
        header.addWidget(self.pdf_button)
        header.addWidget(self.settings_button)
        layout.addLayout(header)
        self.context_label = QLabel()
        self.context_label.setWordWrap(True)
        self.context_label.setStyleSheet("color: #51687f; font-size: 11px;")
        layout.addWidget(self.context_label)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.message_area = QWidget()
        self.messages = QVBoxLayout(self.message_area)
        self.messages.setContentsMargins(0, 0, 5, 0)
        self.messages.setSpacing(12)
        self.messages.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.message_area)
        layout.addWidget(self.scroll, 1)

        self.proposal_card = QFrame()
        self.proposal_card.setObjectName("aiCard")
        card = QVBoxLayout(self.proposal_card)
        self.proposal_label = QLabel()
        self.proposal_label.setWordWrap(True)
        self.proposal_label.setTextFormat(Qt.TextFormat.PlainText)
        card.addWidget(self.proposal_label)
        self.preview = AiPreview()
        card.addWidget(self.preview)
        self.proposal_details = QPlainTextEdit()
        self.proposal_details.setReadOnly(True)
        self.proposal_details.setMaximumHeight(75)
        card.addWidget(self.proposal_details)
        buttons = QHBoxLayout()
        self.apply_button = QPushButton()
        self.apply_button.setObjectName("aiPrimary")
        self.apply_button.clicked.connect(self.apply)
        self.discard_button = QPushButton()
        self.discard_button.clicked.connect(self.discard)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.discard_button)
        card.addLayout(buttons)
        self.proposal_card.hide()
        layout.addWidget(self.proposal_card)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumHeight(3)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.prompt = ChatInput()
        self.prompt.setMinimumHeight(90)
        self.prompt.setMaximumHeight(145)
        self.prompt.submitted.connect(self.send)
        layout.addWidget(self.prompt)
        footer = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("", "build")
        self.mode.addItem("", "ask")
        self.model_label = QLabel("Gemini · Auto")
        self.model_label.setStyleSheet("font-size: 11px; color: #617489;")
        self.model_label.setWordWrap(True)
        self.send_button = QPushButton()
        self.send_button.setObjectName("aiPrimary")
        self.send_button.clicked.connect(self.send)
        self.stop_button = QPushButton()
        self.stop_button.clicked.connect(self.cancel)
        self.stop_button.hide()
        self.regenerate_button = QPushButton()
        self.regenerate_button.clicked.connect(self.regenerate)
        self.regenerate_button.setEnabled(False)
        footer.addWidget(self.mode)
        footer.addWidget(self.model_label, 1)
        footer.addWidget(self.send_button)
        footer.addWidget(self.stop_button)
        layout.addLayout(footer)
        layout.addWidget(self.regenerate_button)
        self.hint = QLabel()
        self.hint.setStyleSheet("font-size: 10px; color: #617489;")
        layout.addWidget(self.hint)
        self.client = GeminiClient(self)
        self.client.progress.connect(self._progress)
        self.client.completed.connect(self._completed)
        self.client.failed.connect(self._failed)
        self.client.cancelled.connect(self._cancelled)
        self.translate()
        self._welcome()

    def t(self, en, pl):
        return self.window.t(en, pl)

    def translate(self):
        self.new_button.setText(self.t("+ New chat", "+ Nowa rozmowa"))
        self.settings_button.setText(self.t("Settings", "Ustawienia"))
        self.pdf_button.setToolTip(self.t("Separate datasheet analysis", "Osobna analiza dokumentacji"))
        self.send_button.setText(self.t("Send ↑", "Wyślij ↑"))
        self.stop_button.setText(self.t("Stop", "Zatrzymaj"))
        self.regenerate_button.setText(self.t("Regenerate answer", "Wygeneruj ponownie"))
        self.apply_button.setText(self.t("Apply changes", "Zastosuj zmiany"))
        self.discard_button.setText(self.t("Discard", "Odrzuć"))
        self.mode.setItemText(0, self.t("Build", "Buduj"))
        self.mode.setItemText(1, self.t("Ask", "Zapytaj"))
        self.mode.setToolTip(self.t("Build proposes additions to your schematic. Ask only answers questions.",
                                   "Buduj proponuje dodanie elementów i połączeń. Zapytaj tylko odpowiada na pytania."))
        self.prompt.setPlaceholderText(self.t("Describe a circuit or ask a question…", "Opisz układ lub zadaj pytanie…"))
        self.hint.setText(self.t("Enter: send · Shift+Enter: new line", "Enter: wyślij · Shift+Enter: nowa linia"))
        self.update_context_label()

    def update_context_label(self):
        index = self.window.tabs.currentIndex()
        if 0 <= index < len(self.window.project.sheets):
            sheet = self.window.project.sheets[index]
            count = len(self.window._current_view().scene.selectedItems())
            self.context_label.setText(self.t("Context: ", "Kontekst: ") + sheet.name + self.t(f" · {count} selected", f" · zaznaczone: {count}"))

    def _welcome(self):
        self._message("assistant", self.t(
            "Let's work on your schematic.\n\nBuild — describe a circuit; review and apply the proposed components and wires.\nAsk — questions about the current sheet and selected objects.\n\nPDF datasheets have their own tool. AI suggestions should be checked before building a real circuit.",
            "Popracujmy nad schematem.\n\nBuduj — opisz układ; sprawdź i zastosuj proponowane elementy oraz przewody.\nZapytaj — pytania o bieżący arkusz i zaznaczone obiekty.\n\nDokumentacja PDF ma osobne narzędzie. Sprawdź propozycje AI przed budową rzeczywistego układu."))

    def _message(self, role, text):
        # Zwykły tekst: odpowiedź modelu nie może ładować obrazów z sieci,
        # lokalnych plików ani interpretować HTML/javascript.
        frame = QFrame()
        frame.setObjectName("userMessage" if role == "user" else "assistantMessage")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 10, 12, 12)
        title = QLabel(self.t("YOU", "TY") if role == "user" else "ELECTROSCHEM AI")
        title.setStyleSheet("font-size: 10px; font-weight: bold; color: #526a84;")
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(title)
        box.addWidget(label)
        self.messages.addWidget(frame)
        if self.messages.count() > 60:
            old = self.messages.takeAt(0)
            old.widget().deleteLater()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def _set_busy(self, busy):
        self._busy = busy
        self.progress.setVisible(busy)
        self.send_button.setVisible(not busy)
        self.stop_button.setVisible(busy)
        self.mode.setEnabled(not busy)
        self.apply_button.setEnabled(not busy and self._proposal is not None)
        self.regenerate_button.setEnabled(not busy and self._last_request is not None and bool(self.window.settings.api_key))

    def cancel(self):
        self.client.cancel()

    def new_chat(self):
        self.cancel()
        self.history.clear()
        self._proposal = self._snapshot = self._sheet_id = None
        self._pending_prompt = ""
        self._last_request = self._candidate = None
        self._retry_history = []
        self.proposal_card.hide()
        self.prompt.clear()
        self.status.clear()
        while self.messages.count():
            self.messages.takeAt(0).widget().deleteLater()
        self._welcome()
        self._set_busy(False)

    def regenerate(self):
        if self._busy or not self._last_request or not self.window.settings.api_key:
            return
        # Odnawiamy ostatnie polecenie z aktualnym arkuszem, ale bez odpowiedzi,
        # którą zastępujemy. Nie kasujemy rozpoczętego przez użytkownika szkicu.
        draft = self.prompt.toPlainText()
        text, mode = self._last_request
        self.prompt.setPlainText(text)
        self.mode.setCurrentIndex(self.mode.findData(mode))
        self.send(regenerating=True)
        if draft != text:
            self.prompt.setPlainText(draft)

    def send(self, *, regenerating=False):
        if self._busy or self.client.busy:
            return
        text = self.prompt.toPlainText().strip()
        if not text:
            return
        if not self.window.settings.api_key:
            self.status.setText(self.t("Add your Gemini API key using Settings above.", "Podaj klucz API Gemini przyciskiem Ustawienia powyżej."))
            return
        self.window._sync_positions()
        context = self.window._ai_context()
        context["selected_ids"] = [i.data(1) for i in self.window._current_view().scene.selectedItems()]
        mode = self.mode.currentData()
        try:
            history = self._retry_history if regenerating else self.history
            body = request_body(text, context, self.window.settings.language, history=history, chat_only=mode == "ask")
        except (ValueError, TypeError, RecursionError):
            self.status.setText(self.t("The request or conversation is too large. Shorten it or start a new chat.",
                                      "Polecenie lub rozmowa są zbyt duże. Skróć je albo rozpocznij nową rozmowę."))
            return
        if not self._consented and not self.window.settings.ai_chat_consent:
            answer = QMessageBox.question(self, "Google Gemini", self.t(
                "Chat sends your conversation, current sheet, selection and component library to Google Gemini. Provider fees may apply. Remember this consent? You can revoke it in Settings → AI privacy. PDF files are confirmed separately.",
                "Czat wysyła rozmowę, bieżący arkusz, zaznaczenie i bibliotekę elementów do Google Gemini. Operator może naliczać opłaty. Zapamiętać zgodę? Możesz ją wycofać w Ustawienia → Prywatność AI. Pliki PDF potwierdza się osobno."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._consented = True
            try:
                remember_chat_consent(self.window.settings)
            except OSError:
                self._message("assistant", self.t("Consent applies to this session only because preferences could not be saved.", "Zgoda obowiązuje tylko w tej sesji, ponieważ nie udało się zapisać ustawień."))
        self._snapshot = deepcopy(self.window.project.to_dict())
        self._retry_history = deepcopy(history)
        self.history = deepcopy(history)
        self._last_request = (text, mode)
        self._candidate = None
        self._sheet_id = context["sheet"]["id"]
        self._proposal = None
        self.proposal_card.hide()
        self._request_mode, self._pending_prompt = mode, text
        self._message("user", text)
        self.prompt.clear()
        self._set_busy(True)
        try:
            self.client.start(self.window.settings.api_key, "auto", body)
        except (ValueError, TypeError):
            self._failed("key")

    def _progress(self, stage):
        if stage == "models":
            text = self.t("Finding an available model…", "Wykrywanie dostępnego modelu…")
        elif stage == "retry":
            text = self.t("Gemini is busy. Retrying shortly…", "Gemini jest zajęte. Ponowienie za chwilę…")
        else:
            self.model_label.setText(stage.removeprefix("generate:"))
            text = self.t("Preparing an answer…", "Przygotowywanie odpowiedzi…")
        self.status.setText(text)

    def _completed(self, proposal):
        self._set_busy(False)
        self._message("assistant", proposal["summary"])
        self.history.extend([
            {"role": "user", "parts": [{"text": self._pending_prompt}]},
            {"role": "model", "parts": [{"text": proposal["summary"] if self._request_mode == "ask" else json.dumps(proposal, ensure_ascii=False)}]},
        ])
        self.history = self.history[-12:]
        self._pending_prompt = ""
        if self._request_mode == "ask" or not any(proposal[key] for key in ("components", "wires", "custom_components")):
            self.status.setText(self.t("Ready", "Gotowe"))
            return
        try:
            self._proposal = validate_proposal(deepcopy(proposal))
            index = next(i for i, s in enumerate(self._snapshot["sheets"]) if s["id"] == self._sheet_id)
            # Walidacja semantyczna odbywa się PRZED pokazaniem przycisku, a nie
            # dopiero po kliknięciu. Podgląd i zatwierdzenie użyją tej samej kopii.
            self._candidate = apply_proposal(Project.from_dict(deepcopy(self._snapshot)), index, self._proposal)
            self.preview.set_project(self._candidate, index, self.window.settings)
        except (ValueError, TypeError, KeyError, StopIteration) as error:
            self._proposal = self._candidate = None
            self.apply_button.setEnabled(False)
            self.proposal_card.hide()
            self.status.setText(self.t("Cannot apply this proposal: ", "Nie można zastosować tej propozycji: ") + str(error) +
                                self.t(". Regenerate the answer.", ". Wygeneruj odpowiedź ponownie."))
            return
        count = len(proposal["components"])
        wires = len(proposal["wires"])
        custom = len(proposal["custom_components"])
        self.proposal_label.setText(self.t(f"PROPOSED CHANGES\n{count} components · {wires} connections · {custom} custom definitions",
                                         f"PROPONOWANE ZMIANY\nElementy: {count} · połączenia: {wires} · definicje customowe: {custom}"))
        # Human-readable change list instead of making JSON the main interface.
        details = []
        for component in proposal["components"]:
            definition = get_definition(component["library_id"], self.window.project.custom_components + proposal["custom_components"])
            name = component.get("display_name") or (item_name(definition, self.window.settings.language) if definition else component["library_id"])
            value = " ".join([component.get("value", ""), component.get("unit", "")]).strip()
            details.append(f"+ {name} · {value} [{component['key']}]")
        details += [f"+ {w['from']} [{w['from_pin']}] → {w['to']} [{w['to_pin']}]" for w in proposal["wires"]]
        details += ["+ " + c["name"] for c in proposal["custom_components"]]
        self.proposal_details.setPlainText("\n".join(details))
        self.proposal_card.show()
        self.apply_button.setEnabled(True)
        self.status.setText(self.t("Review the changes below. Nothing has been changed yet.", "Sprawdź zmiany poniżej. Jeszcze niczego nie zmieniono."))

    def apply(self):
        if self._proposal is None or self._busy:
            return
        self.window._sync_positions()
        if self.window.project.to_dict() != self._snapshot:
            self.apply_button.setEnabled(False)
            self.status.setText(self.t("The project changed since this request. Ask again using the current state.",
                                      "Projekt zmienił się od wysłania polecenia. Poproś ponownie z aktualnym stanem."))
            return
        index = next((i for i, sheet in enumerate(self.window.project.sheets) if sheet.id == self._sheet_id), None)
        if index is None:
            self.discard()
            return
        try:
            candidate = self._candidate or apply_proposal(self.window.project, index, self._proposal)
        except (ValueError, TypeError, KeyError) as error:
            self.status.setText(self.t("Invalid proposal; no changes applied: ", "Niepoprawna propozycja; nie zastosowano zmian: ") + str(error))
            return
        self.window.project = candidate
        self.window._rebuild_tabs(selected=index)
        self.window.record_history()
        self._proposal = None
        self._candidate = None
        self._last_request = None  # ponowienie zastosowanej propozycji dublowałoby układ
        self.regenerate_button.setEnabled(False)
        self.proposal_card.hide()
        self.apply_button.setEnabled(False)
        self.status.setText(self.t("Applied · Ctrl+Z to undo", "Zastosowano · Ctrl+Z, aby cofnąć"))
        self._message("assistant", self.t("Changes applied to the schematic. What next?", "Zmiany zastosowane na schemacie. Co dalej?"))
        # History clearly distinguishes proposed objects from applied ones.
        self.history.extend([
            {"role": "user", "parts": [{"text": "The previous proposal has now been applied. Use the updated project context for the next request."}]},
            {"role": "model", "parts": [{"text": "Application confirmed by the editor. I will use the updated project context."}]},
        ])
        self.history = self.history[-12:]
        self.update_context_label()

    def discard(self):
        self._proposal = None
        self._candidate = None
        self.proposal_card.hide()
        self.status.setText(self.t("Proposal discarded. No changes applied.", "Propozycja odrzucona. Nie zastosowano zmian."))

    def _failed(self, code):
        self._set_busy(False)
        messages = {
            "http_400": ("Gemini rejected the request (400). Try a shorter request or a new conversation.", "Gemini odrzuciło żądanie (400). Spróbuj krótszego polecenia lub nowej rozmowy."),
            "http_401": ("Invalid API key (401). Check Settings.", "Niepoprawny klucz API (401). Sprawdź Ustawienia."),
            "http_403": ("No API access (403). Check the key and project permissions in Google AI Studio.", "Brak dostępu do API (403). Sprawdź klucz i uprawnienia projektu w Google AI Studio."),
            "http_404": ("The model is no longer available (404). Try again to refresh the list.", "Model nie jest już dostępny (404). Ponów, aby odświeżyć listę."),
            "http_429": ("Google API quota reached (429). Check your Gemini account limits.", "Wyczerpany limit API Google (429). Sprawdź limity konta Gemini."),
            "http_503": ("Google's Gemini server is temporarily unavailable or overloaded (503), even after retries. Your message is kept; try again later.", "Serwer Google Gemini jest chwilowo niedostępny lub przeciążony (503), również po ponowieniu. Wiadomość została zachowana; spróbuj za chwilę."),
            "timeout": ("Gemini timed out. Try a smaller task.", "Przekroczono czas odpowiedzi Gemini. Spróbuj mniejszego zadania."),
            "invalid_response": ("The answer failed validation. The schematic is unchanged.", "Odpowiedź nie przeszła walidacji. Schemat pozostał bez zmian."),
            "incomplete": ("The answer was cut off. Ask for a smaller circuit.", "Odpowiedź została urwana. Poproś o mniejszy układ."),
            "blocked": ("Gemini did not return an answer.", "Gemini nie zwróciło odpowiedzi."),
            "no_model": ("No compatible model is available for this key.", "Brak zgodnego modelu dostępnego dla tego klucza."),
            "network": ("Network/TLS error. Check your connection and system clock.", "Błąd sieci/TLS. Sprawdź połączenie i zegar systemowy."),
            "key": ("Check the Gemini API key in Settings.", "Sprawdź klucz API Gemini w ustawieniach."),
        }
        message = self.t(*messages.get(code, ("Gemini service error: ", "Błąd usługi Gemini: "))) + (" " + code)
        self.status.setText(message)
        self._message("assistant", message)
        if self._pending_prompt and not self.prompt.toPlainText().strip():
            self.prompt.setPlainText(self._pending_prompt)

    def _cancelled(self):
        self._set_busy(False)
        self.status.setText(self.t("Stopped. The schematic is unchanged.", "Zatrzymano. Schemat pozostał bez zmian."))
