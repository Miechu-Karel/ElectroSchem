"""Offline screenshots of alpha8; muted, no provider requests or settings saves."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QFontDatabase
from app.core.models import Project,Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.component_info_dialog import ComponentInfoDialog
from app.libraries.built_in import get_definition
from app.simulation.examples import example
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=Path(__file__).resolve().parents[1]/'output'/'alpha138'; out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language='pl',theme='dark',window_mode='windowed',fault_effect='mini',ai_provider='none'),start_setup=False)
window.resize(1400,950); window.show()
def load(sheet):
    window.project=Project(sheets=[sheet]); window._rebuild_tabs(); app.processEvents()
def sandbox(name):
    load(example(name)); window.show_simulation(); sim=window.simulation_window
    sim.resize(1400,950); sim.buzzer_sound_button.setChecked(True); sim.single_step()
    sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-40,-40,40,40),Qt.AspectRatioMode.KeepAspectRatio)
    app.processEvents(); sim.grab().save(str(out/(name+'.png'))); sim.close()
for name in ('led','transistor','usb_c_led','fault_gpio'): sandbox(name)
b=Bench(); switch=b.add('Przełącznik wielostopniowy',sim_outputs='2'); switch.x,switch.y=450,350
load(Sheet(components=b.components)); switch.properties['sim_outputs']='10'; window._current_view().refresh_component(switch.id)
view=window._current_view(); view.fitInView(view.scene.itemsBoundingRect(),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); window.grab().save(str(out/'switch10.png'))
b=Bench(); board=b.add('Raspberry Pi 5',sim_source=str(Path(__file__).parent/'fixtures'/'console_input.py')); board.x,board.y=700,550
keyboard=b.add('Klawiatura USB'); keyboard.x,keyboard.y=350,550
b.connect(board,'5V',keyboard,'VBUS'); b.connect(board,'GND',keyboard,'GND')
load(Sheet(components=b.components,wires=b.wires)); window.show_simulation(); sim=window.simulation_window
sim.resize(1400,950); sim.buzzer_sound_button.setChecked(True); sim.single_step()
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-40,-40,40,40),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); sim.grab().save(str(out/'keyboard.png')); sim.close()
port=b.add('Port USB C'); dialog=ComponentInfoDialog(port,get_definition(port.library_id),'pl',parent=window)
dialog.show(); app.processEvents(); dialog.grab().save(str(out/'usb-help.png')); dialog.close()
window._saved_state=window.project.to_dict(); window.close(); print(out)
