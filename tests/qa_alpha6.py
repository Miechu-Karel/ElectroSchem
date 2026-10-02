"""Render editor selection and white logic indicators without user-data writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.core.models import Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
out=Path("output/alfa6"); out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl"),start_setup=False)
b=Bench(); source=b.add("Input",sim_closed="true"); output=b.add("Output")
source.x=200; output.x=400; b.connect(source,0,output,0)
window.project.sheets=[Sheet(components=b.components,wires=b.wires)]; window._rebuild_tabs()
window.show(); app.processEvents()
view=window._current_view()
for item in view._component_items.values(): item.setSelected(True)
view.fitInView(QRectF(100,180,400,260),Qt.AspectRatioMode.KeepAspectRatio)
view.viewport().grab().save(str(out/"selection.png"))
window.show_simulation(); sim=window.simulation_window; sim.resize(1000,750)
app.processEvents(); sim.single_step()
sim.view.fitInView(QRectF(80,180,440,260),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); sim.grab().save(str(out/"logic-high.png"))
sim.toggle(source.id); sim.single_step(); app.processEvents()
sim.grab().save(str(out/"logic-low.png"))
window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
print(out.resolve())
