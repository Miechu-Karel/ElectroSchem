import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc6'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import QPointF
from app.core.models import Project,Sheet
from app.core.assets import make_asset
from app.core.settings import AppSettings
from app.ui.paint_case_editor import PaintAssetCaseEditor
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench
app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
b=Bench(); r=b.add('Rezystor','330','Ω'); led=b.add('Dioda LED 3mm'); r.x,r.y=300,300; led.x,led.y=500,300; b.connect(r,1,led,0)
p=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); definition=make_asset(p,p.sheets[0],'Moduł LED',True,{r.id,led.id})
d=PaintAssetCaseEditor(definition,AppSettings(language='pl')); d.width.setValue(640); d.height.setValue(320); d.scale.setValue(100)
d.shapes=[dict(kind='path',points=[[-300,-120],[260,-120],[300,-80],[300,120],[-300,120],[-300,-120]],closed=True)]; d.render()
d.add_pin(QPointF(-320,0),'IN'); d.add_pin(QPointF(320,0),'OUT')
for i,source in ((0,d.internal_pins[0][0]),(1,d.internal_pins[-1][0])):
    pin=d.pins[i]; d.connect_at(QPointF(pin['x'],pin['y'])); d.connect_at(source)
d.show(); app.processEvents(); out=root/'output'/'rc1306'; out.mkdir(parents=True,exist_ok=True); d.grab().save(str(out/'paint-case-editor.png')); d.save()
p=Project(custom_components=[d.definition]); p.sheets[0].components.append(p.new_component(d.definition['id'],500,350))
w=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False); w.project=p; w._rebuild_tabs(); w.resize(1300,900); w.show(); app.processEvents(); w._current_view().fit_page(); w.grab().save(str(out/'saved-case.png')); w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); d.close()
