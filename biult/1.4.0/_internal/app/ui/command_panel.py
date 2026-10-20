"""AI conversation and editor terminal share a transactional proposal."""
from copy import deepcopy
from html import escape
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTabWidget, QMessageBox,QSplitter,QComboBox
from app.core.editor_commands import CommandSession
from app.services.assistant_client import AssistantClient
from app.ui.ai_preview import AiPreview

RUN_STARTUP_EXERCISES = True


class CommandPanel(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.session = None
        self.history = []
        self.busy = False
        self.context = None
        self.simulation_report = None
        self.curriculum=None; self.pending_prompt=""
        self.last_request=None; self.request_snapshot=None; self.retry_snapshot=None
        self._phase=None
        self._response_cancelled=False
        self.planner_questions_asked=False
        self.clarification_plan=None; self.clarification_request=''
        layout = QVBoxLayout(self)
        self.status = QLabel(self.t("Ready to answer.", "Gotowy do odpowiedzi."))
        self.status.setWordWrap(True)
        self.status.linkActivated.connect(lambda _:self.show_error_info())
        self.last_error=''
        layout.addWidget(self.status)
        self.splitter=QSplitter(Qt.Orientation.Vertical); layout.addWidget(self.splitter,1)
        self.tabs = QTabWidget(); self.splitter.addWidget(self.tabs)
        ai = QWidget(); ai_layout = QVBoxLayout(ai)
        from app.ui.ai_chat import Conversation
        self.chat = Conversation(); ai_layout.addWidget(self.chat,1)
        self.prompt = QPlainTextEdit(); self.prompt.setMaximumHeight(90); ai_layout.addWidget(self.prompt)
        self.prompt.setPlaceholderText(self.t('Ask a question…','Zadaj pytanie…'))
        first_row=QHBoxLayout(); ai_layout.addLayout(first_row)
        self.request_mode=QComboBox()
        for label,key in ((self.t('Automatic','Automatycznie'),'auto'),(self.t('Question / explanation','Pytanie / wyjaśnienie'),'explain'),(self.t('Draw / edit','Rysowanie / edycja'),'draw')): self.request_mode.addItem(label,key)
        self.send = QPushButton(self.t("Send", "Wyślij")); self.send.clicked.connect(self.send_request)
        self.stop_response=QPushButton(self.t('Stop response','Zatrzymaj odpowiedź')); self.stop_response.clicked.connect(self.cancel_request)
        first_row.addWidget(self.send,1); first_row.addWidget(self.stop_response,1)
        self.regenerate=QPushButton(self.t('Generate again','Wygeneruj odpowiedź ponownie'))
        self.regenerate.clicked.connect(self.regenerate_response)
        second_row=QHBoxLayout(); ai_layout.addLayout(second_row)
        self.edit_prompt=QPushButton(self.t('Edit last message','Edytuj ostatnie polecenie')); self.edit_prompt.clicked.connect(self.edit_last_prompt)
        second_row.addWidget(self.edit_prompt,1); second_row.addWidget(self.regenerate,1)
        self.network_note=QLabel(); self.network_note.setWordWrap(True); ai_layout.addWidget(self.network_note)
        self.edit_commands=QPushButton(self.t('Edit circuit commands','Edytuj komendy schematu')); self.edit_commands.clicked.connect(lambda:self.tabs.setCurrentIndex(1))
        self.tabs.addTab(ai, self.t("AI assistant", "Asystent AI"))
        terminal = QWidget(); terminal_layout = QVBoxLayout(terminal)
        self.terminal_hint = QLabel()
        self.terminal_hint.setWordWrap(True); terminal_layout.addWidget(self.terminal_hint)
        self.commands = QPlainTextEdit(); self.commands.setPlaceholderText('ADD_COMPONENT type=<library_id> id=R1 x=200 y=200\nSET_PROPERTY id=R1 property=value value=330')
        terminal_layout.addWidget(self.commands)
        self.terminal_output = QPlainTextEdit(); self.terminal_output.setReadOnly(True)
        self.terminal_output.setMaximumHeight(150); terminal_layout.addWidget(self.terminal_output)
        self.execute = QPushButton(self.t("Execute on proposal", "Wykonaj na propozycji")); self.execute.clicked.connect(self.execute_commands); terminal_layout.addWidget(self.execute)
        self.tabs.addTab(terminal, self.t("Editor terminal", "Terminal edytora"))
        # Drawing and the command console remain implemented for later reuse,
        # but this release exposes the assistant as a question/answer tool.
        self.tabs.setTabVisible(1, False)
        self.tabs.tabBar().hide()
        # Rysowanie/propozycje i ich raporty są wycofane z interfejsu; klasy
        # raportów pozostają w kodzie do ewentualnego ponownego użycia.
        self.simulation_output = QPlainTextEdit(); self.simulation_output.setReadOnly(True)
        self.plan_output=QPlainTextEdit(); self.plan_output.setReadOnly(True)
        self.layout_output=QPlainTextEdit(); self.layout_output.setReadOnly(True)
        self.readability_button=QPushButton(self.t('Improve readability','Popraw czytelność'))
        self.readability_button.clicked.connect(self.request_readability)
        legacy_actions=QHBoxLayout(); ai_layout.addLayout(legacy_actions)
        for widget in (self.request_mode,self.edit_commands,self.readability_button): legacy_actions.addWidget(widget)
        preview_buttons = QHBoxLayout(); layout.addLayout(preview_buttons)
        self.inspect_button = QPushButton(); self.inspect_button.clicked.connect(lambda: self.preview.inspect(self.editor.settings.language))
        self.test_button = QPushButton(); self.test_button.clicked.connect(self.test_proposal)
        preview_buttons.addWidget(self.inspect_button); preview_buttons.addWidget(self.test_button)
        self.inspect_button.hide()
        self.preview = AiPreview(); self.splitter.addWidget(self.preview); self.splitter.setSizes([450,220])
        self.preview.hide()
        for widget in (self.request_mode, self.edit_commands, self.readability_button,
                       self.inspect_button, self.test_button): widget.hide()
        self.preview.projectEdited.connect(self.preview_edited)
        buttons = QHBoxLayout(); layout.addLayout(buttons)
        self.accept_button = QPushButton(self.t("Accept", "Akceptuj")); self.accept_button.clicked.connect(self.accept)
        self.reject_button = QPushButton(self.t("Reject", "Odrzuć")); self.reject_button.clicked.connect(self.reject)
        self.cancel_button = QPushButton(self.t("Cancel request", "Anuluj żądanie")); self.cancel_button.clicked.connect(self.cancel_request)
        for button in (self.accept_button, self.reject_button, self.cancel_button): buttons.addWidget(button)
        self.accept_button.hide(); self.reject_button.hide(); self.cancel_button.hide()
        self.client = AssistantClient(self)
        self.planner=AssistantClient(self)
        self.planner.completed.connect(self.plan_completed)
        self.planner.failed.connect(self.failed)
        self.planner.cancelled.connect(lambda:self.set_busy(False))
        self.client.completed.connect(self.completed)
        self.client.failed.connect(self.failed)
        self.client.cancelled.connect(lambda: self.set_busy(False))
        self.accept_button.setEnabled(False)
        self.set_busy(False)
        self.translate()

    def t(self, en, pl): return self.editor.t(en, pl)

    def update_context_label(self):
        # A tab change must not silently retarget an existing proposal.
        if not self.session:
            self.status.setText(self.t("Ready to answer.", "Gotowy do odpowiedzi."))
        if self.editor.settings.ai_provider == "none":
            self.status.setText(self.t("AI is disabled in Settings.", "AI jest wyłączone w ustawieniach."))
        elif not self.provider_key():
            self.status.setText(self.t('Choose an installed local model in Settings.','Wybierz zainstalowany model lokalny w Ustawieniach.') if self.editor.settings.ai_provider=='local' else self.t("Missing API key. Add it in Options → Settings, under AI provider.", "Brak klucza API. Dodaj go w Opcje → Ustawienia, pod dostawcą AI."))

    def provider_key(self):
        settings = self.editor.settings
        if settings.ai_provider=='local': return 'local' if settings.local_ai_model.strip() else ''
        return settings.openai_api_key if settings.ai_provider == "openai" else settings.api_key if settings.ai_provider == "gemini" else ""

    def prepare(self):
        if self.session is None:
            self.editor._sync_positions()
            self.session = CommandSession(self.editor.project, self.editor.tabs.currentIndex())
            self.context = deepcopy(self.editor._ai_context())

    def working_context(self):
        context = deepcopy(self.context)
        from dataclasses import asdict
        context["sheet"] = asdict(self.session.working.sheets[self.session.sheet_index])
        context["simulation_report"] = self.simulation_report
        from app.services.layout_review import review
        context['layout_report']=review(self.session.working,self.session.sheet_index)
        return context

    def set_busy(self, value):
        self.busy = value
        for widget in (self.send, self.execute, self.reject_button): widget.setEnabled(not value)
        self.send.setEnabled(not value and self.editor.settings.ai_provider != "none")
        self.regenerate.setEnabled(not value and self.last_request is not None and self.session is not None)
        self.inspect_button.setEnabled(not value and not self.preview.image.isNull())
        self.preview.setEnabled(not value)
        self.test_button.setEnabled(not value and self.session is not None)
        self.cancel_button.setEnabled(value)
        self.stop_response.setEnabled(value)
        self.edit_prompt.setEnabled(not value and self.last_request is not None)
        self.edit_commands.setEnabled(not value and self.session is not None)
        self.request_mode.setEnabled(not value)
        self.readability_button.setEnabled(not value and self.session is not None)
        self.accept_button.setEnabled(not value and self.session is not None and self.session.working.to_dict() != self.session.base)

    def execute_commands(self):
        try:
            from app.core.editor_commands import FIELDS, parse_commands
            commands = parse_commands(self.commands.toPlainText())
            if any(name == "HELP" for name, _ in commands):
                lines = [self.t("One command per line. Changes stay in the proposal until Accept.", "Jedna komenda na linię. Zmiany zostają w propozycji do akceptacji.")]
                for name, (_, required) in FIELDS.items():
                    lines.append(name + " " + " ".join(key+"=..." for key in sorted(required)))
                lines.append(self.t("Pins use zero-based indices. Library IDs:", "Piny używają indeksów od zera. ID biblioteki:"))
                from app.libraries.built_in import AVAILABLE_ITEMS, item_name
                lines.extend(item.id + " : " + item_name(item, self.editor.settings.language) + "\n  " +
                    ", ".join(f"{index}={pin.name} [{pin.number}]" for index, pin in enumerate(item.pins)) for item in AVAILABLE_ITEMS)
                self.terminal_output.setPlainText("\n".join(lines))
                if all(name == "HELP" for name, _ in commands): return
            self.prepare()
            self.session.execute(self.commands.toPlainText())
            self.show_proposal()
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
            self.failed(str(error))

    def show_proposal(self):
        self.preview.set_project(self.session.working, self.session.sheet_index, self.editor.settings)
        self.status.setText(self.t("Answer prepared.", "Odpowiedź przygotowana."))
        self.set_busy(False)
        self.test_proposal()

    def preview_edited(self,project):
        if self.busy or self.session is None: return
        self.session.working=project
        self.request_snapshot=None; self.retry_snapshot=None; self.last_request=None
        self.history.append({'role':'editor','text':self.t('The user moved/rotated parts in the working preview. Use its current geometry.',
            'Użytkownik przesunął/obrócił elementy w podglądzie roboczym. Używaj jego aktualnej geometrii.')})
        self.show_proposal()

    def request_readability(self):
        if self.busy or self.session is None: return
        self.retry_snapshot=None
        self.request_mode.setCurrentIndex(self.request_mode.findData('draw'))
        self.clarification_plan=None; self.clarification_request=''
        self.prompt.setPlainText(self.t(
            'Improve only the readability of the current working schematic. Preserve every electrical connection and component parameter. Arrange functional blocks from supply to outputs, align related branches, leave space for labels and routing, minimize crossings and long diagonal wires. Use the layout_report to fix overlaps and obstructed labels. Modify the existing proposal, do not duplicate it. Explain remaining visual limitations.',
            'Popraw wyłącznie czytelność bieżącego schematu roboczego. Zachowaj wszystkie połączenia elektryczne i parametry elementów. Ułóż bloki od zasilania do wyjść, wyrównaj powiązane gałęzie, zostaw miejsce na opisy i prowadzenie przewodów, ogranicz skrzyżowania oraz długie ukośne przewody. Użyj layout_report, aby usunąć nakładanie i zasłanianie opisów. Popraw istniejącą propozycję, nie twórz duplikatu. Wyjaśnij pozostałe ograniczenia wizualne.'))
        self.tabs.setCurrentIndex(0); self.prompt.setFocus()
        self.status.setText(self.t('Readability request ready. Review it and press Send; this uses normal AI requests and may incur API costs.',
            'Polecenie poprawy czytelności gotowe. Sprawdź je i kliknij Wyślij; to zwykłe zapytania AI i mogą powodować koszty API.'))

    def test_proposal(self):
        if self.session is None or self.busy: return
        from app.services.layout_review import review,describe
        visual=review(self.session.working,self.session.sheet_index)
        self.layout_output.setPlainText(self.t('Local readability check (independent of simulation):','Lokalna kontrola czytelności (niezależna od symulacji):')+'\n'+
            ('\n'.join(describe(issue,self.editor.settings.language) for issue in visual['issues']) or self.t('No detected geometric issues; inspect the preview too.','Nie wykryto problemów geometrycznych; oceń również podgląd.')))
        from app.services.proposal_simulation import simulate_proposal
        self.simulation_report = simulate_proposal(self.session.working, self.session.sheet_index, self.editor.settings.language)
        report = self.simulation_report
        statuses = {"sampled": self.t("Sampled, no fault in the tested interval", "Próbka bez awarii w badanym przedziale"),
                    "fault": self.t("Fault detected", "Wykryto awarię"), "blocked": self.t("Test blocked", "Test zablokowany"),
                    "not_tested": self.t("Not tested", "Nie przetestowano")}
        lines = [self.t("Short electrical test only; not a guarantee of correct or safe operation.", "Tylko krótki test elektryczny; nie gwarantuje poprawnego ani bezpiecznego działania."),
                 statuses[report["status"]], f'{self.t("Simulated time", "Czas symulacji")}: {report["seconds"]:.6g} s; {self.t("steps", "kroki")}: {report["steps"]}']
        if report.get("reason"): lines.append(report["reason"])
        for group in ("faults", "warnings"): lines.extend(report[group].values())
        references = {c.id: c.reference for c in self.session.working.sheets[self.session.sheet_index].components}
        lines.append(self.t("Peak sampled currents:", "Największe zmierzone prądy:"))
        lines.extend(f'{references.get(cid, cid)}: {value:.6g} A' for cid, value in report["peak_current_A"].items())
        self.simulation_output.setPlainText("\n".join(lines))
        if visual['issues']:
            self.status.setText(self.t('Working proposal: ','Propozycja robocza: ')+str(len(visual['issues']))+
                self.t(' readability warnings. See Readability report and enlarged preview.',' uwag do czytelności. Sprawdź Raport czytelności i powiększony podgląd.'))

    def send_request(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt or self.busy: return
        settings = self.editor.settings
        from app.services.assistant_intent import explanation_only
        mode=self.request_mode.currentData()
        # Keep the old planner/drawing pipeline in source, but do not expose or
        # invoke it in this release. The assistant only answers questions.
        explain=True
        from app.services.power_recipe import matches,commands,summary
        candidate_sheet=self.session.working.sheets[self.session.sheet_index] if self.session else self.editor.project.sheets[self.editor.tabs.currentIndex()]
        if not explain and matches(prompt) and not candidate_sheet.components:
            message=summary(settings.language)+self.t('\nUse the built-in reference on an A3 sheet without an API request?', '\nUżyć wbudowanego wzorca na arkuszu A3, bez zapytania API?')
            if QMessageBox.question(self,'ElectroSchem',message)==QMessageBox.StandardButton.Yes:
                try:
                    self.prepare()
                    sheet=self.session.working.sheets[self.session.sheet_index]
                    sheet.paper_size='A3'; sheet.orientation='landscape'
                    self.request_snapshot=None; self._response_cancelled=False
                    self.last_request=None; self.retry_snapshot=None
                    self.clarification_plan=None; self.clarification_request=''
                    self.plan_output.setPlainText(summary(settings.language))
                    self.history.append({'role':'user','text':prompt})
                    self.completed({'commands':commands(),'summary':summary(settings.language)})
                    self.prompt.clear()
                except (ValueError,TypeError,OSError) as error: self.failed(str(error))
                return
        if settings.ai_provider == "none":
            self.failed(self.t("AI is disabled in Settings.", "AI jest wyłączone w ustawieniach.")); return
        key = self.provider_key()
        if not key:
            self.failed(self.t('Configure an installed local model in Settings.','Wybierz zainstalowany model lokalny w ustawieniach.') if settings.ai_provider=='local' else self.t("Configure an API key in Settings first.", "Najpierw ustaw klucz API w ustawieniach.")); return
        if not settings.ai_chat_consent and not settings.ai_request_consents.get(settings.ai_provider):
            provider = "lokalny serwer AI" if settings.ai_provider=='local' else "OpenAI" if settings.ai_provider == "openai" else "Google Gemini"
            consent=self.t('Send the conversation, working sheet and library to your local server? ElectroSchem sends no requests to a cloud provider. Server configuration is your responsibility.','Wysłać rozmowę, roboczy arkusz i bibliotekę do lokalnego serwera? ElectroSchem nie wysyła wtedy żądań do dostawcy w chmurze. Konfiguracja serwera zależy od Ciebie.') if settings.ai_provider=='local' else self.t(
                f"Send this conversation, working sheet and component library to {provider}? API fees may apply. No code files or API keys are included in project context.",
                f"Wysłać rozmowę, roboczy arkusz i bibliotekę elementów do {provider}? API może naliczać opłaty. Pliki kodu i klucze API nie są częścią kontekstu projektu.")
            choice = QMessageBox.question(self, "ElectroSchem AI",consent)
            if choice != QMessageBox.StandardButton.Yes: return
            from app.core.settings import remember_chat_consent
            try: remember_chat_consent(settings)
            except OSError as error: self.failed(str(error)); return
        try:
            from app.services.assistant_curriculum import read_profile,Curriculum
            completed=20 if explain or not RUN_STARTUP_EXERCISES else len(read_profile(settings)["exercises"])
            from app.ui.ai_cost_dialog import confirm_requests
            if not settings.ai_request_consents.get(settings.ai_provider):
                if not confirm_requests(self,settings,20-completed if completed<20 else 1,completed<20): return
                from app.core.settings import remember_request_consent
                remember_request_consent(settings)
            if completed<20:
                self.pending_prompt=prompt; self.set_busy(True)
                self.curriculum=Curriculum(settings,self)
                self.curriculum.progress.connect(lambda i,n,name:self.status.setText(self.t("Practice task ","Zadanie startowe ")+f"{i}/{n}: {name}"))
                self.curriculum.failed.connect(self.course_failed)
                self.curriculum.completed.connect(self.course_completed)
                self.curriculum.start(); return
            self.prepare()
            if self.clarification_plan is None: self.planner_questions_asked=False
            snapshot=deepcopy(self.retry_snapshot) if self.retry_snapshot else {'working':self.session.working.to_dict(),'history':deepcopy(self.history),'report':deepcopy(self.simulation_report),'prompt':prompt}
            snapshot['prompt']=prompt
            snapshot['explanation_only']=explain
            context = self.working_context()
            context['request_mode']='question_and_answer' if explain else 'draw_or_edit'
            context['planner_questions_already_asked']=self.planner_questions_asked
            context['sheet']=deepcopy(snapshot['working']['sheets'][self.session.sheet_index])
            context['simulation_report']=deepcopy(snapshot['report'])
            # Source paths are private, even in the command-based sheet context.
            for component in context["sheet"]["components"]:
                component["properties"] = {k: v for k, v in component["properties"].items()
                    if k not in {"sim_source", "sim_code_folder", "sim_firmware", "sim_bootrom"}}
            self.set_busy(True)
            self.request_snapshot=snapshot; self.last_request=deepcopy(snapshot); self.retry_snapshot=None
            if self.clarification_plan is not None:
                snapshot['prompt']=self.clarification_request+'\n'+self.t('User clarification: ','Doprecyzowanie użytkownika: ')+prompt
                self.last_request=deepcopy(snapshot)
            self.request_context=context
            self._response_cancelled=False
            self._phase='explain' if explain else 'plan'
            if explain:
                self.client.start(settings,snapshot['prompt']+self.t('\nAnswer the user directly and helpfully. Return commands="" and put the answer in summary.',
                    '\nOdpowiedz użytkownikowi bezpośrednio i pomocnie. Zwróć commands="", a odpowiedź umieść w summary.'),context,snapshot['history'])
            else: self.planner.start(settings, snapshot['prompt'], context, snapshot['history'],purpose='plan')
            self.history=deepcopy(snapshot['history'])+[{'role':'user','text':prompt}]
            self.chat.appendPlainText(self.t("You: ", "Ty: ") + prompt)
            self.prompt.clear()
            self.status.setText(self.t('Answering…','Odpowiadam…'))
            if self.clarification_plan is not None:
                self.clarification_plan=None
        except (ValueError, TypeError, OSError) as error:
            self.failed(str(error))

    def plan_completed(self,plan):
        if not self.busy or self.session is None or self._phase!='plan': return
        from app.services.assistant_plan import decode_plan
        import json
        try:
            plan=decode_plan(json.dumps(plan))
            from app.services.power_requirements import validate_plan
            validate_plan(plan,self.request_snapshot['prompt'])
            lines=[plan['goal']]
            for task in plan['tasks']:
                lines.append(f"{task['id']}. {task['task']}\n"+self.t('Check: ','Warunek: ')+task['check'])
            lines.extend(plan['questions']); self.plan_output.setPlainText('\n\n'.join(lines))
            if plan['questions']:
                if self.planner_questions_asked:
                    # Never silently discard unresolved electrical requirements.
                    raise ValueError(self.t('Essential requirements remain unresolved. Add explicit answers to continue.','Istotne wymagania nadal nie są ustalone. Podaj konkretne odpowiedzi, aby kontynuować.'))
                else:
                    self.planner_questions_asked=True
                    self.clarification_plan=deepcopy(plan); self.clarification_request=self.request_snapshot['prompt']
            if plan['questions']:
                self._phase=None
                self.set_busy(False)
                self.chat.appendPlainText(self.t('Planner asks: ','Planista pyta: ')+'\n'.join(plan['questions']))
                self.history.append({'role':'assistant','text':'\n'.join(plan['questions'])})
                self.status.setText(self.t('Please answer the follow-up questions.','Odpowiedz na pytania doprecyzowujące.')); return
            context=deepcopy(self.request_context); context['task_plan']=plan
            self.status.setText(self.t('Answering…','Odpowiadam…'))
            self._phase='draw'
            self.client.start(self.editor.settings,self.request_snapshot['prompt'],context,self.request_snapshot['history'])
        except (ValueError,TypeError,KeyError,OSError) as error: self.failed('Invalid plan: '+str(error))

    def completed(self, answer):
        if self._response_cancelled: return
        try:
            if self.request_snapshot and self.request_snapshot.get('explanation_only'):
                if answer['commands'].strip(): raise ValueError(self.t('Unexpected response format. Please try again.',
                    'Nieoczekiwany format odpowiedzi. Spróbuj ponownie.'))
                self.history.append({'role':'assistant','text':answer['summary']})
                self.chat.appendPlainText('AI: '+answer['summary']); self._phase=None; self.set_busy(False)
                self.status.setText(self.t('Answer ready.','Odpowiedź gotowa.'))
                return
            if self.request_snapshot:
                from app.core.models import Project
                from app.core.editor_commands import execute_batch
                self.session.working=execute_batch(Project.from_dict(self.request_snapshot['working']),self.session.sheet_index,answer['commands'])
            else: self.session.execute(answer["commands"])
            self.commands.setPlainText(answer["commands"])
            self.history.append({"role": "assistant", "text": answer["summary"]})
            self.chat.appendPlainText("AI: " + answer["summary"])
            self.show_proposal()
            self.planner_questions_asked=False
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
            if (not (self.request_snapshot and self.request_snapshot.get('explanation_only'))
                    and self.client.repair_last_response(getattr(self.client, '_raw_answer', None), error)):
                self.status.setText(self.t('Retrying the response once…', 'Ponawiam odpowiedź (jedna próba)…'))
                return
            self.failed(self.t("The response could not be completed: ", "Nie udało się przygotować odpowiedzi: ") + str(error))

    def regenerate_response(self):
        if self.busy or self.last_request is None or self.session is None: return
        self.retry_snapshot=deepcopy(self.last_request)
        self.prompt.setPlainText(self.last_request['prompt'])
        self.send_request()
        self.retry_snapshot=None

    def course_completed(self):
        self.curriculum.deleteLater(); self.curriculum=None
        self.set_busy(False); self.prompt.setPlainText(self.pending_prompt); self.pending_prompt=""
        self.send_request()

    def edit_last_prompt(self):
        if self.busy or self.last_request is None: return
        self.retry_snapshot=deepcopy(self.last_request)
        self.prompt.setPlainText(self.last_request['prompt']); self.prompt.setFocus()
        self.planner_questions_asked=False
        self.clarification_plan=None; self.clarification_request=''

    def course_failed(self,message):
        self.curriculum.deleteLater(); self.curriculum=None; self.pending_prompt=""
        if self.editor.settings.language=="pl":
            errors={"Exercise circuit failed the electrical probe":"Układ z zadania nie przeszedł testu elektrycznego", "Unexpected load current":"Prąd obciążenia nie odpowiada zadaniu", "LED is not lit":"LED nie świeci", "Wrong logic output":"Nieprawidłowy wynik logiczny"}
            message=errors.get(message,message)
            if message.startswith("Wrong logic output:"):
                message="Nieprawidłowa tabela prawdy. Sprawdź typ bramki i połączenia jej wejść oraz wyjścia O1."
            elif message.startswith("Exercise requires logic input "):
                message="Zadanie wymaga wejścia logicznego "+message.removeprefix("Exercise requires logic input ")
        self.failed(self.t("Practice stopped; verified tasks are saved. ","Ćwiczenia zatrzymane; zaliczone zadania są zapisane. ")+message)

    def failed(self, message):
        self._phase=None
        if self.editor.settings.ai_provider=='local':
            from app.services.local_ai import localized_error
            message=localized_error(message,self.editor.settings.language)
        self.set_busy(False)
        self.last_error=message
        self.status.setText('<a href="error">'+escape(self.t("Error: ", "Błąd: ") + message)+'</a>')
        self.status.setToolTip(self.t('Click for an explanation','Kliknij, aby wyświetlić objaśnienie'))
        self.history.append({"role": "editor", "text": message})

    def show_error_info(self):
        if not self.last_error: return
        from app.services.ai_errors import explanation
        box=QMessageBox(self); box.setWindowTitle(self.t('AI error information','Informator błędów AI'))
        box.setText(self.last_error); box.setInformativeText(explanation(self.last_error,self.editor.settings.ai_provider,self.editor.settings.language))
        copy=box.addButton(self.t('Copy error','Kopiuj błąd'),QMessageBox.ButtonRole.ActionRole)
        copy.clicked.connect(self.copy_error)
        box.setStandardButtons(QMessageBox.StandardButton.Close); box.exec()
    def copy_error(self):
        from PySide6.QtWidgets import QApplication
        if self.last_error: QApplication.clipboard().setText(self.last_error)

    def cancel_request(self):
        was_busy=self.busy
        self._response_cancelled=True
        self._phase=None
        if self.curriculum:
            self.curriculum.cancel(); self.curriculum.deleteLater(); self.curriculum=None; self.pending_prompt=""
        self.planner.cancel(); self.client.cancel(); self.set_busy(False)
        if was_busy: self.status.setText(self.t('Response stopped.','Odpowiedź zatrzymana.'))

    def accept(self):
        if self.session is None or self.busy: return
        try:
            self.editor._sync_positions()
            candidate = self.session.accept(self.editor.project)
        except ValueError as error:
            self.failed(str(error)); return
        index = self.session.sheet_index
        self.editor.project = candidate
        self.editor._rebuild_tabs(selected=index)
        self.editor.record_history()
        self.session = None; self.context = None; self.history = []
        self.last_request=None; self.request_snapshot=None; self.retry_snapshot=None
        self.simulation_report = None
        self.set_busy(False)
        self.status.setText(self.t("Applied.", "Zastosowano."))

    def reject(self):
        if self.busy: return
        self.session = None; self.context = None; self.history = []
        self.last_request=None; self.request_snapshot=None; self.retry_snapshot=None
        self.planner_questions_asked=False
        self.clarification_plan=None; self.clarification_request=''
        self.simulation_report = None; self.simulation_output.clear()
        self.plan_output.clear()
        self.layout_output.clear()
        self.preview.image = self.preview.image.__class__(); self.preview.update()
        self.set_busy(False)
        self.status.setText(self.t("Dismissed.", "Odrzucono."))

    def reset(self):
        self.cancel_request()
        self.reject()
        self.chat.clear(); self.commands.clear(); self.terminal_output.clear()

    def translate(self):
        self.edit_commands.setText(self.t('Edit circuit commands','Edytuj komendy schematu'))
        local=self.editor.settings.ai_provider=='local'
        self.network_note.setText(self.t('Local AI: a running local server/model is required.','AI lokalne: wymagany uruchomiony lokalny serwer/model.') if local else self.t('Cloud AI requires Internet. Remembered consent permits API requests that may incur costs; revoke it in AI Settings.','AI w chmurze wymaga internetu. Zapamiętana zgoda pozwala wysyłać zapytania API, które mogą kosztować; cofnij ją w ustawieniach AI.'))
        self.edit_prompt.setText(self.t('Edit last message','Edytuj ostatnie polecenie')); self.stop_response.setText(self.t('Stop response','Zatrzymaj odpowiedź'))
        self.preview.language = self.editor.settings.language
        self.preview.setToolTip(self.t("Click to inspect and zoom", "Kliknij, aby powiększyć podgląd"))
        self.terminal_hint.setText(self.t("Editor commands only, no system shell. One command per line; quote values with spaces.", "Tylko komendy edytora, bez powłoki systemowej. Jedna komenda na linię; wartości ze spacjami w cudzysłowie."))
        self.tabs.setTabText(0, self.t("AI assistant", "Asystent AI"))
        self.tabs.setTabText(1, self.t("Editor terminal", "Terminal edytora"))
        self.readability_button.setText(self.t('Improve readability','Popraw czytelność'))
        for index,en,pl in ((0,'Automatic','Automatycznie'),(1,'Question / explanation','Pytanie / wyjaśnienie'),(2,'Draw / edit','Rysowanie / edycja')): self.request_mode.setItemText(index,self.t(en,pl))
        self.inspect_button.setText(self.t("Inspect / zoom", "Powiększ podgląd"))
        self.test_button.setText(self.t("Test in simulator", "Test w symulatorze"))
        for button, en, pl in ((self.send, "Send", "Wyślij"), (self.execute, "Execute on proposal", "Wykonaj na propozycji"),
            (self.regenerate,'Generate again','Wygeneruj odpowiedź ponownie'),
            (self.accept_button, "Accept", "Akceptuj"), (self.reject_button, "Reject", "Odrzuć"), (self.cancel_button, "Cancel request", "Anuluj żądanie")):
            button.setText(self.t(en, pl))
        self.set_busy(self.busy)
        self.update_context_label()
