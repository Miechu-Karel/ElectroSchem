"""Offline visual alpha4 QA; no API traffic, sounds or user-settings writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt,QPoint
from app.core.models import Project,Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.libraries.built_in import BUILT_IN_ITEMS,get_definition
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
for name in ("arial.ttf","segoeui.ttf","cour.ttf"): QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+name)
app.setFont(QFont("Segoe UI",9))
out=Path(__file__).resolve().parents[1]/"output"/"alpha134"; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",theme="dark",window_mode="windowed",fault_effect="mini"),start_setup=False)
window.resize(1350,860); window.show()
settings=SettingsDialog(window.settings,window); settings.resize(850,650); settings.show()
for i,name in enumerate(("general","editor","ai","simulation")):
    settings.settings_tabs.setCurrentIndex(i); app.processEvents(); settings.grab().save(str(out/("settings-"+name+".png")))
settings.close()
b=Bench(); source=b.add("Kostka zasilająca USB","5","V"); port=b.add("Port USB A"); cable=b.add("Kabel USB"); r=b.add("Rezystor","1","kΩ"); am=b.add("Amperomierz")
for c,pos in zip(b.components,((150,220),(410,240),(730,240),(1060,150),(1060,350))): c.x,c.y=pos
b.connect(source,0,port,"VBUS"); b.connect(source,1,port,"GND")
b.connect(port,"VBUS",cable,"A.VBUS"); b.connect(port,"GND",cable,"A.GND")
b.connect(cable,"B.VBUS",r,0); b.connect(r,1,am,0); b.connect(am,1,cable,"B.GND")
window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.resize(1320,850); sim.single_step(); app.processEvents(); sim.grab().save(str(out/"usb-instruments.png"))
sim.open_measurements(); panel=sim.measurement_panel
for field,cid,pin in ((panel.positive,r.id,0),(panel.negative,r.id,1)):
    field.setCurrentIndex(field.findData(sim.circuit.netlist.pins[cid,pin]))
panel.mode.setCurrentIndex(panel.mode.findData("Ω")); panel.refresh(); app.processEvents(); panel.grab().save(str(out/"resistance.png")); panel.close(); sim.close()
definition=next(d for d in BUILT_IN_ITEMS if d.name=="Karta RFID")
card=window.project.new_component(definition.id,500,500); properties=ComponentPropertiesDialog(card,definition,"pl",window)
properties.resize(850,570); properties.show(); app.processEvents(); properties.grab().save(str(out/"rfid-properties.png")); properties.close()
b=Bench(); board=b.add("Raspberry Pi 5",sim_console="true",sim_source=str(Path(__file__).parent/"fixtures"/"console_input.py"))
board.x,board.y=400,420
window.project=Project(sheets=[Sheet(components=b.components)]); window._rebuild_tabs(); window.show_simulation(); sim=window.simulation_window
sim.single_step(); sim.toggle_console(board.id); app.processEvents(); sim.pi_consoles[board.id].grab().save(str(out/"python-console.png")); sim.grab().save(str(out/"pi-connectors.png")); sim.close()
window._sync_positions(); window._saved_state=window.project.to_dict(); window.close(); app.processEvents()
print("Alpha4 QA screenshots:",out)
