"""Live terminal probes and a bounded waveform history."""
from collections import deque
from math import isfinite,sqrt
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox,QDoubleSpinBox,QCheckBox

class Waveform(QWidget):
    def __init__(self):
        super().__init__(); self.samples=deque(maxlen=50000); self.bounds=(-10.,10.); self.duration=.08; self.autoscale=False; self.setMinimumSize(500,260)
    def paintEvent(self,event):
        from app.ui.instrument_graphics import draw_waveform
        p=QPainter(self); draw_waveform(p,self.rect(),self.samples,self.bounds,self.duration,self.autoscale)

def rms(samples,period):
    """Time-weighted RMS, with an interpolated exact window boundary."""
    if not samples: return 0.
    boundary=samples[-1][0]-period; data=[]
    for entry in reversed(samples):
        data.append(entry)
        if entry[0]<=boundary: break
    data.reverse()
    end=data[-1][0]; start=max(data[0][0],end-period); integral=duration=0.
    for (ta,va),(tb,vb) in zip(data,data[1:]):
        if tb<=start or tb<=ta: continue
        a=max(start,ta); fraction=(a-ta)/(tb-ta); v=va+(vb-va)*fraction
        integral+=(v*v+vb*vb)/2*(tb-a); duration+=tb-a
    return sqrt(max(0,integral/duration)) if duration else abs(data[-1][1])

