"""Read-only supplied-project screenshots; no sound playback or file edits."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","segoeui.ttf","cour.ttf"):
    QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts")/name))
app.setFont(QFont("Segoe UI",9))
out=Path(__file__).resolve().parents[1]/"output/rc6"; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(theme="dark",language="pl",fault_effect="mini"),start_setup=False)
window.project=load_project("C:/Users/miesz/Documents/EtectroSchem Projeky/Testy Przełączników.els")
window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.buzzer_sound_button.setChecked(False); sim.resize(1150,850)
for _ in range(5): app.processEvents()
for kind in ("potentiometer","keypad"):
    device=next(d for d in sim.circuit.devices if d.kind==kind)
    item=sim.symbols[device.component.id]
    rect=item.mapRectToScene(item.boundingRect().united(item.childrenBoundingRect())).adjusted(-30,-30,30,30)
    sim.view.fitInView(rect,Qt.AspectRatioMode.KeepAspectRatio)
    app.processEvents(); sim.view.grab().save(str(out/(kind+".png")))
print(out)
window._sync_positions(); window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
