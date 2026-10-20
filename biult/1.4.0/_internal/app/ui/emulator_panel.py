"""Firmware i kod są oddzielnymi plikami: edytor nie jest kompilatorem.

Przypisanie zapisuje ścieżki w ELS, ale plik nigdy nie uruchamia się przy
otwieraniu projektu. Emulator startuje dopiero po kliknięciu przez użytkownika.
"""
from pathlib import Path
import subprocess
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,
    QFileDialog,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView)
from app.libraries.built_in import get_definition, AVAILABLE_ITEMS, item_name
from app.libraries.emulator_catalog import profile_for
from app.simulation.emulator_process import EmulatorProcess
from app.core.settings import file_dialog_directory, default_editor


class EmulatorPanel(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor, self.pl = editor, editor.settings.language == "pl"
        self.runner, self.active, self.loaded = EmulatorProcess(self), False, False
        self.script = None
        from app.simulation.arduino_compile import ArduinoCompiler
        self.compiler=ArduinoCompiler(self)
        self.compiler.finished.connect(self.compiled)
        self.compiler.failed.connect(self.failure)
        self.compiler.progress.connect(self.output_compile)
        self.compiling_id=None
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.runner.result.connect(self.result)
        self.runner.failed.connect(self.failure)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        note = QLabel(self.t("Firmware is compiled externally. Load HEX for Uno/Nano or UF2 for Pico. This panel tests firmware independently; the Circuit tab couples assigned firmware to GPIO. Arduino requires 5V/GND; Pico requires VSYS/GND. Unsupported pins stop the circuit.",
            "Firmware kompilujesz zewnętrznie: HEX dla Uno/Nano lub UF2 dla Pico. Ten panel testuje sam firmware; zakładka Obwód łączy przypisany firmware z GPIO. Arduino wymaga 5V/GND, Pico VSYS/GND. Nieobsługiwane piny blokują obwód."))
        note.setWordWrap(True)
        note.setText(self.t("Uno/Nano .ino sketches compile with Arduino CLI and execute as AVR firmware. Python supports simulated GPIO, RPLCD, smbus, functions and local helper modules, not a complete OS. Reload the Circuit tab to connect LCD and other devices; this panel tests the board alone.",
            "Szkice .ino Uno/Nano kompiluje Arduino CLI i wykonuje emulator AVR. Python obsługuje symulowane GPIO, RPLCD, smbus, funkcje i lokalne moduły pomocnicze, nie cały system. Pobierz obwód z edytora, aby podłączyć LCD i inne urządzenia; ta zakładka testuje samą płytkę."))
        layout.addWidget(note)
        bar = QHBoxLayout()
        self.board = QComboBox()
        bar.addWidget(self.board,1)
        refresh = QPushButton(self.t("Refresh boards", "Odśwież płytki"))
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)
        bar = QHBoxLayout()
        self.buttons=[]
        for en,pl,callback in (("Assign firmware…","Przypisz firmware…",self.assign_firmware),
                              ("Pico ROM…","ROM Pico…",self.assign_rom),
                              ("Link source…","Powiąż kod…",self.assign_source),
                              ("Edit source","Edytuj kod",self.edit_source),
                              ("Restart","Restart",self.load),
                              ("Start","Start",self.toggle)):
            button=QPushButton(self.t(en,pl));button.clicked.connect(callback);bar.addWidget(button)
            self.buttons.append(button)
        layout.addLayout(bar)
        from app.ui.live_language import LocalizedLog
        self.output = LocalizedLog(lambda: self.editor.settings.language)
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(150)
        layout.addWidget(self.output)
        entries = [d for d in AVAILABLE_ITEMS if profile_for(d)]
        table=QTableWidget(len(entries),3)
        table.setHorizontalHeaderLabels([self.t("Board","Płytka"),self.t("Engine","Silnik"),self.t("Limitations","Ograniczenia")])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        for row,d in enumerate(entries):
            p=profile_for(d)
            status=self.t("GPIO scripts + firmware: ","Skrypty GPIO + firmware: ") if p.ready else self.t("GPIO scripts only. Firmware/OS: ","Tylko skrypty GPIO. Firmware/system: ")
            for col,text in enumerate((item_name(d,"pl" if self.pl else "en"),p.engine,status+self.t(p.reason_en,p.reason_pl))):
                table.setItem(row,col,QTableWidgetItem(text))
        table.resizeRowsToContents()
        layout.addWidget(table)
        self.board.currentIndexChanged.connect(self.selection_changed)
        self.refresh()

    def t(self,en,pl):
        from app.ui.live_language import phrase
        return phrase(self,en,pl)

    def refresh_language(self):
        from app.ui.live_language import refresh
        refresh(self,self.editor.settings.language)

    def refresh(self):
        self.shutdown()
        self.board.clear()
        view=self.editor._current_view()
        if not view or not view._sheet:return
        for c in view._sheet.components:
            d=get_definition(c.library_id,self.editor.project.custom_components)
            if profile_for(d):self.board.addItem(f"{c.reference} — {item_name(d,'pl' if self.pl else 'en')}",c.id)
        self.selection_changed()

    def component(self):
        cid=self.board.currentData()
        return next((c for s in self.editor.project.sheets for c in s.components if c.id==cid),None)

    def selection_changed(self,*_):
        self.shutdown()
        c=self.component()
        for button in self.buttons:button.setEnabled(c is not None)
        if c:
            p=profile_for(get_definition(c.library_id))
            self.output.setPlainText(self.t(p.reason_en,p.reason_pl)+"\nFirmware: "+str(c.properties.get('sim_firmware','—'))+"\n"+self.t("Source: ","Kod: ")+str(c.properties.get('sim_source','—'))+"\nROM: "+str(c.properties.get('sim_bootrom','—')))
        else:
            self.output.setPlainText(self.t("Add a development board to the active schematic sheet, then click Refresh boards. See the support table below before choosing a board.",
                "Dodaj płytkę do aktywnego arkusza schematu, a następnie kliknij Odśwież płytki. Przed wyborem sprawdź tabelę obsługi poniżej."))

    def assign(self,key,filter):
        c=self.component()
        if not c:return
        filename,_=QFileDialog.getOpenFileName(self,self.t("Select file","Wybierz plik"),file_dialog_directory(self.editor.settings),filter)
        if filename:
            self.shutdown()
            c.properties[key]=str(Path(filename).resolve())
            if key == "sim_firmware": c.properties["sim_mode"]="firmware"
            if key == "sim_source": c.properties["sim_mode"]="arduino" if filename.lower().endswith(".ino") else "gpio"
            self.editor.record_history()
            self.selection_changed()
            self.output.appendPlainText(self.t("Use Reload from editor on the Circuit tab after changes.","Po zmianach użyj Pobierz z edytora w zakładce Obwód."))

    def assign_firmware(self):self.assign("sim_firmware","Firmware (*.hex *.uf2 *.elf *.bin);;All files (*)")
    def assign_source(self):self.assign("sim_source","Code (*.ino *.c *.cpp *.py *.h);;All files (*)")
    def assign_rom(self):
        c=self.component()
        if c and profile_for(get_definition(c.library_id)).engine == "rp2040js":
            self.assign("sim_bootrom","RP2040 boot ROM (*.bin)")

    def edit_source(self):
        c=self.component()
        if not c:return
        self.editor.edit_component_code(c)
        self.selection_changed()

    def load(self):
        self.shutdown()
        c=self.component()
        if not c:return
        profile=profile_for(get_definition(c.library_id))
        if c.properties.get("sim_mode")=="arduino" or Path(c.properties.get("sim_source","")).suffix.lower()==".ino":
            self.compiling_id=c.id
            self.output.setPlainText(self.t("Compiling Arduino sketch…","Kompilowanie szkicu Arduino…"))
            self.compiler.start(c,get_definition(c.library_id)); return
        if c.properties.get("sim_mode")=="gpio" or (c.properties.get("sim_source") and not c.properties.get("sim_firmware")):
            from app.simulation.python_board import PythonBoard
            try:
                source=Path(c.properties.get("sim_source",""))
                if source.stat().st_size > 100000: raise ValueError("GPIO source too large")
                self.script=PythonBoard(source.read_text(encoding="utf-8-sig"),get_definition(c.library_id),source)
                self.loaded=True
                self.result({"time":0,"gpio":self.script.advance(0),"warnings":[self.t("GPIO behavioural mode (no CPU/OS).", "Tryb funkcjonalny GPIO (bez CPU/systemu).")]})
            except (OSError,ValueError,SyntaxError) as exc: self.failure(str(exc))
            return
        if not profile.ready:
            self.failure(self.t(profile.reason_en,profile.reason_pl));return
        firmware=c.properties.get("sim_firmware","")
        if not firmware or not Path(firmware).is_file():
            self.failure(self.t("Assign an existing firmware file first.","Najpierw przypisz istniejący plik firmware."));return
        self.output.clear()
        self.runner.start(profile.engine,firmware,c.properties.get("sim_bootrom",""))

    def output_compile(self,message):
        if hasattr(self,"output"): self.output.appendPlainText(message)

    def compiled(self,firmware):
        c=self.component()
        if c is None or c.id!=self.compiling_id: return
        c.properties["sim_firmware"]=firmware; c.properties["sim_mode"]="arduino"; c.properties["sim_usb_power"]="true"
        self.editor.record_history()
        profile=profile_for(get_definition(c.library_id))
        self.runner.start(profile.engine,firmware)
        self.output.appendPlainText(self.t("Compiled. Reload the circuit from editor to connect devices.","Skompilowano. Pobierz obwód z edytora, aby podłączyć urządzenia."))

    def result(self,data):
        self.loaded=True
        states={0:"LOW",1:"HIGH",2:"IN",3:"PULLUP",4:"PULLDOWN",5:"KEEPER"}
        self.output.setPlainText(f"t = {data.get('time',0):.6f} s\n"+"  ".join(f"{pin}:{states.get(value,'?')}" for pin,value in data.get("gpio",{}).items())+"\nUART: "+data.get("serial","")+"\n"+"\n".join(data.get("warnings",[])))

    def toggle(self):
        if not self.loaded:
            self.failure(self.t("Load firmware first.","Najpierw wczytaj firmware."));return
        self.active=not self.active
        self.buttons[-1].setText(self.t("Pause","Pauza") if self.active else "Start")
        self.timer.start() if self.active else self.timer.stop()

    def tick(self):
        if self.active and self.script:
            try:
                states=self.script.advance(.016)
                self.result({"time":self.script.time,"gpio":states})
            except (ValueError,TypeError,IndexError) as exc: self.failure(str(exc))
            return
        if self.active and not self.runner.busy:self.runner.send({"op":"step","seconds":.001,"inputs":{}})

    def failure(self,message):
        self.shutdown()
        self.output.appendPlainText(message)

    def shutdown(self):
        self.compiler.stop(); self.compiling_id=None
        self.script=None
        self.active,self.loaded=False,False
        if self.buttons: self.buttons[-1].setText("Start")
        self.timer.stop()
        self.runner.stop()
