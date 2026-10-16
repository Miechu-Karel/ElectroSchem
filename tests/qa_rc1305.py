"""Isolated native UI visual verification, no network calls."""
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc5'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt,QPointF
from app.core.settings import AppSettings
from app.core.models import Project,Sheet
from app.core.assets import make_asset
from app.core.editor_commands import execute_batch
from app.services.power_recipe import commands
from app.ui.asset_case_editor import AssetCaseEditor
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench
app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=root/'output'/'rc1305'; out.mkdir(parents=True,exist_ok=True)
b=Bench(); r=b.add('Rezystor','330','Ω'); led=b.add('Dioda LED 3mm'); b.connect(r,1,led,0)
r.x,r.y=300,300; led.x,led.y=500,300
# Rebuild the test connection after positioning.
b.wires=[]; b.connect(r,1,led,0)
p=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
d=make_asset(p,p.sheets[0],'LED module',True,{r.id,led.id})
editor=AssetCaseEditor(d,AppSettings(language='pl')); editor.shapes=[dict(kind='rect',rect=[-150,-50,300,100])]; editor.render(); editor.show(); app.processEvents(); editor.grab().save(str(out/'case-editor.png')); editor.save(); d=editor.definition; editor.close()
w=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False); w.resize(1300,900); w.show()
p=Project(custom_components=[d]); item=p.new_component(d['id'],500,380); p.sheets[0].components.append(item)
w.project=p; w._rebuild_tabs(); view=w._current_view(); view.fitInView(view.scene.itemsBoundingRect().adjusted(-30,-30,30,30),Qt.AspectRatioMode.KeepAspectRatio)
view._show_hidden_wires=True; app.processEvents(); w.grab().save(str(out/'asset-wire-peek.png'))
b=Bench(); male=b.add('Goldpin'); female=b.add('Goldpin żeński'); cable=b.add('Kabel Męsko-Żeński')
for c,(x,y) in zip(b.components,((300,300),(600,300),(450,500))): c.x,c.y=x,y
w.project=Project(sheets=[Sheet(components=b.components)]); w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window; sim.resize(1300,850); sim.show(); sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-60,-60,60,60),Qt.AspectRatioMode.KeepAspectRatio); app.processEvents(); sim.grab().save(str(out/'slim-plugs-old-goldpins.png')); sim.close()
w.project=execute_batch(Project(sheets=[Sheet(paper_size='A3')]),0,commands()); w._rebuild_tabs(); w._current_view().fit_page(); app.processEvents(); w.grab().save(str(out/'orthogonal-routing.png'))
w._saved_state=w.project.to_dict(); w.close()
