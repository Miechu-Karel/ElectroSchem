"""Render alfa5 changes without changing preferences or user projects."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.core.models import Sheet, Annotation
from app.core.settings import AppSettings
from app.libraries.built_in import get_definition
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.settings_dialog import SettingsDialog
from test_simulation import component
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
out=Path("output/alfa5"); out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",grid_visible=False),start_setup=False)
window.show(); app.processEvents()
window.grab().save(str(out/"editor.png"))
for name in ("Bramka NAND","Rezystor","Bateria 9V"):
    c=component(name,100,100); c.reference="NANGat004" if name=="Bramka NAND" else "Example001"
    props=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl",window)
    props.show(); app.processEvents(); props.grab().save(str(out/(get_definition(c.library_id).symbol+"-properties.png")))
    props.close()
settings=SettingsDialog(window.settings,window)
settings.show(); app.processEvents(); settings.grab().save(str(out/"settings.png")); settings.close()
b=Bench(); source=b.add("Input"); gate=b.add("Bramka NOT"); output=b.add("Output")
source.x=200; gate.x=400; output.x=600
b.connect(source,0,gate,0); b.connect(gate,1,output,0)
sheet=Sheet(components=b.components,wires=b.wires,comments=[Annotation("Wejście 0 → NOT → wyjście 1",160,180)])
window.project.sheets=[sheet]; window._rebuild_tabs(); window.show_simulation()
sim=window.simulation_window; sim.resize(1280,850); app.processEvents()
sim.single_step(); sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-100,-100,100,100),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); sim.grab().save(str(out/"logic-comments.png"))
window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
print(out.resolve())
