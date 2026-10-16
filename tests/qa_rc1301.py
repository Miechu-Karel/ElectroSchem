"""Offline visual QA of RC1 without touching the real API profile."""
import os,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc1'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt,QPoint
from app.core.models import Project,Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.component_info_dialog import ComponentInfoDialog
from app.libraries.built_in import get_definition
from test_simulation_alpha2 import Bench
app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=root/'output'/'rc1301'; out.mkdir(parents=True,exist_ok=True)
w=MainWindow(AppSettings(language='pl',theme='dark',window_mode='windowed',scope_size='large'),start_setup=False); w.resize(1400,900); w.show()
b=Bench(); male=b.add('Goldpin'); female=b.add('Goldpin żeński'); board=b.add('Płytka stykowa'); cable=b.add('Kabel Męsko-Żeński',jumper_a_target=board.id,jumper_a_pin='17',jumper_b_target=male.id)
port=b.add('Port USB C'); pi=b.add('Raspberry Pi 5')
for c,x,y in ((male,250,400),(female,250,600),(board,750,550),(cable,420,550),(port,1200,280),(pi,1350,800)): c.x,c.y=x,y
w.project=Project(sheets=[Sheet(paper_size='A3',components=b.components)]); w._rebuild_tabs(); w._current_view().fit_page(); app.processEvents(); w.grab().save(str(out/'editor.png'))
menu=QMenu(); w._populate_library_menu(menu,1,QPoint()); menu.show(); app.processEvents()
sound=next(a.menu() for a in menu.actions() if a.text()=='Dźwięk'); sound.show(); app.processEvents(); sound.grab().save(str(out/'sound.png')); menu.close(); sound.close()
b=Bench(); source=b.add('Zasilacz laboratoryjny','5','V'); r=b.add('Rezystor','1','kΩ'); scope=b.add('Oscyloskop')
for c,x,y in ((source,300,650),(r,1300,650),(scope,1100,1100)): c.x,c.y=x,y
b.connect(source,0,r,0); b.connect(source,1,r,1); b.connect(r,0,scope,0); b.connect(r,1,scope,1)
w.project=Project(sheets=[Sheet(paper_size='A3',components=b.components,wires=b.wires)]); w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window; sim.resize(1500,1000); sim.show(); sim.open_scope(scope.id)
sim.scopes[scope.id].scope_samples.extend((i*.0001,3*math.sin(2*math.pi*50*i*.0001)) for i in range(10000))
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-25,-25,25,25),Qt.AspectRatioMode.KeepAspectRatio); app.processEvents(); sim.grab().save(str(out/'scope-inline.png')); sim.close(); app.processEvents()
info=ComponentInfoDialog(source,get_definition(source.library_id),'pl'); info.show(); app.processEvents(); info.grab().save(str(out/'help.png')); info.close()
w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); print(out)
