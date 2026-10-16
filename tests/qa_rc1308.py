"""Offline screenshots: real circuit behind shell; no provider calls."""
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc8'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtTest import QTest
from app.core.models import Project,Sheet,Wire
from app.core.settings import AppSettings
from app.libraries.built_in import get_instance_definition
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from test_rc1308 import RC8Tests
from test_simulation_alpha2 import Bench
app=QApplication.instance() or QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
fixture=RC8Tests(); d,r,led,button=fixture.editor(); d.resize(1300,850); d.width.setValue(640); d.height.setValue(320)
d.shapes=[dict(kind='rect',rect=[-260,-120,320,240]),dict(kind='circle',rect=[-60,-120,240,240]),dict(kind='path',points=[[-200,-60],[120,70],[-180,50],[90,-70]])]
d.selection=[-260,-120,440,240]; d.regions=[dict(kind='light',component=led.id,rect=[80,-35,60,60]),dict(kind='interaction',component=button.id,rect=[-150,-30,60,60])]; d.render()
for x,c,pin in ((-280,r,0),(200,button,1)):
    d.add_pin(QPointF(x,0),'PIN'); d.exports[-1]=dict(component=c.id,pin=pin,name='PIN'+str(len(d.pins)))
d.render(); d.tool.setCurrentIndex(d.tool.findData('interaction')); app.processEvents(); d.fit_circuit()
out=root/'output'/'rc1308'; out.mkdir(parents=True,exist_ok=True); d.grab().save(str(out/'editor.png')); d.save()
b=Bench(); source=b.add('Bateria 9V','5','V'); source.x,source.y=180,400
p=Project(sheets=[Sheet(components=b.components)],custom_components=[d.definition]); case=p.new_component(d.definition['id'],700,400); p.sheets[0].components.append(case)
for i,pin in enumerate(get_instance_definition(source).pins):
    port=d.pins[i]; p.sheets[0].wires.append(Wire(source.x+pin.x,source.y+pin.y,case.x+port['x'],case.y+port['y'],start_component_id=source.id,start_pin_index=i,end_component_id=case.id,end_pin_index=i))
w=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False); w.project=p; w._rebuild_tabs(); w.resize(1300,850); w.show(); app.processEvents(); w._current_view().fit_page(); w.grab().save(str(out/'saved.png'))
w.show_simulation(); sim=w.simulation_window; sim.resize(1300,850); sim.show(); sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-30,-30,30,30)); app.processEvents(); sim.single_step()
shell=sim.asset_cases[case.id]; point=sim.view.mapFromScene(shell.mapToScene(QPointF(-120,0)))
QTest.mousePress(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=point); app.processEvents(); sim.grab().save(str(out/'pressed.png'))
QTest.mouseRelease(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=point); app.processEvents(); sim.grab().save(str(out/'released.png'))
settings=SettingsDialog(AppSettings(language='pl',ai_provider='local',local_ai_url='http://127.0.0.1:1',local_ai_model='qwen/qwen3.5-9b')); settings.settings_tabs.setCurrentIndex(2); settings.show(); app.processEvents(); settings.grab().save(str(out/'settings.png')); settings.reject()
sim.close(); w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); d.close(); fixture.doCleanups()
