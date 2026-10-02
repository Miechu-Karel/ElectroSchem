"""Read-only LCD project pacing and visual check; no camera or audio."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
from time import perf_counter
from PySide6.QtCore import QEventLoop,QTimer,Qt
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","segoeui.ttf","cour.ttf"):
    QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts")/name))
app.setFont(QFont("Segoe UI",9))
root=Path(__file__).resolve().parents[1]
out=root/"output/rc4"; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",theme="dark",fault_effect="mini"),start_setup=False)
window.project=load_project("C:/Users/miesz/Documents/EtectroSchem Projeky/Przykładowy LCD.els")
for c in window.project.sheets[0].components:
    if "raspberry" in c.library_id:
        c.properties.update(sim_source=str(root/"examples/lcd_raspberry.py"),sim_mode="gpio")
window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.resize(1200,850)
sim.dt.setValue(.1); sim.time_scale.setValue(100)
loop=QEventLoop(); QTimer.singleShot(3000,loop.quit)
started=perf_counter(); sim.run(); loop.exec(); sim.pause()
elapsed=perf_counter()-started
print(f"Step={sim.dt.value()} ms; real={elapsed:.3f} s; simulated={sim.circuit.time:.3f} s; ratio={100*sim.circuit.time/elapsed:.1f}%")
sim.grab().save(str(out/"lcd-circuit.png"))
lcd=next(item for item in sim.symbols.values() if item.is_lcd)
sim.view.fitInView(lcd.sceneBoundingRect().adjusted(-20,-20,20,20),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); sim.view.grab().save(str(out/"lcd-detail.png"))
print(sim.circuit.result.displays)
window._sync_positions(); window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
