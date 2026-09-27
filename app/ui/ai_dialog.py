"""Asystent: polecenie → odpowiedź → kontrolowany podgląd → zastosowanie."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from app.core.settings import AppSettings, file_dialog_directory
from app.services.gemini import GeminiClient, MAX_PDF_BYTES, request_body, validate_proposal


class AiDialog(QDialog):
    def __init__(self, settings: AppSettings, context: dict, on_apply, parent=None, *, documentation=False):
        super().__init__(parent)
        self.settings = settings
        self.context = deepcopy(context)
        self.on_apply = on_apply
        self.documentation = documentation
        self.history = []
        self._pending_prompt = ""
        self._transcript = ""
        self._proposal = None
        self._applied = False
        self._pdf_data = None
        self._pdf_name = ""
        self.setWindowTitle(self._t("AI assistant — Gemini", "Asystent AI — Gemini"))
        if documentation:
            self.setWindowTitle(self._t("Datasheet analysis — Gemini", "Analiza dokumentacji — Gemini"))
        self.resize(820, 760)
        layout = QVBoxLayout(self)
        note = QLabel(self._t(
            "Chat about your circuit or ask for components and connections. Review proposed changes, then click Apply proposal. Datasheet analysis is a separate tool in Tools. Verify AI suggestions before building a real circuit.",
            "Porozmawiaj o układzie lub poproś o dodanie elementów i połączeń. Sprawdź wynik i kliknij Zastosuj propozycję. Analiza dokumentacji jest osobnym narzędziem w menu Narzędzia. Sprawdź propozycję AI przed budową rzeczywistego układu."))
        if documentation:
            note.setText(self._t("Select a PDF datasheet to analyse or create a custom component. This tool has no access to your chat or sheet contents. Verify extracted pins before applying.",
                                "Wybierz dokumentację PDF do analizy lub utworzenia własnego elementu. To narzędzie nie otrzymuje czatu ani zawartości arkusza. Sprawdź odczytane piny przed zastosowaniem."))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText(self._t("Describe what you need…", "Opisz, czego potrzebujesz…"))
        self.prompt.setMaximumHeight(150)
        layout.addWidget(self.prompt)
        self.pdf_panel = QWidget()
        pdf_row = QHBoxLayout(self.pdf_panel)
        self.pdf_button = QPushButton(self._t("Attach datasheet PDF…", "Dołącz dokumentację PDF…"))
        self.pdf_button.clicked.connect(self._choose_pdf)
        self.pdf_label = QLabel(self._t("No attachment", "Brak załącznika"))
        self.pdf_label.setWordWrap(True)
        self.pdf_clear = QPushButton(self._t("Remove PDF", "Usuń PDF"))
        self.pdf_clear.clicked.connect(self._clear_pdf)
        self.pdf_clear.setEnabled(False)
        pdf_row.addWidget(self.pdf_button)
        pdf_row.addWidget(self.pdf_label, 1)
        pdf_row.addWidget(self.pdf_clear)
        layout.addWidget(self.pdf_panel)
        self.pdf_panel.setVisible(documentation)
        self.tabs = QTabWidget()
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.tabs.addTab(self.summary, self._t("Answer / review", "Odpowiedź / przegląd"))
        self.tabs.addTab(self.preview, self._t("Proposed changes (JSON)", "Proponowane zmiany (JSON)"))
        layout.addWidget(self.tabs, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.generate_button = QPushButton(self._t("Send to Gemini", "Wyślij do Gemini"))
        self.generate_button.clicked.connect(self._generate)
        self.cancel_button = QPushButton(self._t("Cancel request", "Anuluj żądanie"))
        self.cancel_button.setEnabled(False)
        self.apply_button = QPushButton(self._t("Apply proposal", "Zastosuj propozycję"))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.close_button = QPushButton(self._t("Close", "Zamknij"))
        self.close_button.clicked.connect(self.reject)
        self.reset_button = QPushButton(self._t("New conversation", "Nowa rozmowa"))
        self.reset_button.clicked.connect(self._reset_chat)
        for button in (self.generate_button, self.cancel_button, self.apply_button, self.reset_button, self.close_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.client = GeminiClient(self)
        self.client.completed.connect(self._completed)
        self.client.failed.connect(self._failed)
        self.client.cancelled.connect(self._cancelled)
        self.client.progress.connect(self._progress)
        self.cancel_button.clicked.connect(self.client.cancel)
        if not settings.api_key:
            self.generate_button.setEnabled(False)
            self.status.setText(self._t("AI is disabled. Add your Gemini API key in Settings.", "AI jest wyłączone. Podaj klucz API Gemini w ustawieniach."))

    def _t(self, en: str, pl: str) -> str:
        return pl if self.settings.language == "pl" else en

    def _choose_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, self._t("Select PDF datasheet", "Wybierz dokumentację PDF"), file_dialog_directory(self.settings), "PDF (*.pdf)")
        if not path:
            return
        try:
            # Limit przed odczytem i ograniczony odczyt chronią również przed
            # podmianą/plikiem rosnącym pomiędzy stat() i open().
            source = Path(path)
            if source.stat().st_size > MAX_PDF_BYTES:
                raise ValueError("size")
            with source.open("rb") as stream:
                data = stream.read(MAX_PDF_BYTES + 1)
            if len(data) > MAX_PDF_BYTES or b"%PDF-" not in data[:1024]:
                raise ValueError("format")
            self._pdf_data = data
            self._pdf_name = source.name
            self.pdf_label.setText(f"{source.name} ({len(data) / 1024:.0f} KiB)")
            self.pdf_clear.setEnabled(True)
        except (OSError, ValueError):
            QMessageBox.warning(self, "PDF", self._t("Cannot read PDF. Select a valid file up to 10 MiB.", "Nie można odczytać PDF. Wybierz poprawny plik do 10 MiB."))

    def _clear_pdf(self):
        self._pdf_data = None
        self._pdf_name = ""
        self.pdf_label.setText(self._t("No attachment", "Brak załącznika"))
        self.pdf_clear.setEnabled(False)

    def _reset_chat(self):
        self.history.clear()
        self._transcript = ""
        self._proposal = None
        self.summary.clear()
        self.preview.clear()
        self.prompt.clear()
        self.apply_button.setEnabled(False)
        self.status.clear()

    def _progress(self, stage):
        if stage == "retry":
            self.status.setText(self._t("Gemini is temporarily busy. Retrying shortly…", "Gemini jest chwilowo zajęte. Ponowienie za chwilę…"))
        elif stage == "models":
            self.status.setText(self._t("Detecting an available Gemini model…", "Wykrywanie dostępnego modelu Gemini…"))
        else:
            self.status.setText(self._t("Waiting for Gemini — ", "Oczekiwanie na Gemini — ") + stage.removeprefix("generate:"))

    def _set_busy(self, busy):
        self.generate_button.setEnabled(not busy and bool(self.settings.api_key))
        self.cancel_button.setEnabled(busy)
        self.prompt.setReadOnly(busy)
        self.reset_button.setEnabled(not busy)
        self.pdf_button.setEnabled(not busy)
        self.pdf_clear.setEnabled(not busy and self._pdf_data is not None)

    def _generate(self):
        if self.client.busy or not self.settings.api_key:
            return
        if self.documentation and self._pdf_data is None:
            self.status.setText(self._t("Select a PDF datasheet first.", "Najpierw wybierz dokumentację PDF."))
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt and self.documentation:
            prompt = self._t("Analyse this datasheet: purpose, pins, limits and uncertainties. Propose a custom component if its pinout is clear.",
                             "Przeanalizuj dokumentację: przeznaczenie, piny, ograniczenia i niepewności. Zaproponuj własny element, jeśli układ pinów jest jednoznaczny.")
        try:
            body = request_body(prompt, self.context, self.settings.language,
                                self._pdf_data if self.documentation else None,
                                history=self.history, documentation=self.documentation)
        except (ValueError, TypeError, RecursionError):
            self.status.setText(self._t("Enter a request (up to 16000 characters). Project data may not exceed 2 MiB and PDF 10 MiB.",
                                       "Wpisz polecenie (do 16000 znaków). Dane projektu nie mogą przekraczać 2 MiB, a PDF 10 MiB."))
            return
        message = self._t(
            "Send your request, conversation and component-library data to Google Gemini? The chat also includes the current sheet. Provider fees and data policies apply.",
            "Wysłać polecenie, rozmowę i bibliotekę elementów do Google Gemini? Czat zawiera też bieżący arkusz. Obowiązują zasady danych i ewentualne opłaty operatora.")
        if self.documentation:
            message = self._t("Send your documentation-analysis request, its conversation and component library to Google Gemini? No sheet or assistant chat will be sent. Provider fees and data policies apply.",
                              "Wysłać polecenie analizy dokumentacji, jej rozmowę i bibliotekę elementów do Google Gemini? Arkusz ani czat asystenta nie zostaną wysłane. Obowiązują zasady danych i ewentualne opłaty operatora.")
        if self._pdf_data is not None:
            message += self._t("\nThe entire attached PDF will also be sent: ", "\nWysłany zostanie też cały dołączony PDF: ") + self._pdf_name
        if QMessageBox.question(self, self._t("Confirm data transfer", "Potwierdź wysłanie danych"), message,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._proposal = None
        self._applied = False
        self.apply_button.setEnabled(False)
        self.preview.clear()
        self._pending_prompt = prompt
        self._set_busy(True)
        try:
            # Stare zapisane ID nie blokuje użytkowników aktualizujących rc9.
            self.client.start(self.settings.api_key, "auto", body)
        except ValueError:
            self._set_busy(False)
            self.status.setText(self._t("Check your Gemini API key in Settings.", "Sprawdź klucz API Gemini w ustawieniach."))
            return

    def _completed(self, proposal):
        self._set_busy(False)
        if self.documentation and (proposal["components"] or proposal["wires"]):
            self._failed("invalid_response")
            return
        self._proposal = proposal
        self._applied = False
        count = sum(len(proposal[name]) for name in ("components", "wires", "custom_components"))
        if self._pending_prompt:
            self.history.extend([
                {"role": "user", "parts": [{"text": self._pending_prompt}]},
                {"role": "model", "parts": [{"text": json.dumps(proposal, ensure_ascii=False)}]},
            ])
            # Ograniczona historia nie powiela ogromnej biblioteki/PDF w każdym kroku.
            self.history = self.history[-12:]
            self._transcript += self._t("You: ", "Ty: ") + self._pending_prompt + "\n\n"
        self._transcript += "Gemini: " + proposal["summary"] + "\n\n"
        self.summary.setPlainText(self._transcript + self._t(
            f"\n\nProposal: {len(proposal['components'])} components, {len(proposal['wires'])} wires, {len(proposal['custom_components'])} custom definitions.",
            f"\n\nPropozycja: {len(proposal['components'])} elementów, {len(proposal['wires'])} przewodów, {len(proposal['custom_components'])} własnych definicji."))
        self.preview.setPlainText(json.dumps(proposal, ensure_ascii=False, indent=2))
        self.apply_button.setEnabled(count > 0)
        self.tabs.setCurrentIndex(0)
        self.prompt.clear()
        self._pending_prompt = ""
        self.status.setText(self._t("Click Apply proposal to add the proposed objects. Nothing has been changed yet.", "Kliknij Zastosuj propozycję, aby dodać proponowane obiekty. Niczego jeszcze nie zmieniono.") if count else
                            self._t("Answer received. You can ask a follow-up question.", "Odpowiedź otrzymana. Możesz zadać kolejne pytanie."))

    def _failed(self, code):
        self._set_busy(False)
        errors = {
            "http_400": ("Request rejected. Check model support and PDF format.", "Odrzucono żądanie. Sprawdź obsługę modelu i format PDF."),
            "http_401": ("API authentication failed. Check your key.", "Błąd uwierzytelnienia API. Sprawdź klucz."),
            "http_403": ("Access denied. Check the API key and project permissions.", "Brak dostępu. Sprawdź klucz API i uprawnienia projektu."),
            "http_404": ("The detected model is unavailable. Try again to refresh the model list.", "Wykryty model jest niedostępny. Spróbuj ponownie, aby odświeżyć listę modeli."),
            "no_model": ("No supported Gemini Flash model was returned for this API key.", "API nie zwróciło obsługiwanego modelu Gemini Flash dla tego klucza."),
            "http_429": ("Gemini quota/rate limit reached. Check your Google account limits.", "Osiągnięto limit Gemini. Sprawdź limity konta Google."),
            "http_500": ("Google Gemini returned a server error. Try again shortly; the project is unchanged.", "Serwer Google Gemini zwrócił błąd. Spróbuj za chwilę; projekt pozostał bez zmian."),
            "http_503": ("Google Gemini is temporarily unavailable or overloaded. Try again shortly; no changes were applied.", "Google Gemini jest chwilowo niedostępne lub przeciążone. Spróbuj za chwilę; nie zastosowano zmian."),
            "timeout": ("Request timed out after 120 seconds.", "Przekroczono limit 120 sekund oczekiwania."),
            "network": ("Network/TLS error. Check your connection and system clock.", "Błąd sieci/TLS. Sprawdź połączenie i zegar systemowy."),
            "blocked": ("Gemini returned no answer or blocked the request.", "Gemini nie zwróciło odpowiedzi lub zablokowało żądanie."),
            "incomplete": ("Response was incomplete. Ask for a smaller circuit.", "Odpowiedź jest niepełna. Poproś o mniejszy układ."),
            "invalid_response": ("Response failed validation; the project was not changed.", "Odpowiedź nie przeszła walidacji; projekt pozostał bez zmian."),
            "response_too_large": ("Response exceeded the size limit.", "Odpowiedź przekroczyła limit rozmiaru."),
        }
        texts = errors.get(code, ("Gemini service error. Try again later.", "Błąd usługi Gemini. Spróbuj ponownie później."))
        self.status.setText(self._t(*texts))

    def _cancelled(self):
        self._set_busy(False)
        self.status.setText(self._t("Request cancelled. The project was not changed.", "Anulowano żądanie. Projekt pozostał bez zmian."))

    def _apply(self):
        if self._proposal is None or self._applied:
            return
        try:
            proposal = validate_proposal(deepcopy(self._proposal))
            payload = {key: proposal[key] for key in ("components", "wires", "custom_components")}
            self.apply_button.setEnabled(False)
            self.on_apply(payload)
        except (ValueError, KeyError, TypeError, RuntimeError):
            self.status.setText(self._t("The proposal could not be applied. Check library IDs and pin references.",
                                       "Nie można zastosować propozycji. Sprawdź ID biblioteki i odwołania do pinów."))
            self.apply_button.setEnabled(True)
            return
        self._applied = True
        self.status.setText(self._t("Applied. You can undo these changes in the editor.", "Zastosowano. Zmiany możesz cofnąć w edytorze."))
        # Po zastosowaniu zamykamy dialog: kontekst starego arkusza nie służy
        # ponownemu generowaniu, a dwa kliknięcia nie dodadzą układu dwukrotnie.
        self.accept()

    def done(self, result):
        self.client.cancel()
        super().done(result)
