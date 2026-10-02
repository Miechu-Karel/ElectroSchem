"""LCD and dark-paper screenshots; never access a physical camera."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","segoeui.ttf","cour.ttf","courbd.ttf"):
    path=Path("C:/Windows/Fonts")/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
root=Path(__file__).resolve().parents[1]; out=root/"output/alfa11"; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",theme="dark",window_mode="windowed",fault_effect="mini"),start_setup=False)
window.project=load_project("C:/Users/miesz/Documents/EtectroSchem Projeky/Przykładowy LCD.els")
for c in window.project.sheets[0].components:
    if "raspberry" in c.library_id: c.properties.update(sim_source=str(root/"examples/lcd_raspberry.py"),sim_mode="gpio")
window._rebuild_tabs(); window.resize(1200,820); window.show()
for _ in range(8): app.processEvents()
window.grab().save(str(out/"dark-paper.png"))
window.show_simulation(); sim=window.simulation_window; sim.advance(single=True); sim.resize(1200,800)
for _ in range(8): app.processEvents()
sim.grab().save(str(out/"lcd-circuit.png"))
lcd=next(item for item in sim.symbols.values() if "LCD" in item.definition.name)
sim.view.fitInView(lcd.sceneBoundingRect().adjusted(-40,-30,40,30),Qt.AspectRatioMode.KeepAspectRatio)
for _ in range(8): app.processEvents()
sim.view.grab().save(str(out/"lcd-detail.png"))
from app.ui.camera_preview import CameraPreview
camera=CameraPreview(sim,"pl"); camera.show(); app.processEvents()
camera.grab().save(str(out/"camera-off.png")); camera.close()
window._sync_positions(); window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
print(out)
