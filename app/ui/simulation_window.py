"""Osobny ciemny sandbox; kopia arkusza, bez marginesów i tabliczki.

Reset nie cofa edycji schematu. Odświeżenie pobiera nową kopię dokumentu.
Krótkie porcje obliczeń ograniczają blokowanie pętli zdarzeń Qt.
"""
from copy import deepcopy
from math import floor
from pathlib import Path
from time import perf_counter, perf_counter_ns
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QPen, QPainter, QPainterPath, QRadialGradient, QBrush,QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QPlainTextEdit, QDoubleSpinBox, QSplitter,
    QGraphicsItem, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QComboBox, QStyle)
from app.canvas.component_item import ComponentItem
from app.libraries.built_in import AVAILABLE_ITEMS, item_name
from app.libraries.simulation_catalog import behavior_for
from app.core.led_colors import color_key
from app.simulation.engine import Circuit, SimulationError
from app.simulation.emulator_process import EmulatorProcess


class SandboxView(QGraphicsView):
    fault_flash = 0.0

    def set_fault_flash(self, opacity):
        self.fault_flash=max(0.0,min(1.0,float(opacity)))
        self.viewport().update()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter,rect)
        if self.fault_flash:
            painter.save()
            painter.resetTransform()
            painter.fillRect(self.viewport().rect(),QColor(255,255,255,round(255*self.fault_flash)))
            painter.restore()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        zoom = self.transform().m11()*factor
        if .05 < zoom < 20: self.scale(factor, factor)
        event.accept()


class LiveSymbol(ComponentItem):
    display_state=None
    camera_frame=None

    def lcd_rect(self):
        r=self._hit_rect
        return QRectF(r.center().x()-160,r.top()-112,320,100)

    def boundingRect(self):
        rect=super().boundingRect()
        if getattr(self,"is_lcd",False):
            rect=rect.united(self.lcd_rect().adjusted(-6,-6,6,6))
        if getattr(self,"display_profile",None):
            from app.ui.display_preview import preview_rect
            rect=rect.united(preview_rect(self).adjusted(-6,-6,6,6))
        return rect

    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        state=self.display_state
        if self.display_profile:
            from app.ui.display_preview import paint_preview
            paint_preview(self,painter)
            return
        if self.is_lcd:
            state=state or {"cells":" "*32,"backlight":False}
            panel=self.lcd_rect()
            painter.save()
            painter.setPen(QPen(QColor("#527567"),2))
            painter.setBrush(QColor("#183d32")); painter.drawRoundedRect(panel,4,4)
            body=panel.adjusted(12,12,-12,-12)
            lit=state.get("backlight") and state.get("powered",True)
            painter.fillRect(body,QColor("#164fc9" if lit else "#101c3b"))
            painter.setPen(QColor("#e8f4ff" if lit else "#526489"))
            font=QFont("Courier New"); font.setBold(True); font.setPixelSize(22)
            painter.setFont(font)
            cells=str(state.get("cells",""))[:32].ljust(32)
            for row in range(2):
                for col in range(16):
                    cell=QRectF(body.left()+col*body.width()/16,
                                body.top()+row*body.height()/2,body.width()/16,body.height()/2)
                    painter.drawText(cell,Qt.AlignmentFlag.AlignCenter,cells[row*16+col])
            painter.restore()
            return
        if not state and self.camera_frame is None: return
        r=self._hit_rect
        top_pins=any(abs(pin.y-r.top())<.1 for pin in self.definition.pins)
        body=r.adjusted(27,44 if top_pins or len(self.definition.pins)>8 else 24,-27,-39)
        # Keep the existing title and terminal-name band unobstructed.
        if body.height()<8: return
        painter.save()
        if self.camera_frame is not None:
            painter.drawImage(body,self.camera_frame)
        else:
            painter.fillRect(body,QColor("#90bd36" if state.get("backlight") else "#34432a"))
            painter.setPen(QPen(QColor("#14240a"))); painter.drawRect(body)
            font=QFont("Courier New"); font.setBold(True); font.setPixelSize(max(3,int(min(body.width()/11,body.height()/2.4))))
            painter.setFont(font)
            cells=state.get("cells"," "*32).ljust(32)
            for row in range(2):
                painter.drawText(QRectF(body.left()+3,body.top()+row*body.height()/2,body.width()-6,body.height()/2),Qt.AlignmentFlag.AlignCenter,cells[row*16:(row+1)*16])
        painter.restore()

    def __init__(self, *args, toggle=None, **kwargs):
        super().__init__(*args, **kwargs)
        from app.libraries.display_profiles import display_profile
        self.display_profile=display_profile(self.definition)
        model=behavior_for(self.definition)
        self.is_lcd=bool(model and model.kind=="lcd_i2c")
        self.ink_color, self.paper_color = "#c6d5df", "#10151c"
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.toggle = toggle
        if self.definition.symbol == "logic_output": self.logic_label = "0"
        elif self.definition.symbol == "logic_input":
            self.logic_label = "1" if self.component.properties.get("sim_closed") == "true" else "0"

    def mousePressEvent(self, event):
        model=behavior_for(self.definition)
        if event.button() == Qt.MouseButton.LeftButton and model and model.kind in {"switch","tactile","spdt","encoder","digital_sensor","logic_input","joystick","ir_receiver"}:
            self.toggle(self.component.id)
            event.accept()
        else: super().mousePressEvent(event)


