"""Osobny ciemny sandbox; kopia arkusza, bez marginesów i tabliczki.

Reset nie cofa edycji schematu. Odświeżenie pobiera nową kopię dokumentu.
Krótkie porcje obliczeń ograniczają blokowanie pętli zdarzeń Qt.
"""
from copy import deepcopy
from math import floor, hypot
from pathlib import Path
from time import perf_counter, perf_counter_ns
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QPen, QPainter, QPainterPath, QRadialGradient, QBrush,QFont,QCursor
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

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_S and event.modifiers()==Qt.KeyboardModifier.ShiftModifier:
            self._show_hidden_wires=True; self.viewport().update(); event.accept(); return
        if event.key()==Qt.Key.Key_E and not event.modifiers():
            point=self.mapToScene(self.mapFromGlobal(QCursor.pos()))
            candidates=list(self.scene().items(point))+list(self.scene().selectedItems())
            for item in candidates:
                while item.parentItem(): item=item.parentItem()
                from app.ui.asset_shells import CaseShell
                if isinstance(item,CaseShell) and item.activate_at(item.mapFromScene(point)):
                    self._action_target=item; event.accept(); return
                if isinstance(item,LiveSymbol):
                    event.ignore()
                    item.keyPressEvent(event)
                    if event.isAccepted():
                        self._action_target=item
                        return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key() in (Qt.Key.Key_S,Qt.Key.Key_Shift) and not event.isAutoRepeat(): self._show_hidden_wires=False; self.viewport().update()
        if event.key()==Qt.Key.Key_E and getattr(self,'_action_target',None):
            self._action_target.keyReleaseEvent(event)
            if not event.isAutoRepeat(): self._action_target=None
            event.accept(); return
        super().keyReleaseEvent(event)

    def focusOutEvent(self,event):
        self._show_hidden_wires=False; self.viewport().update()
        item=getattr(self,'_action_target',None)
        if item and hasattr(item,'release_input'): item.release_input()
        elif item and item.held:
            model=behavior_for(item.definition)
            if model and model.kind in {'tactile','joystick'}: item.held(item.component.id,'sim_closed',False)
        self._action_target=None
        super().focusOutEvent(event)

    def set_fault_flash(self, opacity):
        self.fault_flash=max(0.0,min(1.0,float(opacity)))
        self.viewport().update()

    def drawForeground(self, painter, rect):
        super().drawForeground(painter,rect)
        window=getattr(self,'simulation_window',None)
        if window and (getattr(self,'_show_hidden_wires',False) or window.editor.settings.wires_through_cases):
            from app.canvas.wire_peek import draw
            symbols=[i for i in window.symbols.values() if i.isVisible()]+list(getattr(window,'asset_cases',{}).values())
            draw(painter,symbols,[i for i in window.wires.values() if i.isVisible()],'#71b08a')
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
        if self.definition.symbol == "meter":
            rect=rect.united(QRectF(-72,-41,144,20))
        if self.definition.name=="Oscyloskop": rect=rect.united(self.scope_rect())
        if getattr(self,"is_lcd",False):
            rect=rect.united(self.lcd_rect().adjusted(-6,-6,6,6))
        if getattr(self,"display_profile",None):
            from app.ui.display_preview import preview_rect
            rect=rect.united(preview_rect(self).adjusted(-6,-6,6,6))
        return rect

    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        if self.definition.name=="Oscyloskop":
            from app.ui.instrument_graphics import draw_waveform
            draw_waveform(painter,self.scope_rect(),getattr(self,"scope_samples",()),getattr(self,'scope_bounds',(-10,10)),getattr(self,'scope_duration',.08),getattr(self,'scope_autoscale',False),getattr(self,'scope_cursor_fraction',None))
        if self.definition.symbol == "meter" and getattr(self,"meter_reading",""):
            painter.save(); font=QFont("Arial"); font.setPixelSize(9); painter.setFont(font)
            painter.setPen(QColor("#c6d5df")); painter.drawText(QRectF(-70,-39,140,16),Qt.AlignmentFlag.AlignCenter,self.meter_reading)
            painter.restore()
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

    def __init__(self, *args, toggle=None, motion=None, console=None, held=None, **kwargs):
        super().__init__(*args, **kwargs)
        from app.libraries.display_profiles import display_profile
        self.display_profile=display_profile(self.definition)
        model=behavior_for(self.definition)
        self.is_lcd=bool(model and model.kind=="lcd_i2c")
        self.ink_color, self.paper_color = "#c6d5df", "#10151c"
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.toggle = toggle
        self.motion = motion
        self.console = console
        self.held = held
        self.scope_dimensions=(480,260)
        self.scope_cursor_fraction=None
        self._scope_dragging=False
        self.rfid = self.definition.name == "Karta RFID"
        self.match = self.definition.name == "Zapałka"
        self.remote = self.definition.name == "Pilot IR"
        self.sensor_prop = self.definition.name in {"Cel ultradźwiękowy", "Osoba", "Pilot IR"}
        if self.rfid or self.match or self.sensor_prop:
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.setCursor(Qt.CursorShape.OpenHandCursor); self.setZValue(15)
            prefix="rfid:" if self.rfid else "match-move:" if self.match else "sensor-prop-move:"
            self.on_position_changed = lambda: self.console(prefix+self.component.id) if self.console else None
        self.is_pir = "PIR" in self.definition.name
        self.setAcceptHoverEvents(self.is_pir)
        if self.definition.symbol == "logic_output": self.logic_label = "0"
        elif self.definition.symbol == "logic_input":
            self.logic_label = "1" if self.component.properties.get("sim_closed") == "true" else "0"

    def mousePressEvent(self, event):
        model=behavior_for(self.definition)
        if event.button()==Qt.MouseButton.LeftButton: self.setFocus(Qt.FocusReason.MouseFocusReason)
        if (event.button()==Qt.MouseButton.LeftButton and self.definition.name=="Oscyloskop"
                and self._scope_plot_rect().contains(event.pos())):
            self._scope_dragging=True; self._update_scope_cursor(event.pos()); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and model and model.kind in {"tactile", "joystick"} and self.held:
            self.held(self.component.id, "sim_closed", True); event.accept(); return
        if self.match and event.button()==Qt.MouseButton.LeftButton:
            self._match_press_scene=QPointF(event.scenePos())
            super().mousePressEvent(event); return
        if self.remote and event.button()==Qt.MouseButton.LeftButton:
            self._remote_press_scene=QPointF(event.scenePos())
            super().mousePressEvent(event); return
        if self.definition.name == "Karta RFID" and event.button() == Qt.MouseButton.LeftButton:
            super().mousePressEvent(event); return
        if event.button() == Qt.MouseButton.LeftButton and self.definition.symbol=="meter" and self.console:
            self.console(self.component.id); event.accept(); return
        if self.is_pir:
            event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and model and model.kind in {"switch","tactile","spdt","multi_switch","encoder","digital_sensor","logic_input","joystick","ir_receiver"}:
            self.toggle(self.component.id)
            event.accept()
        else: super().mousePressEvent(event)

    def scope_rect(self):
        width,height=getattr(self,'scope_dimensions',(480,260))
        return QRectF(-width/2,-45-height,width,height)

    def _scope_plot_rect(self):
        return self.scope_rect().adjusted(56,22,-12,-24)

    def _update_scope_cursor(self,point):
        plot=self._scope_plot_rect()
        if not plot.contains(point):
            self.scope_cursor_fraction=None
        else:
            self.scope_cursor_fraction=(point.x()-plot.left())/max(1.,plot.width())
        self.update()

    def mouseMoveEvent(self,event):
        if self._scope_dragging:
            self._update_scope_cursor(event.pos()); event.accept(); return
        super().mouseMoveEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_E and not event.modifiers():
            model=behavior_for(self.definition)
            if "Raspberry Pi" in self.definition.name and "Pico" not in self.definition.name and self.console:
                if not event.isAutoRepeat(): self.console(self.component.id)
                event.accept(); return
            if model and model.kind in {"tactile","joystick"} and self.held:
                if not event.isAutoRepeat(): self.held(self.component.id,"sim_closed",True)
                event.accept(); return
            if self.definition.symbol=="meter" and self.console:
                if not event.isAutoRepeat(): self.console(self.component.id)
                event.accept(); return
            if model and model.kind in {"switch","spdt","multi_switch","encoder","digital_sensor","logic_input","keypad","ir_receiver"}:
                if not event.isAutoRepeat(): self.toggle(self.component.id)
                event.accept(); return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        model=behavior_for(self.definition)
        if event.key()==Qt.Key.Key_E and model and model.kind in {"tactile","joystick"} and self.held:
            if not event.isAutoRepeat(): self.held(self.component.id,"sim_closed",False)
            event.accept(); return
        super().keyReleaseEvent(event)

    def hoverMoveEvent(self, event):
        if self.is_pir and self.motion and event.pos() != event.lastPos():
            self.motion(self.component.id)
        super().hoverMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._scope_dragging and event.button()==Qt.MouseButton.LeftButton:
            self._update_scope_cursor(event.pos()); self._scope_dragging=False; event.accept(); return
        model = behavior_for(self.definition)
        if event.button() == Qt.MouseButton.LeftButton and model and model.kind in {"tactile", "joystick"} and self.held:
            self.held(self.component.id, "sim_closed", False); event.accept(); return
        if self.match and event.button()==Qt.MouseButton.LeftButton:
            start=getattr(self,"_match_press_scene",None)
            super().mouseReleaseEvent(event)
            self._match_press_scene=None
            dragged=start is not None and (event.scenePos()-start).manhattanLength()>=6
            if dragged:
                if self.console: self.console("match:"+self.component.id)
            elif self.toggle:
                self.toggle(self.component.id)
            return
        if self.sensor_prop and event.button()==Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            if self.remote:
                start=getattr(self,"_remote_press_scene",None)
                self._remote_press_scene=None
                dragged=start is not None and (event.scenePos()-start).manhattanLength()>=6
                if not dragged and self.toggle: self.toggle(self.component.id)
            if self.console: self.console("sensor-prop:"+self.component.id)
            return
        super().mouseReleaseEvent(event)


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
        self.examples.addItem(self.t("USB-C powered LED", "LED zasilany z USB C"),"usb_c_led")
        for key,en,pl in (("fault_led","Failure: LED overcurrent","Awaria: przepalenie LED"),("fault_resistor","Failure: resistor overload","Awaria: zapłon rezystora"),("fault_gpio","Failure: GPIO overvoltage","Awaria: uszkodzenie GPIO")):
            self.examples.addItem(self.t(en,pl),key)
        self.examples.addItem(self.t("PN2222 switches an LED", "PN2222 steruje diodą LED"),"transistor")
        for key,en,pl in (("meter_ac","Measurements: AC RMS and oscilloscope","Pomiary: AC RMS i oscyloskop"),("meter_ohm","Measurements: resistance and continuity","Pomiary: opór i ciągłość"),("pi_blink","Raspberry Pi: blinking LED with Python","Raspberry Pi: miganie LED z Pythonem")):
            self.examples.addItem(self.t(en,pl),key)
        self.examples.activated.connect(self.load_example)
        layout.addWidget(self.examples)
        self.camera_button=QPushButton(self.t("Device camera…","Kamera urządzenia…"))
        self.camera_button.setIcon(editor._icon("camera_access.png"))
        self.camera_button.clicked.connect(self.open_camera)
        tools=QHBoxLayout(); layout.addLayout(tools)
        tools.addWidget(self.camera_button)
        self.camera_preview=None
        self.buzzer_audio=None
        from app.ui.sound_button import SoundButton
        self.buzzer_sound_button=SoundButton(self.t("Mute sound","Wycisz dźwięk"))
        self.buzzer_sound_button.setCheckable(True); self.buzzer_sound_button.setChecked(False)
        self.buzzer_sound_button.setIcon(editor._icon("sound_on.png"))
        self.buzzer_sound_button.toggled.connect(self.mute_sound)
        self.buzzer_sound_button.clicked.connect(self.cycle_sound)
        tools.addWidget(self.buzzer_sound_button)
        self.measurement_panel=None
        self.measurement_button=QPushButton(self.t("Measurement tools", "Narzędzia pomiarowe"))
        self.measurement_button.setIcon(editor._icon("measurement_tool.png"))
        self.measurement_button.clicked.connect(self.open_measurements); tools.addWidget(self.measurement_button)
        for button,standard in ((self.camera_button,QStyle.StandardPixmap.SP_ComputerIcon),(self.buzzer_sound_button,QStyle.StandardPixmap.SP_MediaVolume),(self.measurement_button,QStyle.StandardPixmap.SP_FileDialogDetailedView)):
            if button.icon().isNull(): button.setIcon(self.style().standardIcon(standard))
            button.setToolTip(button.text()); button.setText(""); button.setFixedSize(44,44)
            button.setIconSize(__import__("PySide6.QtCore",fromlist=["QSize"]).QSize(28,28))
        tools.addStretch()
        note = QLabel(self.t("Wire colours show voltage. Click switches, turn potentiometer dials and hold keypad keys. Drag RFID cards to readers; light a match for a flame sensor, move a target for HC-SR04 or a person near PIR, and click an IR remote near its receiver. Sensor sliders set other external stimuli. Model details are in the Functionality database tab.",
            "Kolor przewodów pokazuje napięcie. Klikaj przełączniki, obracaj pokrętła potencjometrów i przytrzymuj klawisze klawiatur. Karty RFID przeciągaj do czytników; zapałką pobudź czujnik płomienia, celem ustaw odległość HC-SR04, a osobą czujnik PIR. Pilot IR kliknięty przy odbiorniku wysyła krótki impuls. Suwaki ustawiają pozostałe bodźce czujników. Opisy modeli są w zakładce Baza funkcjonalności."))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.scope_controls=None; self.scope_panels={}
        self.sound_volume=1.0
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.scene = QGraphicsScene(self)
        self.view = SandboxView(self.scene)
        self.view.simulation_window=self
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
        from app.ui.instrument_graphics import scope_dimensions
        dimensions=scope_dimensions(self.editor.settings)
        for item in getattr(self,'scopes',{}).values():
            item.prepareGeometryChange(); item.scope_dimensions=dimensions; item.update()
            controls=getattr(self,'scope_panels',{}).get(item.component.id)
            if controls:
                rect=item.scope_rect(); controls.graphicsProxyWidget().setPos(rect.right()+12,rect.top())
                apply_theme(controls,self.editor.settings)
        panel=getattr(self,'measurement_panel',None)
        if panel: panel.waveform.setMinimumSize(*dimensions)
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
        self._last_cable_circuit=None
        self.view._action_target=None
        if getattr(self,"measurement_panel",None):
            self.measurement_panel.close(); self.measurement_panel.deleteLater(); self.measurement_panel=None
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
        from app.core.assets import expand_assets, with_asset_dependencies
        self.custom=with_asset_dependencies(self.custom)
        self.sheet=expand_assets(self.sheet,self.custom)
        for c in self.sheet.components:
            from app.libraries.built_in import get_definition
            model=behavior_for(get_definition(c.library_id, self.custom))
            if model and model.kind in {"joystick", "tactile"}: c.properties["sim_closed"]="false"
            if model and model.kind == "keypad": c.properties["sim_key"]="none"
            definition=get_definition(c.library_id,self.custom)
            if definition and definition.name == "Zapałka": c.properties["sim_lit"]="false"
        from app.ui.main_window import APP_VERSION
        self.setWindowTitle(f"ElectroSchem {APP_VERSION} — " + self.t("Simulation", "Symulacja") + " — " + self.sheet.name)
        self.log.clear()
        self.reported_warnings = set()
        self.clock.setText("t = 0 s")
        self.scene.clear()
        self.symbols, self.wires, self.glows, self.fault_marks = {}, {}, {}, {}
        self.scopes={}
        from collections import deque
        self.voltage_history=deque(maxlen=1000)
        self.controls={}
        for console in getattr(self, "pi_consoles", {}).values(): console.close(); console.deleteLater()
        self.pi_consoles = {}
        self.input_generation = getattr(self, "input_generation", 0) + 1
        self.pulse_tokens = {}
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
            item = LiveSymbol(c, language="pl" if self.pl else "en", standard=self.sheet.standard, custom_components=self.custom, toggle=self.toggle, motion=lambda cid: self.pulse_input(cid, "sim_active", "true", "false", 500), console=self.toggle_console, held=self.set_simulation_input)
            self.scene.addItem(item)
            self.symbols[c.id] = item
            if item.definition.name=="Oscyloskop":
                item.setZValue(5)
                from collections import deque
                from app.ui.instrument_graphics import scope_dimensions
                item.scope_dimensions=scope_dimensions(self.editor.settings)
                item.scope_samples=deque(maxlen=50000); self.scopes[c.id]=item
                item.scope_bounds=(-2*self.editor.settings.scope_volts_div,2*self.editor.settings.scope_volts_div)
                item.scope_duration=8*self.editor.settings.scope_time_div; item.scope_autoscale=self.editor.settings.scope_autoscale
            if item.definition.symbol == "meter":
                item.console=self.open_scope if item.definition.name=='Oscyloskop' else lambda _: self.open_measurements()
                c.properties["sim_console"]="true"
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
            self.voltage_history=deque(maxlen=max(100,min(5000,200000//max(1,self.circuit.netlist.count))))
            from app.ui.simulation_controls import add_control
            for device in self.circuit.devices:
                if device.kind in {"potentiometer","variable_resistor","keypad","joystick","usb_keyboard",'lab_source','ldr','analog_sensor','ultrasonic'} or device.parameters.get("solar"):
                    self.controls[device.component.id]=add_control(self,device,self.symbols[device.component.id])
            self._interactive_base_distances={d.component.id:float(d.parameters["sim_distance"]) for d in self.circuit.devices if d.kind=="ultrasonic"}
            self._interactive_base_flame_signals={d.component.id:float(d.parameters["sim_signal"]) for d in self.circuit.devices if d.kind=="analog_sensor" and d.component.library_id and "Czujnik Płomienia" in d.parameters.get("name","")}
            self.update_rfid()
            self.update_interactive_inputs(recalculate=False)
            self.log.setPlainText(self.t("Ready. Source negative terminal is the reference when GND is absent. Time shown is simulation time, not wall time.",
                "Gotowe. Bez GND punktem odniesienia jest minus pierwszego źródła. Wyświetlany czas jest czasem symulacji, nie zegara."))
            for cid,message in self.circuit.ignored_warnings.items():
                item=self.symbols[cid]; item.ink_color="#74818c"; item.update()
                item.setToolTip(f"{item.component.reference}: {message}")
                self.log.appendPlainText(f"{item.component.reference}: {message}")
                self.reported_warnings.add(cid)
        self.run_button.setEnabled(self.circuit is not None)
        from app.ui.scope_controls import ScopeControls
        from PySide6.QtWidgets import QGraphicsProxyWidget
        from app.ui.theme import apply_theme
        self.scope_panels={}
        for cid,item in self.scopes.items():
            panel=ScopeControls(self,cid); panel.refresh(); apply_theme(panel,self.editor.settings)
            proxy=QGraphicsProxyWidget(item); proxy.setWidget(panel)
            rect=item.scope_rect(); proxy.setPos(rect.right()+12,rect.top())
            self.scope_panels[cid]=panel
        self.scope_controls=next(iter(self.scope_panels.values()),None)
        self.step_button.setEnabled(self.circuit is not None)
        self.camera_button.setEnabled(any("kamer" in item.definition.name.lower() or "camera" in item.definition.name_en.lower() for item in self.symbols.values()))
        self.buzzer_sound_button.setEnabled(True)
        self.adjust_time_step()
        from app.ui.usb_cable import UsbCable
        self.usb_cables=[]
        for c in self.sheet.components:
            from app.ui.usb_cable import CABLE_IDS
            if c.library_id in CABLE_IDS:
                self.symbols[c.id].hide(); self.glows[c.id].hide()
                self.usb_cables.append(UsbCable(self,c))
        from app.ui.asset_shells import create
        create(self)

    def open_camera(self):
        from app.ui.camera_preview import CameraPreview
        candidates=[item for item in self.symbols.values() if "kamer" in item.definition.name.lower() or "camera" in item.definition.name_en.lower()]
        if not candidates: return
        if self.camera_preview is None:
            self.camera_preview=CameraPreview(self,self.editor.settings.language)
            self.camera_preview.frame.connect(lambda frame:self.camera_frame(candidates,frame))
        self.camera_preview.show(); self.camera_preview.raise_()

    def reconfigure_cables(self):
        from shiboken6 import isValid
        if not isValid(self): return
        from app.simulation.reconfigure import reconfigure
        previous=self.circuit or getattr(self,'_last_cable_circuit',None)
        try: updated=reconfigure(previous,self.sheet,self.custom,'pl' if self.pl else 'en')
        except (ValueError,ArithmeticError) as error:
            self._last_cable_circuit=previous; self.pause(); self.circuit=None
            self.run_button.setEnabled(False); self.step_button.setEnabled(False)
            self.log.appendPlainText(self.t('Cable changed; calculations paused: ','Kabel zmieniony; obliczenia wstrzymane: ')+str(error)); return
        self.circuit=updated; self._last_cable_circuit=None
        self.run_button.setEnabled(True); self.step_button.setEnabled(True)
        # Existing controls must refer to rebuilt devices, not stale node maps.
        by_id={d.component.id:d for d in updated.devices}
        for cid,panel in self.controls.items():
            if cid in by_id:
                if hasattr(panel,'device'): panel.device=by_id[cid]
                if hasattr(panel,'joystick'): panel.joystick.device=by_id[cid]
        if self.measurement_panel:
            self.measurement_panel.reconfigure()
        self.voltage_history.clear()
        self.adjust_time_step(); self.runtime_limit=self.live_step_limit()
        self.log.appendPlainText(self.t('Cable changed; simulation time and device state preserved.','Kabel zmieniony; czas symulacji i stany urządzeń zachowane.'))

    def mute_sound(self,muted):
        if muted:
            if self.buzzer_audio: self.buzzer_audio.stop()
            if self.fault_sound: self.fault_sound.stop()
            if self.measurement_panel and self.measurement_panel.beep: self.measurement_panel.beep.stop()
        elif self.measurement_panel: self.measurement_panel.refresh()

    def cycle_sound(self):
        levels=(1.,.5,.25,0.)
        current=getattr(self,'_sound_cycle_level',1.)
        value=levels[(levels.index(current)+1)%len(levels)]
        self._sound_cycle_level=value
        self.buzzer_sound_button.setChecked(value==0)
        if value: self.set_sound_volume(value)
        icon={1.:'sound_on.png',.5:'volume_50.png',.25:'volume_25.png',0.:'mute.png'}[value]
        self.buzzer_sound_button.setIcon(self.editor._icon(icon))
        self.buzzer_sound_button.setToolTip(self.t('Sound: ','Dźwięk: ')+f'{round(value*100)}%')

    def set_sound_volume(self,value):
        self.sound_volume=float(value)
        if self.buzzer_audio: self.buzzer_audio.audio.setVolume(.30*self.sound_volume)
        if self.fault_sound: self.fault_sound.audio.setVolume((.9 if self.fault_sound.level=='mega' else .45)*self.sound_volume)
        if self.measurement_panel and self.measurement_panel.beep:
            self.measurement_panel.beep.audio.setVolume(.30*self.sound_volume)

    def camera_frame(self,items,frame):
        for item in items:
            if item in self.symbols.values(): item.camera_frame=None if frame.isNull() else frame; item.update()

    def toggle(self, cid):
        if not self.circuit or self.circuit.result.faults: return
        item = self.symbols.get(cid)
        if item and item.definition.name == "Pilot IR":
            receivers=[d for d in self.circuit.devices if d.kind=="digital_sensor" and "Podczerwieni" in d.parameters.get("name","")]
            nearby=[d for d in receivers if (QPointF(d.component.x,d.component.y)-item.scenePos()).manhattanLength()<=260]
            if not nearby:
                self.log.appendPlainText(self.t("No nearby IR receiver in this sandbox.","Brak pobliskiego odbiornika IR w sandboxie.")); return
            receiver=min(nearby,key=lambda d:(QPointF(d.component.x,d.component.y)-item.scenePos()).manhattanLength())
            self.pulse_input(receiver.component.id,"sim_active","true","false",180)
            self.log.appendPlainText(receiver.component.reference+": "+self.t("IR stimulus sent (active-low preview).","Wysłano bodziec IR (podgląd aktywny niskim stanem)."))
            return
        if item and item.definition.name == "Zapałka":
            item.component.properties["sim_lit"] = "false" if item.component.properties.get("sim_lit") == "true" else "true"
            item.update()
            self.update_interactive_inputs()
            return
        if item and item.definition.name == "Karta RFID":
            readers = [d for d in self.circuit.devices if "RC522" in d.parameters.get("name", "")]
            if not readers:
                self.log.appendPlainText(self.t("No connected RC522 reader in this sandbox.", "Brak podłączonego czytnika RC522 w sandboxie.")); return
            reader = min(readers, key=lambda d: (d.component.x-item.component.x)**2+(d.component.y-item.component.y)**2)
            uid = int(str(item.component.properties.get("rfid_id","A1B2C3D4")),16) & 0xffffffff
            present = not item.component.properties.get("rfid_present", False)
            item.component.properties["rfid_present"] = present
            reader.parameters["sim_stimulus"] = uid if present else 0
            item.ink_color = "#67dca0" if present else "#c6d5df"; item.update()
            self.log.appendPlainText(reader.component.reference + ": " + self.t("RFID preview only: ", "Tylko podgląd RFID: ") + (f"UID {uid:08X}" if present else self.t("card removed", "karta usunięta")))
            if not self.timer.isActive(): self.single_step()
            return
        for d in self.circuit.devices:
            if d.component.id == cid:
                if d.kind in {"tactile", "joystick"}:
                    self.pulse_input(cid, "sim_closed", True, False)
                    return
                if d.kind == "multi_switch":
                    next_position=(int(d.parameters["sim_position"])+1)%(int(d.parameters["sim_outputs"])+1)
                    if next_position==0 and d.parameters.get("sim_allow_off","true")=="false": next_position=1
                    d.parameters["sim_position"] = str(next_position)
                    self.symbols[cid].component.properties["sim_position"] = d.parameters["sim_position"]
                    self.symbols[cid].update()
                    if not self.timer.isActive(): self.single_step()
                    return
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
                # A paused simulation otherwise keeps the previous result;
                # module light windows then show stale LED brightness after
                # toggling their internal switch.
                if not self.timer.isActive(): self.single_step()

    def open_scope(self,cid):
        panel=self.scope_panels.get(cid)
        if panel:
            panel.load(); panel.volts_div.setFocus()

    def open_measurements(self):
        if self.measurement_panel is None:
            from app.ui.measurement_panel import MeasurementPanel
            self.measurement_panel=MeasurementPanel(self)
        self.measurement_panel.show(); self.measurement_panel.raise_()

    def set_simulation_input(self,cid,key,value):
        if not self.circuit: return
        device=next((d for d in self.circuit.devices if d.component.id==cid),None)
        if device is None: return
        if device.kind=='lab_source' and key in {'value','sim_max_current','sim_frequency','sim_waveform'}:
            device.parameters[key]=str(value) if key=='sim_waveform' else float(value)
            self.adjust_time_step()
        elif device.kind=="potentiometer" and key=="sim_position":
            device.parameters[key]=max(0,min(1,float(value)))
        elif device.kind=="variable_resistor" and key=="sim_position":
            device.parameters[key]=max(0,min(1,float(value)))
        elif device.kind == "ldr" and key == "sim_light":
            device.parameters[key] = max(.001, min(1000, float(value)))
        elif device.kind == "analog_sensor" and key == "sim_signal":
            device.parameters[key] = max(0, min(1, float(value)))
            if device.parameters.get("name")=="Czujnik Płomienia":
                getattr(self,"_interactive_base_flame_signals",{})[device.component.id]=device.parameters[key]
                self.update_interactive_inputs(recalculate=False)
        elif device.kind == "ultrasonic" and key == "sim_distance":
            device.parameters[key] = max(.02, min(4, float(value)))
        elif device.kind == "joystick" and key in {"sim_x", "sim_y"}:
            device.parameters[key] = max(0, min(1, float(value)))
        elif device.kind in {"tactile", "joystick"} and key == "sim_closed":
            device.closed = bool(value)
            self.symbols[cid].component.properties[key] = "true" if value else "false"
            self.symbols[cid].update()
        elif device.kind == "digital_sensor" and key == "sim_active":
            device.parameters[key] = str(value)
        elif device.parameters.get("solar") and key == "sim_light":
            device.parameters[key] = max(0, min(1, float(value)))
            device.parameters["value"] = device.parameters["sim_open_voltage"] * device.parameters[key]
        elif device.kind=="keypad" and key=="sim_key" and str(value) in {"none",*(str(i) for i in range(16))}:
            device.parameters[key]=str(value)
        else: return
        if not self.circuit.result.faults and not self.timer.isActive(): self.single_step()

    def pulse_input(self, cid, key, active, idle, milliseconds=150):
        generation = self.input_generation
        token = self.pulse_tokens.get((cid, key), 0) + 1
        self.pulse_tokens[cid, key] = token
        self.set_simulation_input(cid, key, active)
        # Even a short click reaches a circuit step before release.
        if self.timer.isActive(): self.advance(single=True)
        def release():
            if generation == self.input_generation and self.pulse_tokens.get((cid, key)) == token:
                self.set_simulation_input(cid, key, idle)
        QTimer.singleShot(milliseconds, release)

    def toggle_console(self, cid):
        if cid.startswith("rfid:"):
            self.update_rfid(); return
        if cid.startswith("match-move:"):
            self.update_interactive_inputs(recalculate=False); return
        if cid.startswith("match:"):
            self.update_interactive_inputs(); return
        if cid.startswith("sensor-prop-move:"):
            self.update_interactive_inputs(recalculate=False); return
        if cid.startswith("sensor-prop:"):
            self.update_interactive_inputs(); return
        console = self.pi_consoles.get(cid)
        if console is None:
            from app.ui.python_console import PythonConsole
            console = PythonConsole(self, cid)
            self.pi_consoles[cid] = console
            self.refresh_consoles()
        if console.isVisible(): console.hide()
        else:
            console.show(); console.raise_(); console.activateWindow()

    def console_script(self, cid):
        if not self.circuit: return None
        return next((part.scripts[cid] for part in self.circuit.parts if cid in part.scripts), None)

    def refresh_consoles(self):
        for panel in getattr(self,"controls",{}).values():
            if hasattr(panel,"refresh_power"): panel.refresh_power()
        for cid, console in self.pi_consoles.items():
            script = self.console_script(cid)
            text = script.serial if script else self.t("No Python program is running. This is simulated program output, not a system shell.", "Brak uruchomionego programu Python. To wyjście symulowanego programu, nie powłoka systemowa.")
            if console.toPlainText() != text:
                console.setPlainText(text)
                console.verticalScrollBar().setValue(console.verticalScrollBar().maximum())
            console.entry.setEnabled(script is not None)

    def update_rfid(self):
        if not self.circuit: return
        cards=[item for item in self.symbols.values() if item.definition.name == "Karta RFID"]
        presented=set()
        for reader in self.circuit.devices:
            if "RC522" not in reader.parameters.get("name", ""): continue
            nearby=[item for item in cards if (item.scenePos()-QPointF(reader.component.x,reader.component.y)).manhattanLength()<260]
            uid=0
            if nearby:
                closest=min(nearby,key=lambda item:(item.scenePos()-QPointF(reader.component.x,reader.component.y)).manhattanLength())
                presented.add(closest)
                try: uid=int(str(closest.component.properties.get("rfid_id", "A1B2C3D4")).replace(" ", ""),16)
                except ValueError: pass
            reader.parameters["sim_stimulus"]=uid & 0xffffffff
        for item in cards:
            item.ink_color="#67dca0" if item in presented else "#c6d5df"; item.update()

    def update_interactive_inputs(self, recalculate=True):
        """Map environmental scene props to the supported sensor models."""
        if not self.circuit: return
        matches=[item for item in self.symbols.values() if item.definition.name == "Zapałka"]
        targets=[item for item in self.symbols.values() if item.definition.name == "Cel ultradźwiękowy"]
        people=[item for item in self.symbols.values() if item.definition.name == "Osoba"]
        changed=False
        for device in self.circuit.devices:
            item=self.symbols.get(device.component.id)
            if not item: continue
            sensor=QPointF(device.component.x,device.component.y)
            if device.kind=="ultrasonic":
                base=getattr(self,"_interactive_base_distances",{}).get(device.component.id,float(device.parameters.get("sim_distance",1.0)))
                distances=[hypot(target.scenePos().x()-sensor.x(),target.scenePos().y()-sensor.y()) for target in targets]
                distance=min(distances,default=400.01)
                measured=max(.02,min(4.0,distance/100)) if distance<=400 else base
                if float(device.parameters.get("sim_distance",base)) != measured:
                    device.parameters["sim_distance"]=measured; changed=True
                panel=self.controls.get(device.component.id)
                if panel and hasattr(panel,"set_distance_value"): panel.set_distance_value(measured)
            elif device.kind=="digital_sensor" and "PIR" in item.definition.name and people:
                active=any(hypot(person.scenePos().x()-sensor.x(),person.scenePos().y()-sensor.y())<=260 for person in people)
                state="true" if active else "false"
                if device.parameters.get("sim_active") != state:
                    device.parameters["sim_active"]=state; changed=True
                item.component.properties["sim_motion_detected"]=state
                item.update()
            elif device.kind=="analog_sensor" and item.definition.name=="Czujnik Płomienia":
                active=any(match.component.properties.get("sim_lit")=="true" and
                           (match.scenePos()-sensor).manhattanLength()<180 for match in matches)
                if matches:
                    signal=.05 if active else getattr(self,"_interactive_base_flame_signals",{}).get(device.component.id,1.0)
                    try: previous=float(device.parameters.get("sim_signal",1.0))
                    except (TypeError,ValueError): previous=None
                    if previous != signal:
                        device.parameters["sim_signal"]=signal
                        changed=True
                item.component.properties["sim_flame_detected"]="true" if active else "false"
                item.update()
        for match in matches: match.update()
        if changed and recalculate and not self.timer.isActive() and not self.circuit.result.faults:
            self.single_step()

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
            self.runtime_dt = self.dt.value()/1000
            self.runtime_limit = self.live_step_limit()
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
                self.runners[device.component.id].send({"op":"step", "seconds":self.running_step(),
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
                result = self.circuit.step(self.running_step())
                self.voltage_history.append((result.time,result.voltages))
                for cid,item in self.scopes.items():
                    a,b=(self.circuit.netlist.pins[cid,i] for i in (0,1))
                    item.scope_samples.append((result.time,result.voltages.get(a,0)-result.voltages.get(b,0)))
                if self.measurement_panel: self.measurement_panel.sample(result)
                if self.measurement_panel and self.measurement_panel.mode.currentData()=="wave":
                    panel=self.measurement_panel
                    a,b=(p.node for p in panel.probes)
                    if a is not None and b is not None: panel.waveform.samples.append((result.time,result.voltages.get(a,0)-result.voltages.get(b,0)))
                # Check every computed step, including those between UI
                # refreshes. Report once per component until Reset, otherwise
                # a changing voltage would flood the log on every time step.
                for cid, message in result.warnings.items():
                    if cid not in self.reported_warnings:
                        self.reported_warnings.add(cid)
                        self.log.appendPlainText(self.t("Warning: ", "Ostrzeżenie: ")+message)
                if result.faults or perf_counter()-started > .012: break
            if self.timer.isActive() and not result.faults:
                target = self.sim_start + (perf_counter_ns()-self.wall_start_ns)/1e9*self.time_scale.value()/100
                if target-self.circuit.time > .04:
                    self.runtime_dt = min(self.runtime_limit, self.runtime_dt*1.5)
                    self.dt.blockSignals(True); self.dt.setValue(self.runtime_dt*1000); self.dt.blockSignals(False)
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
        if self.timer.isActive() and not result.faults and perf_counter()-self.last_render < .05:
            return
        self.last_render = perf_counter()
        self.refresh_consoles()
        if self.measurement_panel: self.measurement_panel.refresh()
        self.clock.setText(f"t = {result.time:.6f} s")
        if self.timer.isActive():
            elapsed = (perf_counter_ns()-self.wall_start_ns)/1e9
            speed = (result.time-self.sim_start)/elapsed*100 if elapsed > .1 else self.time_scale.value()
            self.clock.setText(f"t = {result.time:.6f} s; {self.t('actual', 'rzeczywiście')} {speed:.0f}%")
        for wid, item in self.wires.items():
            voltage = result.voltages.get(self.circuit.netlist.wires[wid], 0)
            color = QColor("#247a4a" if voltage > .01 else "#4d6594" if voltage < -.01 else "#56606b")
            item.setPen(QPen(color,2))
            item.setToolTip(f"{voltage:.6g} V")
        colours = {"red":"#ff4433","green":"#48ff55","blue":"#4488ff","yellow":"#ffee44","orange":"#ff9922","white":"#ffffff","ir":"#9f63cb"}
        for cid, item in self.symbols.items():
            current = result.currents.get(cid)
            control=self.controls.get(cid)
            if control and item.definition.name=='Zasilacz laboratoryjny':
                a,b=(self.circuit.netlist.pins[cid,i] for i in (0,1))
                voltage=result.voltages.get(a,0)-result.voltages.get(b,0)
                device=next(d for d in self.circuit.devices if d.component.id==cid)
                mode='CC' if abs(current or 0)>=device.parameters['sim_max_current']*(1-1e-6) else 'CV'
                control.reading.setText(f'{voltage:.4g} V | {abs(current or 0):.4g} A | {mode}')
            reading=result.readings.get(cid,"")
            if item.definition.symbol == "meter":
                if item.definition.name in {"Omomierz", "Tester ciągłości"}:
                    from app.simulation.measurements import resistance,live_network
                    try:
                        a,b=(self.circuit.netlist.pins[cid,i] for i in (0,1))
                        if live_network(self.sheet,self.circuit.netlist,a,b,self.circuit.devices,result): raise ValueError('live_network')
                        ohms=resistance(self.sheet,self.custom,self.circuit.netlist,a,b,self.circuit.devices)
                        from app.core.units import format_si
                        reading=format_si(ohms,"Ω") if item.definition.name == "Omomierz" else self.t("Closed", "Zwarte") if ohms<10 else self.t("Open", "Rozwarte")
                        if item.definition.name=='Tester ciągłości' and ohms<10:
                            result.sounds['continuity_'+cid]={'frequency':2000,'level':.4}
                    except ValueError: reading=self.t("Active network", "Układ aktywny")
                item.meter_reading=reading; item.update()
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
            was_running=self.timer.isActive()
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
            if level!="mini" and not self.buzzer_sound_button.isChecked():
                try:
                    from app.ui.fault_sound import FaultSound
                    if self.fault_sound is None or getattr(self.fault_sound,"level",level)!=level:
                        if self.fault_sound is not None: self.fault_sound.dispose()
                        self.fault_sound=FaultSound(self,level)
                        self.set_sound_volume(self.sound_volume)
                    self.fault_sound.play()
                except (RuntimeError,OSError) as exc:
                    self.log.appendPlainText(self.t("Audio unavailable: ","Dźwięk niedostępny: ")+str(exc))
            self.fault_animation.start()
            self.log.appendPlainText(self.t("Run resumes healthy circuits; if none remain, it resets this simulation.", "Start wznawia sprawne obwody; jeśli żaden nie pozostał, resetuje symulację."))
            if not self.editor.settings.stop_on_fault and was_running and self.circuit.can_resume:
                self.circuit.acknowledge_faults(); self.run()
                self.log.appendPlainText(self.t('Continuing healthy circuits; the failed island is disabled.','Kontynuuję sprawne obwody; uszkodzona wyspa została odłączona.'))
        else: self.update_audio(result)
        from app.ui.asset_shells import update
        update(self,result)

    def update_audio(self,result):
        sounds=result.sounds if self.timer.isActive() else {k:v for k,v in result.sounds.items() if k.startswith('continuity_')}
        if self.buzzer_sound_button.isChecked(): sounds={}
        if any(s.get('level',0)>0 for s in sounds.values()) and self.buzzer_audio is None:
            try:
                from app.ui.buzzer_audio import BuzzerAudio
                self.buzzer_audio=BuzzerAudio(self)
                self.set_sound_volume(self.sound_volume)
            except (RuntimeError,OSError):
                self.buzzer_sound_button.setChecked(True)
                self.log.appendPlainText(self.t('Audio unavailable.','Dźwięk jest niedostępny.')); return
        if self.buzzer_audio: self.buzzer_audio.update(sounds)

    def _steps_due(self):
        elapsed=max(0,perf_counter_ns()-self.wall_start_ns)/1_000_000_000
        target=self.sim_start+elapsed*self.time_scale.value()/100
        lag = target-self.circuit.time
        due=max(0,int(lag/self.running_step()))
        if target-self.circuit.time > .25:
            self.clock.setToolTip(self.t("Computation is slower than the requested time scale.", "Obliczenia są wolniejsze od zadanej skali czasu."))
        else: self.clock.setToolTip("")
        return due

    def running_step(self):
        return getattr(self, "runtime_dt", self.dt.value()/1000) if self.timer.isActive() else self.dt.value()/1000

    def live_step_limit(self):
        """Adaptive pacing without skipping solver states or signal periods."""
        limit = min(.005, self.circuit.maximum_time_step())
        resistances = [d.parameters["value"] for d in self.circuit.devices if d.kind == "resistor"]
        if resistances:
            for device in self.circuit.devices:
                if device.kind in {"capacitor", "polar_capacitor"}:
                    limit = min(limit, min(resistances)*device.parameters["value"]/4)
                elif device.kind == "inductor":
                    limit = min(limit, device.parameters["value"]/max(resistances)/4)
        return max(self.dt.value()/1000, limit)

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
        if event.key()==Qt.Key.Key_H and not event.modifiers():
            from PySide6.QtWidgets import QLineEdit,QTextEdit,QAbstractSpinBox
            if isinstance(self.focusWidget(),(QLineEdit,QTextEdit,QPlainTextEdit,QAbstractSpinBox)):
                super().keyPressEvent(event); return
            point=self.view.mapToScene(self.view.mapFromGlobal(QCursor.pos()))
            item=next((i for i in self.scene.items(point) if isinstance(i,LiveSymbol)),None)
            if item:
                from app.ui.component_info_dialog import ComponentInfoDialog
                custom=next((d for d in self.custom if d.get('id')==item.definition.id),None)
                ComponentInfoDialog(item.component,item.definition,'pl' if self.pl else 'en',custom,self).exec()
            event.accept(); return
        if event.key()==Qt.Key.Key_Escape:
            self.fault_animation.stop(); self.animate_faults(1)
            if self.fault_sound is not None: self.fault_sound.stop()
            if self.isFullScreen(): self.showMaximized()
            event.accept()
        else: super().keyPressEvent(event)

    def closeEvent(self, event):
        self.pause()
        self.input_generation += 1
        for console in getattr(self, "pi_consoles", {}).values(): console.close()
        if self.measurement_panel: self.measurement_panel.close()
        self.arduino_compiler.stop(); self.compile_queue=[]
        if self.camera_preview is not None: self.camera_preview.close()
        self.fault_animation.stop()
        if self.fault_sound is not None: self.fault_sound.stop()
        self.stop_emulators()
        self.emulators.shutdown()
        super().closeEvent(event)