class MeasurementPanel(QWidget):
    def __init__(self,window):
        super().__init__(window,Qt.WindowType.Window); self.window=window; self.setWindowIcon(window.windowIcon())
        self.setWindowTitle(window.t("Measurement tools","Narzędzia pomiarowe")); self.resize(640,460)
        layout=QVBoxLayout(self); layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setSpacing(8)
        form=QFormLayout(); self.form=form; form.setVerticalSpacing(6); layout.addLayout(form)
        self.history=deque(maxlen=50000); self.beep=None; self.audio_unavailable=False
        self.mode=QComboBox()
        for key,en,pl in (("V","Voltage","Napięcie"),("A","Branch current","Natężenie w gałęzi"),("Ω","Resistance","Opór"),("continuity","Continuity","Stykanie"),("wave","Waveform","Przebieg")):
            self.mode.addItem(window.t(en,pl),key)
        self.positive=QComboBox(); self.negative=QComboBox(); self.branch=QComboBox()
        from app.core.assets import expand_assets,with_asset_dependencies
        from app.simulation.netlist import build_netlist
        self.custom=with_asset_dependencies(window.custom)
        self.measurement_sheet=window.circuit.sheet if window.circuit else expand_assets(window.sheet,self.custom)
        self.netlist=build_netlist(self.measurement_sheet,self.custom)
        self.terminals=[]
        from app.libraries.built_in import get_definition
        for c in window.sheet.components:
            definition=window.symbols[c.id].definition
            positions=window.symbols[c.id].pin_positions()
            if not positions: continue
            self.branch.addItem(c.reference,c.id)
            for i,pin in enumerate(definition.pins):
                node=self.netlist.pins.get((c.id,i))
                if node is None:
                    raw=next((d for d in self.custom if d["id"]==c.library_id and "asset" in d),None)
                    if raw and i<len(raw["asset"]["exports"]):
                        from uuid import uuid5,NAMESPACE_URL
                        port=raw["asset"]["exports"][i]
                        internal=str(uuid5(NAMESPACE_URL,c.id+":"+str(port["component"])))
                        node=self.netlist.pins.get((internal,port["pin"]))
                    if node is None: continue
                    self.netlist.pins[c.id,i]=node
                text=c.reference+"."+pin.name
                self.terminals.append((positions[i],node,text))
                self.positive.addItem(text,node); self.negative.addItem(text,node)
        self.positive.setCurrentIndex(-1); self.negative.setCurrentIndex(-1)
        form.addRow(window.t("Mode","Tryb"),self.mode); form.addRow("+",self.positive); form.addRow("−",self.negative)
        form.addRow(window.t("Component branch","Gałąź elementu"),self.branch)
        self.volts_div=QDoubleSpinBox(); self.volts_div.setDecimals(3); self.volts_div.setRange(.001,1e6); self.volts_div.setValue(window.editor.settings.scope_volts_div)
        self.offset=QDoubleSpinBox(); self.offset.setDecimals(3); self.offset.setRange(-1e6,1e6)
        form.addRow(window.t('V/division','V/działkę'),self.volts_div); form.addRow(window.t('Vertical centre [V]','Środek pionowy [V]'),self.offset)
        self.time_div=QDoubleSpinBox(); self.time_div.setDecimals(6); self.time_div.setRange(.000001,100); self.time_div.setSingleStep(.01); self.time_div.setValue(window.editor.settings.scope_time_div)
        self.auto_scale=QCheckBox(window.t('Automatic voltage and time scales','Automatyczne skale napięcia i czasu')); self.auto_scale.setChecked(window.editor.settings.scope_autoscale)
        form.addRow(window.t('Time/division [s]','Czas/działkę [s]'),self.time_div); form.addRow(self.auto_scale)
        self.reading=QLabel(); layout.addWidget(self.reading)
        self.note=QLabel(window.t("Drag the red and black probes onto pins or wires. Voltage is measured in parallel with the part; AC voltage shows RMS, while the waveform shows instantaneous voltage. Current is measured in series: open the branch and insert the ammeter. Never connect an ammeter in parallel across a source. Resistance requires no voltage or load current; lamp resistance is its rated hot resistance. Diodes and LEDs: apparent resistance at 1 mA, test range 3 V; reversing probes may give OL.",
            "Przeciągnij czerwoną i czarną sondę na piny lub przewody. Napięcie mierzy się równolegle do elementu; dla AC odczyt pokazuje RMS, a przebieg — wartość chwilową. Prąd mierzy się szeregowo: przerwij gałąź i włącz w nią amperomierz. Nigdy nie podłączaj amperomierza równolegle do źródła. Opór mierzymy bez napięcia i prądu obciążenia; dla żarówki jest to opór znamionowy gorącego włókna. LED i diody: opór pozorny przy 1 mA, zakres testu 3 V; po odwróceniu sond może być OL."))
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.waveform=Waveform(); layout.addWidget(self.waveform)
        from app.ui.instrument_graphics import scope_dimensions
        width,height=scope_dimensions(window.editor.settings); self.waveform.setMinimumSize(width,height)
        self.volts_div.valueChanged.connect(self.scale_changed); self.offset.valueChanged.connect(self.scale_changed)
        self.time_div.valueChanged.connect(self.scale_changed); self.auto_scale.toggled.connect(self.scale_changed); self.scale_changed()
        from app.ui.instrument_graphics import Multimeter,Probe
        self.instrument=Multimeter(self); self.probes=[Probe(self,0),Probe(self,1)]
        self.cords=[window.scene.addPath(__import__("PySide6.QtGui",fromlist=["QPainterPath"]).QPainterPath()) for _ in range(2)]
        window.scene.addItem(self.instrument)
        for probe in self.probes: window.scene.addItem(probe)
        center=window.view.mapToScene(window.view.viewport().rect().center())
        self.instrument.setPos(center+QPointF(-170,-100))
        for i,probe in enumerate(self.probes):
            field=self.positive if i==0 else self.negative
            probe.setPos(center+QPointF(20+40*i,20))
            probe.node=None; probe.label=''
        self.positive.setCurrentIndex(-1); self.negative.setCurrentIndex(-1)
        for field in (self.mode,self.positive,self.negative,self.branch): field.currentIndexChanged.connect(self.changed)
        from app.ui.theme import apply_theme
        apply_theme(self,window.editor.settings); self.changed(); self.resize(640,220)
    def reconfigure(self):
        """Rebind nodes after cable edits; keep instrument and probe positions."""
        connected=[probe.node is not None for probe in self.probes]
        from app.simulation.netlist import build_netlist
        self.measurement_sheet=self.window.circuit.sheet
        self.netlist=build_netlist(self.measurement_sheet,self.custom)
        self.terminals=[]
        for field in (self.positive,self.negative): field.blockSignals(True); field.clear()
        for component in self.window.sheet.components:
            symbol=self.window.symbols.get(component.id)
            if symbol is None: continue
            for index,point in enumerate(symbol.pin_positions()):
                node=self.netlist.pins.get((component.id,index))
                if node is None:
                    raw=next((d for d in self.custom if d['id']==component.library_id and 'asset' in d),None)
                    if raw and index<len(raw['asset']['exports']):
                        from uuid import uuid5,NAMESPACE_URL
                        port=raw['asset']['exports'][index]
                        node=self.netlist.pins.get((str(uuid5(NAMESPACE_URL,component.id+':'+str(port['component']))),port['pin']))
                        if node is not None: self.netlist.pins[component.id,index]=node
                if node is None: continue
                label=component.reference+'.'+symbol.definition.pins[index].name
                self.terminals.append((point,node,label))
                for field in (self.positive,self.negative): field.addItem(label,node)
        for field in (self.positive,self.negative): field.setCurrentIndex(-1); field.blockSignals(False)
        for probe in self.probes: probe.node=None; probe.label=''
        for probe,was_connected in zip(self.probes,connected):
            if was_connected: self.probe_moved(probe)
        self.waveform.samples.clear(); self.history.clear(); self.refresh(); self.draw_cords()

    def changed(self,*_):
        for probe,field in zip(self.probes,(self.positive,self.negative)):
            if field.currentIndex()>=0 and field.currentIndex()<len(self.terminals):
                point,node,label=self.terminals[field.currentIndex()]
                probe.node=node; probe.label=label
                probe.blockSignals(True); probe.setPos(point); probe.blockSignals(False)
            else:
                probe.node=None; probe.label=''; probe.update()
        self.waveform.samples.clear(); self.restore_history(); self.refresh()
    def scale_changed(self,*_):
        center=self.offset.value(); span=2*self.volts_div.value()
        self.waveform.bounds=(center-span,center+span); self.waveform.update()
        self.waveform.duration=8*self.time_div.value(); self.waveform.autoscale=self.auto_scale.isChecked()
        self.volts_div.setEnabled(not self.auto_scale.isChecked()); self.offset.setEnabled(not self.auto_scale.isChecked())
        self.time_div.setEnabled(not self.auto_scale.isChecked())
        for item in self.window.scopes.values():
            item.scope_bounds=self.waveform.bounds; item.scope_duration=self.waveform.duration; item.scope_autoscale=self.waveform.autoscale; item.update()
    def draw_cords(self):
        if not hasattr(self,"cords"): return
        from app.ui.instrument_graphics import draw_cord
        for i,probe in enumerate(self.probes): draw_cord(self.cords[i],self.instrument.pos()+QPointF(48 if i==0 else 102,199),probe.pos(),"#f24e58" if i==0 else "#a9b3bd")
    def probe_moved(self,probe,snap=False):
        pos=probe.pos(); nearest=min(self.terminals,key=lambda x:(x[0]-pos).manhattanLength(),default=None)
        target=nearest if nearest and (nearest[0]-pos).manhattanLength()<24 else None
        if target is None:
            best=12.
            for wire in self.window.sheet.wires:
                points=wire.points or [[wire.start_x,wire.start_y],[wire.end_x,wire.end_y]]
                for start,end in zip(points,points[1:]):
                    a,b=QPointF(*start),QPointF(*end); delta=b-a; length=delta.x()**2+delta.y()**2
                    if not length: continue
                    ratio=max(0,min(1,((pos-a).x()*delta.x()+(pos-a).y()*delta.y())/length)); point=a+delta*ratio
                    distance=(point-pos).manhattanLength()
                    if distance<best:
                        best=distance; target=(point,self.netlist.wires[wire.id],wire.id)
        probe.node=target[1] if target else None; probe.label=target[2] if target else ""
        if snap and target and (probe.pos()-target[0]).manhattanLength()>.01: probe.setPos(target[0])
        field=self.positive if probe.index==0 else self.negative
        field.blockSignals(True); field.setCurrentIndex(field.findData(probe.node)); field.blockSignals(False)
        self.waveform.samples.clear(); self.restore_history(); probe.update()
        if hasattr(self,"reading"): self.refresh()
    def showEvent(self,event):
        super().showEvent(event)
        for item in [self.instrument,*self.probes,*self.cords]: item.show()
        self.refresh()
    def closeEvent(self,event):
        if self.beep: self.beep.stop()
        for item in [self.instrument,*self.probes,*self.cords]: item.hide()
        super().closeEvent(event)
    def refresh(self):
        w=self.window; result=w.circuit.result if w.circuit else None
        mode=self.mode.currentData(); a=self.probes[0].node; b=self.probes[1].node
        self.instrument.update()
        self.waveform.setVisible(mode=="wave"); self.form.setRowVisible(self.branch,mode=="A")
        self.form.setRowVisible(self.volts_div,mode=='wave'); self.form.setRowVisible(self.offset,mode=='wave')
        self.form.setRowVisible(self.time_div,mode=='wave'); self.form.setRowVisible(self.auto_scale,mode=='wave')
        if mode!="continuity" and self.beep: self.beep.stop()
        if a is None or b is None:
            if self.beep: self.beep.stop()
            self.reading.setText(w.t("Connect probes","Podłącz sondy")); return
        if mode in {"Ω","continuity"}:
            if result and self.live_branch_current(a,b,result):
                if self.beep: self.beep.stop()
                self.reading.setText(w.t("Disconnect power before measuring resistance.","Odłącz zasilanie przed pomiarem oporu.")); return
            from app.simulation.measurements import resistance
            try:
                value=resistance(self.measurement_sheet,self.custom,self.netlist,a,b,w.circuit.devices if w.circuit else ())
                from app.core.units import format_si
                formatted=format_si(value,"Ω") if isfinite(value) else "OL"
                self.reading.setText((w.t("Connected","Zwarte") if value<10 else w.t("Open","Rozwarte"))+f" ({formatted})" if mode=="continuity" else formatted)
                self.continuity_beep(mode=="continuity" and value<10)
            except (ValueError,KeyError):
                if self.beep: self.beep.stop()
                self.reading.setText(w.t("Unsupported resistance measurement: isolate the passive network and enter lamp ratings.","Nieobsługiwany pomiar oporu: odłącz układy aktywne i uzupełnij parametry znamionowe żarówki."))
        elif result:
            if mode=="A":
                value=None
                for device in w.circuit.devices:
                    nodes=[self.netlist.pins.get((device.component.id,i)) for i in range(len(device.nodes))]
                    if len(nodes)==2 and (a,b) in ((nodes[0],nodes[1]),(nodes[1],nodes[0])):
                        current=result.currents.get(device.component.id)
                        if current is not None: value=current*(1 if a==nodes[0] else -1); break
            else: value=result.voltages.get(a,0)-result.voltages.get(b,0)
            frequencies=[s.parameters.get("sim_frequency",0) for s in w.circuit.sources if s.kind=="ac"]
            frequencies=[f for f in frequencies if f>0]
            ac=mode=="V" and bool(frequencies)
            displayed=rms(self.history,2/min(frequencies)) if ac and self.history else value
            self.reading.setText("—" if displayed is None else f"{displayed:.6g} {'A' if mode=='A' else 'V RMS' if ac else 'V'}")
            if mode=="wave" and isfinite(value) and (not self.waveform.samples or self.waveform.samples[-1][0]!=result.time):
                self.waveform.samples.append((result.time,value)); self.waveform.update()
            if mode=="wave": self.waveform.update()
        else: self.reading.setText(w.t("No running circuit","Brak uruchomionego układu"))

    def sample(self,result):
        a,b=(p.node for p in self.probes)
        if a is None or b is None: return
        self.history.append((result.time,result.voltages.get(a,0)-result.voltages.get(b,0)))
    def restore_history(self):
        self.history.clear()
        a,b=(p.node for p in self.probes)
        if a is None or b is None: return
        for t,voltages in getattr(self.window,"voltage_history",()):
            self.history.append((t,voltages.get(a,0)-voltages.get(b,0)))
        self.waveform.samples.extend(list(self.history)[-50000:]); self.waveform.update()
    def live_branch_current(self,a,b,result):
        from app.simulation.measurements import live_network
        return live_network(self.measurement_sheet,self.netlist,a,b,self.window.circuit.devices,result)
    def continuity_beep(self,on):
        on=on and self.isVisible() and not self.window.buzzer_sound_button.isChecked()
        if on and self.beep is None and not self.audio_unavailable:
            try:
                from app.ui.buzzer_audio import BuzzerAudio
                self.beep=BuzzerAudio(self)
                self.beep.audio.setVolume(.30*getattr(self.window,'sound_volume',1.0))
            except (RuntimeError,OSError): self.audio_unavailable=True
        if self.beep:
            self.beep.update({"continuity":{"frequency":2000,"level":.4}} if on else {})