class SimulationWindow(QWidget):
    def __init__(self, editor):
        super().__init__(editor, Qt.WindowType.Window)
        self.setWindowIcon(editor.windowIcon())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.editor, self.pl = editor, editor.settings.language == "pl"
        self.circuit = None
        self.runners, self.pending = {}, set()
        self.initializing = False
        from app.ui.main_window import APP_VERSION
        self.setWindowTitle(f"ElectroSchem {APP_VERSION} — " + self.t("Simulation", "Symulacja"))
        self.resize(1150, 780)
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        from app.ui.theme import tint_icon
        self.run_button = QPushButton(self.t("Run", "Uruchom"))
        self.run_button.setIcon(tint_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)))
        self.pause_button = QPushButton(self.t("Pause", "Pauza"))
        self.pause_button.setIcon(tint_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)))
        self.step_button = QPushButton(self.t("Step", "Krok"))
        self.reset_button = QPushButton(self.t("Reset", "Resetuj"))
        self.reload_button = QPushButton(self.t("Reload from editor", "Pobierz z edytora"))
        for button in (self.run_button,self.pause_button,self.step_button,self.reset_button,self.reload_button): bar.addWidget(button)
        bar.addWidget(QLabel(self.t("Step [ms]", "Krok [ms]")))
        self.dt = QDoubleSpinBox()
        self.dt.setDecimals(7)
        self.dt.setRange(.0000001, 10)
        self.dt.setValue(.1)
        self.dt.setMaximumWidth(125)
        bar.addWidget(self.dt)
        bar.addWidget(QLabel(self.t("Time scale", "Skala czasu")))
        self.time_scale = QDoubleSpinBox()
        self.time_scale.setRange(1,1000); self.time_scale.setValue(100); self.time_scale.setSuffix(" %")
        self.time_scale.setMaximumWidth(105)
        self.time_scale.setToolTip(self.t(
            "100% = one simulated second per SI second (9 192 631 770 periods of the caesium-133 transition). Measured using the computer's monotonic clock, not an atomic clock; computation may lag.",
            "100% = sekunda symulacji na sekundę SI (9 192 631 770 okresów przejścia cezu-133). Pomiar zegarem monotonicznym komputera, nie zegarem atomowym; obliczenia mogą się opóźniać."))
        bar.addWidget(self.time_scale)
        self.clock = QLabel("t = 0 s")
        bar.addWidget(self.clock)
        layout.addLayout(bar)
        self.examples = QComboBox()
        self.examples.addItem(self.t("Examples (sandbox only — project is unchanged)", "Przykłady (tylko sandbox — projekt bez zmian)"), "")
        for key,en,pl in (("led","5 V + switch + LED","5 V + łącznik + LED"),("ac","AC + incandescent lamp","AC + żarówka"),("capacitor","Capacitor overvoltage fault","Awaria: przepięcie kondensatora")):
            self.examples.addItem(self.t(en,pl),key)
        self.examples.addItem(self.t("+5 V rail + GND + LED", "Szyna +5 V + GND + LED"),"rails")
        self.examples.addItem(self.t("PN2222 switches an LED", "PN2222 steruje diodą LED"),"transistor")
        self.examples.activated.connect(self.load_example)
        layout.addWidget(self.examples)
        self.camera_button=QPushButton(self.t("Device camera…","Kamera urządzenia…"))
        self.camera_button.clicked.connect(self.open_camera)
        layout.addWidget(self.camera_button)
        self.camera_preview=None
        self.buzzer_audio=None
        self.buzzer_sound_button=QPushButton(self.t("Buzzer sound","Dźwięk buzzerów"))
        self.buzzer_sound_button.setCheckable(True); self.buzzer_sound_button.setChecked(True)
        self.buzzer_sound_button.toggled.connect(lambda enabled:self.buzzer_audio.stop() if not enabled and self.buzzer_audio else None)
        layout.addWidget(self.buzzer_sound_button)
        note = QLabel(self.t("Wire colours show voltage. Click switches, turn potentiometer dials and hold keypad keys. Model details are in the Functionality database tab.",
            "Kolor przewodów pokazuje napięcie. Klikaj przełączniki, obracaj pokrętła potencjometrów i przytrzymuj klawisze klawiatur. Opisy modeli są w zakładce Baza funkcjonalności."))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.scene = QGraphicsScene(self)
        self.view = SandboxView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QColor("#10151c"))
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        splitter.addWidget(self.view)
        from app.ui.live_language import LocalizedLog
        self.log = LocalizedLog(lambda: self.editor.settings.language)
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        splitter.addWidget(self.log)
        splitter.setSizes([510, 130])
        self.tabs.addTab(splitter, self.t("Circuit", "Obwód"))
        self._model_table()
        from app.ui.emulator_panel import EmulatorPanel
        self.emulators = EmulatorPanel(editor)
        self.tabs.addTab(self.emulators, self.t("Firmware emulators", "Emulatory firmware"))
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.advance)
        self.next_tick = QTimer(self)
        self.next_tick.setSingleShot(True)
        self.next_tick.setInterval(0)
        self.next_tick.timeout.connect(self.continue_running)
        # Jednorazowy efekt awarii, niezależny od zatrzymanego zegara fizyki.
        # Nie migamy ekranem i nie naruszamy prostokątów rysowania symboli.
        self.fault_animation = QVariantAnimation(self)
        from app.ui.effects import FlashOverlay
        self.flash_overlay=FlashOverlay(self)
        self.fault_animation.setDuration(650)
        self.fault_animation.setStartValue(0.0)
        self.fault_animation.setEndValue(1.0)
        self.fault_animation.valueChanged.connect(self.animate_faults)
        self.last_render = 0.0
        self.run_button.clicked.connect(self.run)
        self.pause_button.clicked.connect(self.pause)
        self.step_button.clicked.connect(self.single_step)
        self.reset_button.clicked.connect(self.reset)
        self.reload_button.clicked.connect(self.reload)
        self.dt.valueChanged.connect(self.time_step_changed)
        self.time_scale.valueChanged.connect(self.pause)
        self.fault_sound = None
        from app.simulation.arduino_compile import ArduinoCompiler
        self.arduino_compiler=ArduinoCompiler(self)
        self.arduino_compiler.finished.connect(self.sketch_compiled)
        self.arduino_compiler.failed.connect(self.sketch_failed)
        self.arduino_compiler.progress.connect(self.log.appendPlainText)
        self.compile_queue=[]
        self.refresh_theme()
        self.reload()

    def refresh_theme(self):
        from app.ui.theme import apply_theme, tint_icon
        apply_theme(self, self.editor.settings)
        for panel in getattr(self,"controls",{}).values(): apply_theme(panel,self.editor.settings)
        self.view.setStyleSheet("QGraphicsView {background:#10151c; border:0;}")
        self.view.viewport().setStyleSheet("background:#10151c;")
        self.view.setBackgroundBrush(QColor("#10151c"))
        for button, symbol in ((self.run_button,QStyle.StandardPixmap.SP_MediaPlay),
                               (self.pause_button,QStyle.StandardPixmap.SP_MediaPause)):
            icon=self.style().standardIcon(symbol)
            button.setIcon(tint_icon(icon) if self.editor.settings.theme=="dark" else icon)

    def t(self, en, pl):
        from app.ui.live_language import phrase
        return phrase(self,en,pl)

    def refresh_language(self):
        from app.ui.live_language import refresh
        self.emulators.refresh_language()
        refresh(self,self.editor.settings.language)
        for item in getattr(self,"symbols",{}).values():
            item.language=self.editor.settings.language; item.update_labels()
        if self.circuit:
            self.circuit.language=self.editor.settings.language
            for part in self.circuit.parts: part.language=self.editor.settings.language

    def _model_table(self):
        table = QTableWidget(len(AVAILABLE_ITEMS), 3)
        table.setHorizontalHeaderLabels([self.t("Component", "Element"), "Model", self.t("Limitations", "Ograniczenia")])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        from app.libraries.menu_groups import library_sort_key
        for row, d in enumerate(sorted(AVAILABLE_ITEMS, key=library_sort_key)):
            model = behavior_for(d)
            table.setItem(row, 0, QTableWidgetItem(item_name(d, "pl" if self.pl else "en")))
            table.setItem(row, 1, QTableWidgetItem(model.kind if model else self.t("Unsupported — blocks Run", "Nieobsługiwany — blokuje start")))
            note=self.t(model.note_en,model.note_pl) if model else self.t("No implemented model. This component cannot be simulated yet.", "Brak zaimplementowanego modelu. Ten element nie jest jeszcze symulowany.")
            item=QTableWidgetItem(note)
            item.setToolTip(note)
            table.setItem(row,2,item)
        table.resizeRowsToContents()
        self.tabs.addTab(table, self.t("Functionality database", "Baza funkcjonalności"))

    def reload(self):
        self.pause()
        self.arduino_compiler.stop()
        self.editor._sync_positions()
        view = self.editor._current_view()
        if not view or not view._sheet: return
        self.initial_sheet=deepcopy(view._sheet)
        self.custom=deepcopy(self.editor.project.custom_components)
        from app.simulation.engine import loose_component_ids
        try: ignored=loose_component_ids(view._sheet,self.custom)
        except (ValueError,OverflowError): ignored=set()
        self.compile_queue=[c for c in view._sheet.components if c.id not in ignored and Path(c.properties.get("sim_source","")).suffix.lower()==".ino"]
        if self.compile_queue:
            self.run_button.setEnabled(False); self.step_button.setEnabled(False)
            self.circuit=None
            self.log.setPlainText(self.t("Compiling Arduino sketches…","Kompilowanie szkiców Arduino…"))
            self.compile_next(); return
        self.reload_compiled_sheet()

    def compile_next(self):
        if not self.compile_queue:
            self.editor.record_history(); self.reload_compiled_sheet(); return
        from app.libraries.built_in import get_definition
        c=self.compile_queue[0]; self.arduino_compiler.start(c,get_definition(c.library_id))

    def sketch_compiled(self,firmware):
        if not self.compile_queue: return
        c=self.compile_queue.pop(0); c.properties["sim_firmware"]=firmware; c.properties["sim_mode"]="arduino"; c.properties["sim_usb_power"]="true"
        self.compile_next()

    def sketch_failed(self,message):
        self.compile_queue=[]
        self.log.appendPlainText(self.t("Compilation failed: ","Kompilacja nie powiodła się: ")+message)

    def reload_compiled_sheet(self):
        view=self.editor._current_view()
        if not view or not view._sheet: return
        self.initial_sheet = deepcopy(view._sheet)
        self.examples.setCurrentIndex(0)
        self.custom = deepcopy(self.editor.project.custom_components)
        self.reset()
        self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-60,-60,60,60), Qt.AspectRatioMode.KeepAspectRatio)

    def load_example(self,index):
        self.examples.setCurrentIndex(index)
        key=self.examples.itemData(index)
        if not key:
            self.reload()
            return
        from app.simulation.examples import example
        self.initial_sheet=example(key)
        self.custom=[]
        self.reset()
        self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-60,-60,60,60),Qt.AspectRatioMode.KeepAspectRatio)

    def reset(self):
        self.pause()
        self.arduino_compiler.stop(); self.compile_queue=[]
        if self.camera_preview is not None:
            self.camera_preview.close(); self.camera_preview=None
        self.fault_animation.stop()
        self.view.set_fault_flash(0)
        self.flash_overlay.set_opacity(0)
        if self.fault_sound is not None: self.fault_sound.stop()
        self.stop_emulators()
        self.sheet = deepcopy(self.initial_sheet)
        from app.ui.main_window import APP_VERSION
        self.setWindowTitle(f"ElectroSchem {APP_VERSION} — " + self.t("Simulation", "Symulacja") + " — " + self.sheet.name)
        self.log.clear()
        self.reported_warnings = set()
        self.clock.setText("t = 0 s")
        self.scene.clear()
        self.symbols, self.wires, self.glows, self.fault_marks = {}, {}, {}, {}
        self.controls={}
        self.explosion_visuals=[]
        from app.canvas.annotations import AnnotationItem
        self.comments = {}
        for annotation in self.sheet.comments:
            item = AnnotationItem(annotation)
            item.setDefaultTextColor(QColor("#d6e2eb"))
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            item.setZValue(3)
            self.scene.addItem(item)
            self.comments[annotation.id] = item
        for c in self.sheet.components:
            item = LiveSymbol(c, language="pl" if self.pl else "en", standard=self.sheet.standard, custom_components=self.custom, toggle=self.toggle)
            self.scene.addItem(item)
            self.symbols[c.id] = item
            # Poświata to oddzielny obiekt, więc nie łamie boundingRect symbolu.
            halo = self.scene.addEllipse(c.x-32,c.y-32,64,64,QPen(Qt.PenStyle.NoPen))
            halo.setZValue(-1 if item.definition.symbol in {"logic_input", "logic_output"} else 2)
            halo.hide()
            self.glows[c.id] = halo
        for w in self.sheet.wires:
            points = w.points or [[w.start_x,w.start_y],[w.end_x,w.end_y]]
            path = QPainterPath(QPointF(*points[0]))
            for p in points[1:]: path.lineTo(QPointF(*p))
            self.wires[w.id] = self.scene.addPath(path, QPen(QColor("#718499"), 2))
        try:
            self.circuit = Circuit(self.sheet, self.custom, "pl" if self.pl else "en")
        except (ValueError, OverflowError) as exc:
            self.circuit = None
            self.log.setPlainText(self.t("Start blocked. Edit component properties, then Reload from editor:\n", "Start zablokowany. Popraw właściwości elementów i pobierz z edytora:\n")+str(exc))
        else:
            from app.ui.simulation_controls import add_control
            for device in self.circuit.devices:
                if device.kind in {"potentiometer","keypad"}:
                    self.controls[device.component.id]=add_control(self,device,self.symbols[device.component.id])
            self.log.setPlainText(self.t("Ready. Source negative terminal is the reference when GND is absent. Time shown is simulation time, not wall time.",
                "Gotowe. Bez GND punktem odniesienia jest minus pierwszego źródła. Wyświetlany czas jest czasem symulacji, nie zegara."))
            for cid,message in self.circuit.ignored_warnings.items():
                item=self.symbols[cid]; item.ink_color="#74818c"; item.update()
                item.setToolTip(f"{item.component.reference}: {message}")
                self.log.appendPlainText(f"{item.component.reference}: {message}")
                self.reported_warnings.add(cid)
        self.run_button.setEnabled(self.circuit is not None)
        self.step_button.setEnabled(self.circuit is not None)
        self.camera_button.setEnabled(any("kamer" in item.definition.name.lower() or "camera" in item.definition.name_en.lower() for item in self.symbols.values()))
        self.buzzer_sound_button.setEnabled(self.circuit is not None and any(d.kind=="buzzer" for d in self.circuit.devices))
        self.adjust_time_step()

    def open_camera(self):
        from app.ui.camera_preview import CameraPreview
        candidates=[item for item in self.symbols.values() if "kamer" in item.definition.name.lower() or "camera" in item.definition.name_en.lower()]
        if not candidates: return
        if self.camera_preview is None:
            self.camera_preview=CameraPreview(self,self.editor.settings.language)
            self.camera_preview.frame.connect(lambda frame:self.camera_frame(candidates,frame))
        self.camera_preview.show(); self.camera_preview.raise_()

    def camera_frame(self,items,frame):
        for item in items:
            if item in self.symbols.values(): item.camera_frame=None if frame.isNull() else frame; item.update()

    def toggle(self, cid):
        if not self.circuit or self.circuit.result.faults: return
        for d in self.circuit.devices:
            if d.component.id == cid:
                if d.kind in {"switch","tactile","spdt","encoder","joystick","ir_receiver"}:
                    d.closed = not d.closed
                    self.symbols[cid].component.properties["sim_closed"] = "true" if d.closed else "false"
                elif d.kind == "digital_sensor":
                    d.parameters["sim_active"]="false" if d.parameters["sim_active"]=="true" else "true"
                elif d.kind == "keypad":
                    key=d.parameters["sim_key"]
                    d.parameters["sim_key"]="0" if key=="none" else "none" if key=="15" else str(int(key)+1)
                elif d.parameters.get("logic_input"):
                    d.closed=not d.closed
                    d.parameters["value"]=5.0 if d.closed else 0.0
                self.symbols[cid].update()
                self.log.appendPlainText(f"{d.component.reference}: "+self.t("input state changed", "zmieniono stan wejścia"))

    def set_simulation_input(self,cid,key,value):
        if not self.circuit or self.circuit.result.faults: return
        device=next((d for d in self.circuit.devices if d.component.id==cid),None)
        if device is None: return
        if device.kind=="potentiometer" and key=="sim_position":
            device.parameters[key]=max(0,min(1,float(value)))
        elif device.kind=="keypad" and key=="sim_key" and str(value) in {"none",*(str(i) for i in range(16))}:
            device.parameters[key]=str(value)
        else: return
        if not self.timer.isActive(): self.single_step()

    def run(self):
        if self.circuit:
            if self.circuit.result.faults:
                if self.circuit.can_resume:
                    self.circuit.acknowledge_faults()
                else:
                    self.reset()
                    if not self.circuit: return
            self.emulators.shutdown()
            self.dt.setEnabled(False)
            self.wall_start_ns=perf_counter_ns()
            self.sim_start=self.circuit.time
            self.timer.start()

    def pause(self, *_):
        if getattr(self,"buzzer_audio",None): self.buzzer_audio.stop()
        if hasattr(self, "timer"): self.timer.stop()
        if hasattr(self, "next_tick"): self.next_tick.stop()
        if hasattr(self, "dt"): self.dt.setEnabled(True)

    def single_step(self):
        self.pause()
        self.advance(single=True)

    def continue_running(self):
        if self.timer.isActive(): self.advance()

    def advance(self, single=False):
        if not self.circuit: return
        if self.timer.isActive() and not single and self._steps_due() == 0: return
        devices = [d for d in self.circuit.active_devices() if d.kind == "mcu"]
        if devices:
            if self.pending: return
            if not self.runners:
                self.emulators.shutdown()
                self.initializing = True
                self.pending = {d.component.id for d in devices}
                for device in devices:
                    cid = device.component.id
                    runner = EmulatorProcess(self)
                    self.runners[cid] = runner
                    runner.result.connect(lambda data, key=cid: self.emulated(key,data))
                    runner.failed.connect(self.emulator_failed)
                # Każdy worker istnieje przed startem pierwszego, także gdy
                # brak zależności wywoła błąd synchronicznie.
                for device in devices:
                    if device.component.id not in self.runners: break
                    self.runners[device.component.id].start(device.parameters["profile"].engine,device.component.properties["sim_firmware"],device.component.properties.get("sim_bootrom",""))
                return
            self.pending = {d.component.id for d in devices}
            for device in devices:
                self.runners[device.component.id].send({"op":"step", "seconds":self.dt.value()/1000,
                    "inputs":self.circuit.digital_inputs(device),"i2c_addresses":self.circuit.i2c_addresses(device)})
            return
        self.calculate(single)

    def emulated(self,cid,data):
        if cid not in self.pending or not self.circuit: return
        self.circuit.gpio_states[cid] = data.get("gpio",{})
        device=next(d for d in self.circuit.devices if d.component.id==cid)
        try: self.circuit.receive_i2c(device,data.get("i2c",[]))
        except ValueError as error:
            self.emulator_failed(str(error)); return
        self.pending.discard(cid)
        if data.get("serial"): self.log.appendPlainText("UART: "+data["serial"])
        for warning in data.get("warnings",[]): self.log.appendPlainText(warning)
        if not self.pending:
            if self.initializing:
                self.initializing = False
                self.advance(single=True)
            else:
                self.calculate(single=True)
                # Kolejny krok nie czeka 16 ms na animację UI. Czas CPU
                # pozostaje wirtualny, a odpowiedź procesu zapewnia yield.
                if self.timer.isActive(): self.next_tick.start()

    def emulator_failed(self,message):
        self.pause()
        self.stop_emulators()
        self.run_button.setEnabled(False)
        self.step_button.setEnabled(False)
        self.log.appendPlainText(message)

    def stop_emulators(self):
        self.pending.clear()
        self.initializing = False
        for runner in self.runners.values():
            runner.stop()
            # Proces może zakończyć się już podczas zamykania okna; jego
            # sygnały mogły zostać odłączone przez obsługę błędu.
            for signal in (runner.result,runner.failed):
                try: signal.disconnect()
                except (RuntimeError,TypeError): pass
            runner.deleteLater()
        self.runners.clear()

    def time_step_changed(self, *_):
        self.pause()
        self.adjust_time_step()

    def adjust_time_step(self):
        circuit=getattr(self,"circuit",None)
        if circuit is None: return
        precision=10**self.dt.decimals()
        limit=max(self.dt.minimum(),floor(circuit.maximum_time_step()*1000*precision)/precision)
        if self.dt.value()>limit:
            self.dt.setValue(limit)
            self.log.appendPlainText(self.t(
                "Time step reduced automatically to sample the signal frequency safely.",
                "Krok czasowy zmniejszony automatycznie, aby poprawnie próbkować częstotliwość sygnału."))

    def calculate(self, single=False):
        started = perf_counter()
        try:
            count=1 if single else self._steps_due() if self.timer.isActive() else 100
            if count == 0: return
            for _ in range(min(count,10000)):
                result = self.circuit.step(self.dt.value()/1000)
                # Check every computed step, including those between UI
                # refreshes. Report once per component until Reset, otherwise
                # a changing voltage would flood the log on every time step.
                for cid, message in result.warnings.items():
                    if cid not in self.reported_warnings:
                        self.reported_warnings.add(cid)
                        self.log.appendPlainText(self.t("Warning: ", "Ostrzeżenie: ")+message)
                if result.faults or perf_counter()-started > .008: break
            # Yield to Qt between bounded batches, but do not wait for the
            # display timer while physics is still behind its wall-clock target.
            if self.timer.isActive() and not single and not result.faults and self._steps_due():
                self.next_tick.start()
        except (SimulationError, ArithmeticError) as exc:
            self.pause()
            self.log.appendPlainText(str(exc))
            self.run_button.setEnabled(False)
            self.step_button.setEnabled(False)
            return
        if self.timer.isActive() and not result.faults and perf_counter()-self.last_render < .03:
            return
        self.last_render = perf_counter()
        if self.timer.isActive() and not result.faults and self.buzzer_sound_button.isChecked():
            if any(sound.get("level",0)>0 for sound in result.sounds.values()) and self.buzzer_audio is None:
                try:
                    from app.ui.buzzer_audio import BuzzerAudio
                    self.buzzer_audio=BuzzerAudio(self)
                except (RuntimeError,OSError):
                    self.buzzer_sound_button.setChecked(False)
                    self.log.appendPlainText(self.t("Buzzer audio unavailable.","Dźwięk buzzera jest niedostępny."))
            if self.buzzer_audio: self.buzzer_audio.update(result.sounds)
        self.clock.setText(f"t = {result.time:.6f} s")
        for wid, item in self.wires.items():
            voltage = result.voltages.get(self.circuit.netlist.wires[wid], 0)
            color = QColor("#247a4a" if voltage > .01 else "#4d6594" if voltage < -.01 else "#56606b")
            item.setPen(QPen(color,2))
            item.setToolTip(f"{voltage:.6g} V")
        colours = {"red":"#ff4433","green":"#48ff55","blue":"#4488ff","yellow":"#ffee44","orange":"#ff9922","white":"#ffffff","ir":"#9f63cb"}
        for cid, item in self.symbols.items():
            current = result.currents.get(cid)
            reading=result.readings.get(cid,"")
            item.display_state=result.displays.get(cid)
            if item.display_state: item.update()
            if item.definition.symbol == "logic_output":
                item.logic_label="1" if reading.startswith("HIGH") else "0"
                item.update()
            elif item.definition.symbol == "logic_input":
                device=next((d for d in self.circuit.devices if d.component.id==cid),None)
                item.logic_label="1" if device and device.parameters["value"]>2.5 else "0"
                item.update()
            if current is not None: item.setToolTip(f"{item.component.reference}: {current:.6g} A"+("\n"+reading if reading else ""))
            brightness = result.brightness.get(cid, 0)
            if item.definition.symbol == "logic_input":
                brightness = 1.0 if item.logic_label == "1" else 0.0
            halo = self.glows[cid]
            halo.setVisible(brightness > .001)
            if brightness > .001:
                center = item.scenePos()
                gradient = QRadialGradient(center,32)
                if item.definition.symbol in {"logic_input", "logic_output"}:
                    gradient.setColorAt(0,QColor(255,255,255,85))
                    gradient.setColorAt(.4,QColor(255,255,255,45))
                    gradient.setColorAt(1,QColor(255,255,255,0))
                    halo.setBrush(QBrush(gradient))
                    continue
                color = QColor(colours.get(color_key(item.component.properties.get("color", "")), "#ffd166"))
                if cid in result.rgb:
                    channels=result.rgb[cid]
                    peak=max(channels)
                    color=QColor.fromRgbF(*(level/peak for level in channels))
                # A bright core and coloured halo remain visible over the
                # symbol and voltage-coloured wires, including at low zoom.
                color.setAlphaF(min(1, .65+brightness*.35))
                gradient.setColorAt(0,QColor("#ffffff"))
                gradient.setColorAt(.18,color)
                gradient.setColorAt(.55,color)
                gradient.setColorAt(1,QColor(0,0,0,0))
                halo.setBrush(QBrush(gradient))
        if result.faults:
            self.pause()
            self.run_button.setEnabled(True)
            self.step_button.setEnabled(False)
            from app.ui.effects import fault_effect,ExplosionVisual,effect_seconds
            level=fault_effect(self.editor.settings)
            for cid, message in result.faults.items():
                self.log.appendPlainText(message)
                item = self.symbols.get(cid)
                if item is None: continue
                item.ink_color = "#ff5555"
                item.update()
                marker = self.scene.addText("!")
                marker.setDefaultTextColor(QColor("#ff8855"))
                marker.setPos(item.x()-15,item.y()-42)
                self.fault_marks[cid] = marker
                if level!="mini":
                    visual=ExplosionVisual(level); visual.setPos(item.scenePos())
                    self.scene.addItem(visual); self.explosion_visuals.append(visual)
            self.log.appendPlainText(self.t("Stopped. Damage indication is a model threshold, not a prediction of an actual explosion.",
                "Zatrzymano. Oznaczenie uszkodzenia jest progiem modelu, nie prognozą rzeczywistego wybuchu."))
            self.animate_faults(0)
            self.fault_animation.setDuration(round(effect_seconds(level)*1000))
            if level!="mini":
                try:
                    from app.ui.fault_sound import FaultSound
                    if self.fault_sound is None or getattr(self.fault_sound,"level",level)!=level:
                        if self.fault_sound is not None: self.fault_sound.dispose()
                        self.fault_sound=FaultSound(self,level)
                    self.fault_sound.play()
                except (RuntimeError,OSError) as exc:
                    self.log.appendPlainText(self.t("Audio unavailable: ","Dźwięk niedostępny: ")+str(exc))
            self.fault_animation.start()
            self.log.appendPlainText(self.t("Run resumes healthy circuits; if none remain, it resets this simulation.", "Start wznawia sprawne obwody; jeśli żaden nie pozostał, resetuje symulację."))

    def _steps_due(self):
        elapsed=max(0,perf_counter_ns()-self.wall_start_ns)/1_000_000_000
        target=self.sim_start+elapsed*self.time_scale.value()/100
        due=max(0,int((target-self.circuit.time)/(self.dt.value()/1000)))
        if target-self.circuit.time > .25:
            self.clock.setToolTip(self.t("Computation is slower than the requested time scale.", "Obliczenia są wolniejsze od zadanej skali czasu."))
        else: self.clock.setToolTip("")
        return due

    def animate_faults(self,value):
        from app.ui.effects import fault_effect
        level=fault_effect(self.editor.settings)
        dramatic=level=="mega" and bool(self.fault_marks)
        opacity=min(1.,max(0.,(1-float(value))/.75))**1.5 if dramatic else 0
        self.view.set_fault_flash(0)
        self.flash_overlay.set_opacity(opacity)
        for visual in self.explosion_visuals: visual.set_progress(value)
        for cid in self.fault_marks:
            halo,item=self.glows[cid],self.symbols[cid]
            halo.setVisible(True)
            halo.setOpacity(1-float(value))
            halo.setTransformOriginPoint(item.scenePos())
            halo.setScale(1+float(value)*1.5)
            gradient=QRadialGradient(item.scenePos(),32)
            if level!="mini":
                # One abrupt local flash, not a repeated strobe. This branch
                # is disabled in the default, silent accessibility setting.
                halo.setZValue(4)
                halo.setScale(2+(8 if level=="mega" else 3)*float(value)**.35)
                halo.setOpacity(max(0,1-float(value))**2)
                gradient.setColorAt(0,QColor("#ffffff"))
                gradient.setColorAt(.3,QColor("#fff4bb"))
                gradient.setColorAt(.65,QColor("#ff9233"))
                gradient.setColorAt(1,QColor(0,0,0,0))
                halo.setBrush(QBrush(gradient))
                continue
            gradient.setColorAt(0,QColor("#ff6666"))
            gradient.setColorAt(.4,QColor("#cc3333"))
            gradient.setColorAt(1,QColor(0,0,0,0))
            halo.setBrush(QBrush(gradient))

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            self.fault_animation.stop(); self.animate_faults(1)
            if self.fault_sound is not None: self.fault_sound.stop()
            if self.isFullScreen(): self.showMaximized()
            event.accept()
        else: super().keyPressEvent(event)

    def closeEvent(self, event):
        self.pause()
        self.arduino_compiler.stop(); self.compile_queue=[]
        if self.camera_preview is not None: self.camera_preview.close()
        self.fault_animation.stop()
        if self.fault_sound is not None: self.fault_sound.stop()
        self.stop_emulators()
        self.emulators.shutdown()
        super().closeEvent(event)
