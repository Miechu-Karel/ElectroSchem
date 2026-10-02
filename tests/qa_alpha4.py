"""Render alfa4 UI and save a corrected copy of the supplied Pi LED project.

Run from the repository root, with the optional source ELS as the argument.
The original file is never saved or edited.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import sys
from copy import deepcopy
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from app.core.settings import AppSettings
from app.core.project_file import load_project, save_project
from app.core.models import ComponentInstance, Wire
from app.libraries.built_in import get_definition, BUILT_IN_ITEMS
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
out=Path("output/alfa4"); out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",default_author="Miechu"),start_setup=False)
window.show()
settings=SettingsDialog(window.settings,window); settings.show(); app.processEvents()
settings.grab().save(str(out/"settings.png")); settings.close()
if len(sys.argv)>1:
    project=load_project(sys.argv[1]); sheet=project.sheets[0]
    board=next(c for c in sheet.components if get_definition(c.library_id).name=="Raspberry Pi 5")
    board.properties.update(sim_source=str(Path("tests/fixtures/gpio_blink.py").resolve()),sim_mode="gpio")
    # Replace only the anchored board end of the GPIO12 wire with a resistor.
    # Keep the rest of the user's route/physical pin numbering intact.
    original=next(w for w in sheet.wires if w.start_component_id==board.id and w.start_pin_number=="32")
    d=next(d for d in BUILT_IN_ITEMS if d.name=="Rezystor")
    r=ComponentInstance(d.id, original.start_x+120, original.start_y+160, reference=project.allocate_reference(d.id),value="330",unit="Ω")
    sheet.components.append(r)
    start=(original.start_x,original.start_y)
    original.start_component_id=r.id; original.start_pin_index=1; original.start_pin_number="2"
    original.start_x=r.x+d.pins[1].x; original.start_y=r.y+d.pins[1].y
    if original.points: original.points[0]=[original.start_x,original.start_y]
    end=(r.x+d.pins[0].x,r.y+d.pins[0].y)
    sheet.wires.append(Wire(*start,*end,start_component_id=board.id,start_pin_number="32",start_pin_index=31,
                            end_component_id=r.id,end_pin_number="1",end_pin_index=0,points=[list(start),list(end)]))
    save_project(out/"Raspberry-LED-330R.els",project)
    window.project=project; window._rebuild_tabs()
    props=ComponentPropertiesDialog(board,get_definition(board.library_id),"pl",window)
    props.show(); app.processEvents(); props.grab().save(str(out/"board-properties.png")); props.close()
window.show_simulation(); sim=window.simulation_window
if len(sys.argv)==1: sim.load_example(1)
sim.resize(1280,850); app.processEvents(); sim.single_step(); app.processEvents()
if sim.circuit:
    assert not sim.circuit.result.faults,sim.circuit.result.faults
    if len(sys.argv)>1:
        led=next(c for c in sim.sheet.components if get_definition(c.library_id).symbol=="led")
        assert sim.circuit.result.brightness[led.id]>.1
        for _ in range(60): result=sim.circuit.step(.01)
        assert result.brightness[led.id]<1e-6
        for _ in range(50): result=sim.circuit.step(.01)
        assert result.brightness[led.id]>.1
        sim.calculate(single=True)
    sim.grab().save(str(out/"raspberry-simulation.png"))
else: raise RuntimeError(sim.log.toPlainText())
window._saved_state=deepcopy(window.project.to_dict()); window.close()
app.processEvents()
print(out.resolve())
