"""Offline visual QA, isolated settings, no model calls."""
import os,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-alpha11')
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt
from app.core.settings import AppSettings
from app.core.models import Project,Sheet
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from test_simulation_alpha2 import Bench
app=QApplication.instance() or QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=root/'output'/'alpha1311'; out.mkdir(parents=True,exist_ok=True)
settings=AppSettings(language='pl',theme='dark',window_mode='windowed',scope_size='large')
dialog=SettingsDialog(settings); dialog.settings_tabs.setCurrentIndex(3); dialog.show(); app.processEvents(); dialog.grab().save(str(out/'settings.png')); dialog.reject()
w=MainWindow(settings,start_setup=False); w.resize(1300,850); w.show(); app.processEvents()
b=Bench(); source=b.add('Zasilacz laboratoryjny','5','V'); r=b.add('Rezystor','1','kΩ'); scope=b.add('Oscyloskop')
source.x,source.y=300,550; r.x,r.y=1200,550; scope.x,scope.y=950,900
b.connect(source,0,r,0); b.connect(source,1,r,1); b.connect(r,0,scope,0); b.connect(r,1,scope,1)
w.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window
sim.resize(1500,950); sim.show()
for _ in range(900): sim.calculate(single=True)
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-30,-30,30,30),Qt.AspectRatioMode.KeepAspectRatio); app.processEvents()
sim.grab().save(str(out/'lab-supply.png'))
sim.open_measurements(); p=sim.measurement_panel; p.mode.setCurrentIndex(p.mode.findData('wave')); p.resize(900,760)
p.waveform.samples.extend((i*.0001,2+3*math.sin(2*math.pi*50*i*.0001)) for i in range(10000)); p.waveform.update(); app.processEvents(); p.grab().save(str(out/'scope.png')); sim.close(); app.processEvents()
b=Bench(); brick=b.add('Kostka zasilająca USB','5','V'); port=b.add('Port USB C'); cable=b.add('Kabel USB',usb_a_target=brick.id,usb_b_target=port.id)
male=b.add('Goldpin'); female=b.add('Goldpin żeński'); jumper=b.add('Kabel Męsko-Żeński',jumper_a_target=female.id,jumper_b_target=male.id)
for c,x,y in ((brick,220,220),(port,560,220),(cable,390,350),(male,280,550),(female,620,550),(jumper,460,650)): c.x,c.y=x,y
w.project=Project(sheets=[Sheet(components=b.components)]); w._rebuild_tabs(); v=w._current_view(); v.fit_page(); app.processEvents(); v.grab().save(str(out/'editor-cables.png'))
w.show_command_panel(); panel=w.command_panel; panel.chat.appendPlainText('Ty: Narysuj LED zasilany przez USB C.'); panel.chat.appendPlainText('AI: Przyjmuję zasilanie 5 V i rezystor ograniczający prąd. Przygotuję układ z drogą powrotną.'); panel.prompt.setPlainText('Zmień LED na niebieski.'); app.processEvents(); panel.grab().save(str(out/'assistant.png'))
panel.cancel_request(); w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); app.processEvents(); print(out)
