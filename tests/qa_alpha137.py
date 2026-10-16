"""Offline visual QA for alpha7; no sound, network or preference writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from app.core.models import Project, Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.simulation.examples import example
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
for font in ("arial.ttf","segoeui.ttf"): QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+font)
app.setFont(QFont("Segoe UI",9))
out=Path(__file__).resolve().parents[1]/"output"/"alpha137"; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",theme="dark",ai_provider="none",window_mode="windowed",fault_effect="mini"),start_setup=False)
window.resize(1350,860); window.show()
window.project=Project(sheets=[example("usb_c_led")]); window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.resize(1350,860); sim.buzzer_sound_button.setChecked(True)
for _ in range(10): sim.single_step()
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-40,-40,40,40),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); sim.grab().save(str(out/"usb-c-led.png")); sim.close()
b=Bench(); board=b.add("Raspberry Pi 5"); board.x,board.y=380,420
bridge=b.add("Prostownik AC/DC"); bridge.x,bridge.y=670,200
inverter=b.add("Przetwornica DC/AC"); inverter.x,inverter.y=670,340
window.project=Project(sheets=[Sheet(components=b.components)]); window._rebuild_tabs()
view=window._current_view(); view.fitInView(view.scene.itemsBoundingRect(),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); window.grab().save(str(out/"board-and-converters.png"))
b=Bench(); resistor=b.add("Rezystor","330","Ω"); led=b.add("Dioda LED 3mm")
resistor.x,resistor.y=440,240; led.x,led.y=640,240; b.connect(resistor,1,led,0)
window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.resize(1350,860); sim.buzzer_sound_button.setChecked(True); sim.single_step(); sim.open_measurements()
panel=sim.measurement_panel
panel.positive.setCurrentIndex(panel.positive.findData(panel.netlist.pins[resistor.id,0]))
panel.negative.setCurrentIndex(panel.negative.findData(panel.netlist.pins[led.id,1]))
panel.mode.setCurrentIndex(panel.mode.findData("Ω")); panel.refresh()
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-40,-40,40,40),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); panel.grab().save(str(out/"led-resistance.png")); sim.grab().save(str(out/"unpowered-led.png"))
sim.close(); window._saved_state=window.project.to_dict(); window.close()
print(out)
