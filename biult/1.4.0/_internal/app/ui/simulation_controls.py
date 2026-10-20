"""Sandbox-only controls; changing them never edits the source schematic."""
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QGridLayout,QLabel,QDial,QPushButton,QGraphicsProxyWidget,QSlider,QLineEdit
from app.ui.theme import apply_theme
from app.core.units import format_si

KEY_LABELS=(("1","2","3","A"),("4","5","6","B"),("7","8","9","C"),("*","0","#","D"))


class JoystickControl(QWidget):
    def __init__(self, window, device):
        super().__init__()
        self.window, self.device = window, device
        self.setFixedSize(150, 150)
        self.position = QPointF(75, 75)
        self.dragging = False
        self.pressed = False

    def press_switch(self):
        self.window.set_simulation_input(self.device.component.id, "sim_closed", True)
        self.pressed = True; self.update()
        panel=self.window.controls.get(self.device.component.id)
        if panel and hasattr(panel,"switch_state"): panel.switch_state.setText(self.window.t("Pressed", "Wciśnięty"))

    def release_switch(self):
        self.window.set_simulation_input(self.device.component.id, "sim_closed", False)
        self.pressed = False; self.update()
        panel=self.window.controls.get(self.device.component.id)
        if panel and hasattr(panel,"switch_state"): panel.switch_state.setText(self.window.t("Released", "Puszczony"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#d4dfe8"), 2))
        painter.drawEllipse(QPointF(75, 75), 60, 60)
        painter.setBrush(QColor("#56d6ff" if self.pressed else "#d4dfe8"))
        painter.drawEllipse(self.position, 24, 24)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.press_switch(); event.accept()
        elif event.button() == Qt.MouseButton.LeftButton and (event.position()-self.position).manhattanLength() < 48:
            self.dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.dragging: return
        delta = event.position()-QPointF(75, 75)
        length = (delta.x()**2+delta.y()**2)**.5
        if length > 60: delta *= 60/length
        self.position = QPointF(75, 75)+delta
        for key, value in (("sim_x", delta.x()), ("sim_y", -delta.y())):
            self.window.set_simulation_input(self.device.component.id, key, .5+value/120)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.release_switch(); event.accept(); return
        if event.button() != Qt.MouseButton.LeftButton: return
        self.dragging = False
        self.position = QPointF(75, 75)
        for key in ("sim_x", "sim_y"): self.window.set_simulation_input(self.device.component.id, key, .5)
        self.update()
        event.accept()


def add_control(window,device,item):
    panel=QWidget(); panel.setFixedWidth(224)
    layout=QVBoxLayout(panel); layout.setContentsMargins(8,8,8,8)
    if device.kind=='lab_source':
        panel.setFixedWidth(340)
        from PySide6.QtWidgets import QDoubleSpinBox,QComboBox,QFormLayout
        form=QFormLayout(); layout.addLayout(form); panel.fields={}
        for key,en,pl,minimum,maximum in (('value','Voltage [V RMS/DC]','Napięcie [V RMS/DC]',0,1000),('sim_max_current','Current limit [A]','Limit prądu [A]',.001,100),('sim_frequency','Frequency [Hz]','Częstotliwość [Hz]',.001,1e6)):
            field=QDoubleSpinBox(); field.setDecimals(3); field.setRange(minimum,maximum); field.setValue(device.parameters[key])
            field.valueChanged.connect(lambda value,k=key:window.set_simulation_input(device.component.id,k,value)); form.addRow(window.t(en,pl),field); panel.fields[key]=field
        shape=QComboBox()
        for key,en,pl in (('dc','DC','Stały'),('sine','Sine','Sinusoida'),('square','Square','Prostokąt'),('triangle','Triangle','Trójkąt'),('sawtooth','Sawtooth','Piła')): shape.addItem(window.t(en,pl),key)
        shape.setCurrentIndex(shape.findData(device.parameters['sim_waveform'])); shape.currentIndexChanged.connect(lambda:window.set_simulation_input(device.component.id,'sim_waveform',shape.currentData()))
        form.addRow(window.t('Waveform','Fala'),shape); panel.fields['sim_waveform']=shape
        panel.reading=QLabel('CV'); layout.addWidget(panel.reading)
    elif device.kind=="potentiometer":
        label=QLabel(); layout.addWidget(label)
        dial=QDial(); dial.setRange(0,1000); dial.setNotchesVisible(True)
        dial.setFixedSize(100,100); dial.setValue(round(device.parameters["sim_position"]*1000))
        layout.addWidget(dial)
        def refresh(value):
            position=value/1000; resistance=device.parameters["value"]
            label.setText(f"{position:.1%}\n1-W: {format_si(resistance*position,'Ω')}\nW-3: {format_si(resistance*(1-position),'Ω')}")
        refresh(dial.value())
        dial.valueChanged.connect(refresh)
        dial.valueChanged.connect(lambda value:window.set_simulation_input(device.component.id,"sim_position",value/1000))
        panel.dial=dial; panel.position_label=label
        part=next(part for part in window.circuit.parts if device in part.devices)
        wiper=device.parameters["pins"]["W"]
        connected=wiper in part.netlist.wires.values() or any(wiper in d.nodes for d in part.devices if d is not device)
        if not connected:
            warning=QLabel(window.t("W is disconnected: resistance 1-3 stays fixed.","W niepodłączony: opór 1-3 jest stały."))
            warning.setWordWrap(True); layout.addWidget(warning)
            panel.wiper_warning=warning
    elif device.kind=="variable_resistor":
        panel.setFixedWidth(140)
        label=QLabel(); layout.addWidget(label)
        dial=QDial(); dial.setRange(0,1000); dial.setNotchesVisible(True)
        dial.setFixedSize(100,100); dial.setValue(round(device.parameters["sim_position"]*1000))
        layout.addWidget(dial)
        def refresh(value):
            low=float(device.parameters["sim_min_resistance"]); high=float(device.parameters["sim_max_resistance"])
            resistance=low+(high-low)*value/1000
            label.setText(format_si(resistance,"Ω"))
        refresh(dial.value())
        dial.valueChanged.connect(refresh)
        dial.valueChanged.connect(lambda value:window.set_simulation_input(device.component.id,"sim_position",value/1000))
        panel.dial=dial; panel.position_label=label
    elif device.kind == "joystick":
        panel.joystick = JoystickControl(window, device)
        layout.addWidget(panel.joystick)
        panel.switch_button = QPushButton("SW")
        panel.switch_button.pressed.connect(panel.joystick.press_switch)
        panel.switch_button.released.connect(panel.joystick.release_switch)
        layout.addWidget(panel.switch_button)
        panel.switch_state = QLabel(window.t("Released", "Puszczony"))
        layout.addWidget(panel.switch_state)
        panel.switch_button.pressed.connect(lambda:panel.switch_state.setText(window.t("Pressed", "Wciśnięty")))
        panel.switch_button.released.connect(lambda:panel.switch_state.setText(window.t("Released", "Puszczony")))
        note = QLabel(window.t("LMB: move stick. RMB: momentary switch.", "LPM: przesuń gałkę. PPM: chwilowy styk."))
        note.setWordWrap(True); layout.addWidget(note)
    elif device.kind == "usb_keyboard":
        from app.ui.usb_keyboard import UsbKeyboard
        panel=UsbKeyboard(window,device)
    elif device.kind == "ldr":
        label = QLabel(); layout.addWidget(label)
        panel.slider = QSlider(Qt.Orientation.Horizontal)
        panel.slider.setRange(0, 100)
        panel.slider.setValue(max(0,min(100,round(float(device.parameters["sim_light"])*100))))
        panel.slider.setToolTip(window.t("Illumination from darkness to the reference level.", "Oświetlenie od ciemności do poziomu odniesienia."))
        layout.addWidget(panel.slider)
        def illumination(value):
            label.setText(window.t("Illumination: ", "Oświetlenie: ")+f"{value}%")
            window.set_simulation_input(device.component.id, "sim_light", max(.001,value/100))
        panel.slider.valueChanged.connect(illumination)
        label.setText(window.t("Illumination: ", "Oświetlenie: ")+f"{panel.slider.value()}%")
    elif device.kind == "analog_sensor":
        label=QLabel(); layout.addWidget(label)
        panel.slider=QSlider(Qt.Orientation.Horizontal); panel.slider.setRange(0,100)
        panel.slider.setValue(round(float(device.parameters["sim_signal"])*100))
        layout.addWidget(panel.slider)
        def signal(value):
            label.setText(window.t("Sensor signal: ", "Sygnał czujnika: ")+f"{value}%")
            window.set_simulation_input(device.component.id,"sim_signal",value/100)
        panel.slider.valueChanged.connect(signal)
        label.setText(window.t("Sensor signal: ", "Sygnał czujnika: ")+f"{panel.slider.value()}%")
        note=QLabel(window.t("Direct stimulus; no gas, sound or moisture conversion model.","Bodziec bezpośredni; brak przelicznika stężenia gazu, dźwięku i wilgotności."))
        note.setWordWrap(True); layout.addWidget(note)
    elif device.kind == "ultrasonic":
        label=QLabel(); layout.addWidget(label)
        panel.slider=QSlider(Qt.Orientation.Horizontal); panel.slider.setRange(2,400)
        panel.slider.setValue(max(2,min(400,round(float(device.parameters["sim_distance"])*100))))
        layout.addWidget(panel.slider)
        def distance(value):
            label.setText(window.t("Distance: ","Odległość: ")+f"{value/100:.2f} m")
            window.set_simulation_input(device.component.id,"sim_distance",value/100)
        panel.slider.valueChanged.connect(distance)
        def set_distance_value(value):
            blocked=panel.slider.blockSignals(True)
            panel.slider.setValue(max(2,min(400,round(value*100))))
            panel.slider.blockSignals(blocked)
            label.setText(window.t("Distance: ","Odległość: ")+f"{value:.2f} m")
        panel.set_distance_value=set_distance_value
        label.setText(window.t("Distance: ","Odległość: ")+f"{panel.slider.value()/100:.2f} m")
        note=QLabel(window.t("A nearby movable ultrasonic target overrides this setting.","Ustawienie zastępuje pobliski ruchomy cel ultradźwiękowy."))
        note.setWordWrap(True); layout.addWidget(note)
    elif device.parameters.get("solar"):
        label = QLabel(); layout.addWidget(label)
        panel.slider = QSlider(Qt.Orientation.Horizontal)
        panel.slider.setRange(0, 100)
        panel.slider.setValue(round(device.parameters["sim_light"]*100))
        layout.addWidget(panel.slider)
        def sunlight(value):
            label.setText(window.t("Illumination: ", "Oświetlenie: ")+f"{value}%")
            window.set_simulation_input(device.component.id, "sim_light", value/100)
        panel.slider.valueChanged.connect(sunlight)
        label.setText(window.t("Illumination: ", "Oświetlenie: ")+f"{panel.slider.value()}%")
    else:
        grid=QGridLayout(); layout.addLayout(grid); panel.keys=[]
        for row,labels in enumerate(KEY_LABELS):
            for col,label in enumerate(labels):
                key=row*4+col; button=QPushButton(label); button.setFixedSize(44,38)
                button.pressed.connect(lambda index=key:window.set_simulation_input(device.component.id,"sim_key",str(index)))
                button.released.connect(lambda:window.set_simulation_input(device.component.id,"sim_key","none"))
                grid.addWidget(button,row,col); panel.keys.append(button)
        note=QLabel(window.t("Hold a key to close its contact; release to open.","Przytrzymaj klawisz, aby zewrzeć styk; puść, aby go rozewrzeć.")); note.setWordWrap(True)
        layout.addWidget(note)
    apply_theme(panel,window.editor.settings)
    panel.adjustSize()
    proxy=QGraphicsProxyWidget(item); proxy.setWidget(panel)
    panel.graphics_proxy=proxy
    item.setZValue(3)
    proxy.setPos(item._hit_rect.center().x()-panel.width()/2,item._hit_rect.top()-panel.height()-12)
    return panel
