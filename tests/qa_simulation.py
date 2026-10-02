"""Offscreen visual smoke test; writes only ignored output/ previews."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtCore import QEvent
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
    if path.is_file():QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
window=MainWindow(AppSettings(language="pl",grid_visible=False),start_setup=False)
window.show()
window.show_simulation()
sim=window.simulation_window
sim.resize(1200,800)
sim.load_example(1)
app.processEvents()
sim.single_step()
app.processEvents()
destination=Path(__file__).resolve().parent.parent/"output"
destination.mkdir(exist_ok=True)
sim.grab().save(str(destination/"simulation-led.png"))
for name in ("rails","transistor"):
    sim.load_example(sim.examples.findData(name))
    sim.single_step()
    app.processEvents()
    sim.grab().save(str(destination/f"simulation-{name}.png"))
sim.load_example(3)
for _ in range(100):
    sim.advance()
    if sim.circuit.result.faults:break
app.processEvents()
sim.grab().save(str(destination/"simulation-fault.png"))
window._saved_state=window.project.to_dict()
window.close()
app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
print(destination)
