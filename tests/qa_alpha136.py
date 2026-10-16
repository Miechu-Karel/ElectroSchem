"""Offline visual QA; no API calls, sound playback or settings writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import QPointF
from app.core.models import Project,Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.simulation.examples import example
from app.canvas.connector_art import socket_regions
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","segoeui.ttf"): QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+name)
app.setFont(QFont("Segoe UI",9))
out=Path(__file__).resolve().parents[1]/"output"/"alpha136"; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",theme="dark",window_mode="windowed",fault_effect="mini"),start_setup=False)
window.resize(1350,860); window.show(); app.processEvents()
menu=QMenu(window); window._populate_library_menu(menu,5,None); menu.show(); app.processEvents(); menu.grab().save(str(out/"instrument-menu.png")); menu.close()
window.project=Project(sheets=[example("meter_ac")]); window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.resize(1350,860); sim.buzzer_sound_button.setChecked(True)
for _ in range(1200): sim.single_step()
sim.open_measurements(); app.processEvents(); sim.measurement_panel.grab().save(str(out/"meter-compact.png")); sim.grab().save(str(out/"scope-probes.png"))
sim.measurement_panel.mode.setCurrentIndex(4); app.processEvents(); sim.measurement_panel.grab().save(str(out/"meter-wave.png")); sim.measurement_panel.close()
b=Bench(); brick=b.add("Kostka zasilająca USB","5","V"); cable=b.add("Kabel USB",usb_a_target=brick.id); port=b.add("Port USB C"); gold=b.add("Goldpin"); switch=b.add("Przełącznik wielostopniowy",sim_outputs="10")
for c,pos in zip(b.components,((180,260),(420,270),(700,260),(250,470),(570,490))): c.x,c.y=pos
cable.properties["usb_b_target"]=port.id
window.project=Project(sheets=[Sheet(components=b.components)]); window._rebuild_tabs(); sim.reload()
for visual in sim.usb_cables:
    for plug in visual.plugs:
        target=visual.component.properties.get("usb_"+plug.side.lower()+"_target")
        point=next((p for cid,p in visual.targets(plug) if cid==target),None)
        if point: plug.setPos(point)
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-70,-70,70,70),__import__("PySide6.QtCore",fromlist=["Qt"]).Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); sim.grab().save(str(out/"usb-sockets-goldpin-switch.png")); window.grab().save(str(out/"editor.png"))
window._sync_positions(); window._saved_state=window.project.to_dict(); sim.close(); window.close()
print(out)
