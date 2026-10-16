"""Offline screenshots: no provider calls or saved user preferences."""
import os,math
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from app.core.settings import AppSettings
from app.core.models import Project,Sheet
from app.libraries.built_in import get_definition
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=Path(__file__).resolve().parents[1]/'output'/'alpha1310'; out.mkdir(parents=True,exist_ok=True)
settings=AppSettings(language='pl',window_mode='windowed',scope_size='large')
dialog=SettingsDialog(settings); dialog.settings_tabs.setCurrentIndex(3); dialog.show(); app.processEvents()
dialog.grab().save(str(out/'simulation-settings.png')); dialog.reject()
b=Bench(); source=b.add('Źródło napięcia przemiennego','5','V',sim_voltage_mode='limits',sim_voltage_min='-2 V',sim_voltage_max='6 V')
dialog=ComponentPropertiesDialog(source,get_definition(source.library_id),'pl'); dialog.show(); app.processEvents()
dialog.grab().save(str(out/'ac-limits.png')); dialog.reject()
w=MainWindow(settings,start_setup=False); w.show(); app.processEvents()
b=Bench(); r=b.add('Rezystor','5','Ω'); w.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); w._rebuild_tabs()
w.show_simulation(); app.processEvents(); sim=w.simulation_window; sim.buzzer_sound_button.setChecked(True)
sim.open_measurements(); p=sim.measurement_panel; p.mode.setCurrentIndex(p.mode.findData('continuity')); p.refresh(); app.processEvents()
p.grab().save(str(out/'continuity.png'))
p.mode.setCurrentIndex(p.mode.findData('wave')); p.waveform.samples.extend((i*.001,2+3*math.sin(i*.08)) for i in range(500)); p.waveform.update(); p.resize(820,720); app.processEvents()
p.grab().save(str(out/'scope.png')); sim.close(); app.processEvents()
w.show_command_panel(); panel=w.command_panel; panel.failed('http_503'); app.processEvents()
panel.grab().save(str(out/'ai-error.png')); panel.cancel_request()
w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); app.processEvents()
print(out)
