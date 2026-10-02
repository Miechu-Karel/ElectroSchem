"""Sandbox-only controls; changing them never edits the source schematic."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QGridLayout,QLabel,QDial,QPushButton,QGraphicsProxyWidget
from app.ui.theme import apply_theme

KEY_LABELS=(("1","2","3","A"),("4","5","6","B"),("7","8","9","C"),("*","0","#","D"))


def add_control(window,device,item):
    panel=QWidget(); panel.setFixedWidth(224)
    layout=QVBoxLayout(panel); layout.setContentsMargins(8,8,8,8)
    if device.kind=="potentiometer":
        label=QLabel(); layout.addWidget(label)
        dial=QDial(); dial.setRange(0,1000); dial.setNotchesVisible(True)
        dial.setFixedSize(100,100); dial.setValue(round(device.parameters["sim_position"]*1000))
        layout.addWidget(dial)
        def refresh(value):
            position=value/1000; resistance=device.parameters["value"]
            label.setText(f"{position:.1%}\n1-W: {resistance*position:.4g} Ω\nW-3: {resistance*(1-position):.4g} Ω")
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
    else:
        grid=QGridLayout(); layout.addLayout(grid); panel.keys=[]
        for row,labels in enumerate(KEY_LABELS):
            for col,label in enumerate(labels):
                key=row*4+col; button=QPushButton(label); button.setFixedSize(44,38)
                button.pressed.connect(lambda index=key:window.set_simulation_input(device.component.id,"sim_key",str(index)))
                button.released.connect(lambda:window.set_simulation_input(device.component.id,"sim_key","none"))
                grid.addWidget(button,row,col); panel.keys.append(button)
        note=QLabel(window.t("Hold a key to close its contact.","Przytrzymaj klawisz, aby zewrzeć styk.")); note.setWordWrap(True)
        layout.addWidget(note)
    apply_theme(panel,window.editor.settings)
    panel.adjustSize()
    proxy=QGraphicsProxyWidget(item); proxy.setWidget(panel)
    item.setZValue(3)
    proxy.setPos(item._hit_rect.center().x()-112,item._hit_rect.top()-panel.height()-12)
    return panel
