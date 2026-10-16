import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc7'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import QPointF
from app.core.models import Project,Sheet,Wire
from app.core.assets import make_asset
from app.core.settings import AppSettings
from app.ui.paint_case_editor import PaintAssetCaseEditor
from app.ui.main_window import MainWindow
from app.ui.asset_shells import update
from app.libraries.built_in import get_instance_definition
from test_simulation_alpha2 import Bench
app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
b=Bench(); r=b.add('Rezystor','330','Ω'); led=b.add('Dioda LED 3mm'); led.properties['color']='red'; r.x,r.y=300,300; led.x,led.y=500,300; b.connect(r,1,led,0)
p=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); definition=make_asset(p,p.sheets[0],'Moduł LED',True,{r.id,led.id})
d=PaintAssetCaseEditor(definition,AppSettings(language='pl')); d.width.setValue(640); d.height.setValue(320); d.scale.setValue(100)
d.shapes=[dict(kind='rect',rect=[-260,-120,320,240]),dict(kind='circle',rect=[-60,-120,240,240])]; d.render()
d.add_pin(QPointF(-260,0),'IN'); d.add_pin(QPointF(180,0),'OUT')
for i,source in ((0,d.internal_pins[0][0]),(1,d.internal_pins[-1][0])):
    pin=d.pins[i]; d.connect_at(QPointF(pin['x'],pin['y'])); d.connect_at(source)
d.regions=[dict(kind='light',component=led.id,rect=[80,-35,60,60])]; d.render(); d.show(); app.processEvents()
out=root/'output'/'rc1307'; out.mkdir(parents=True,exist_ok=True); d.grab().save(str(out/'editor.png')); d.save()
b=Bench(); source=b.add('Bateria 9V','5','V'); source.x,source.y=200,400
p=Project(sheets=[Sheet(components=b.components)],custom_components=[d.definition]); case=p.new_component(d.definition['id'],700,400); p.sheets[0].components.append(case)
for i in range(2):
    pin=get_instance_definition(source).pins[i]; port=d.definition['pins'][i]
    p.sheets[0].wires.append(Wire(source.x+pin.x,source.y+pin.y,case.x+port['x'],case.y+port['y'],start_component_id=source.id,start_pin_index=i,end_component_id=case.id,end_pin_index=i))
w=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False); w.project=p; w._rebuild_tabs(); w.resize(1300,900); w.show(); app.processEvents(); w._current_view().fit_page(); w.grab().save(str(out/'saved-case.png'))
w.show_simulation(); sim=w.simulation_window; sim.resize(1300,850); sim.show(); app.processEvents()
if sim.circuit: update(sim,sim.circuit.step(.001))
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-30,-30,30,30)); sim.grab().save(str(out/'simulation-case.png')); sim.close(); w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); d.close()
