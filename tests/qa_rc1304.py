"""Offline visual checks with isolated settings; never sends provider requests."""
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc4'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt,QTimer
from app.core.models import Project,Sheet
from app.core.settings import AppSettings
from app.core.editor_commands import execute_batch
from app.services.power_recipe import commands
from app.ui.main_window import MainWindow
from app.ui.usb_keyboard import UsbKeyboard
from test_simulation_alpha2 import Bench
from types import SimpleNamespace
app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=root/'output'/'rc1304'; out.mkdir(parents=True,exist_ok=True)
w=MainWindow(AppSettings(language='pl',theme='dark',window_mode='windowed'),start_setup=False); w.resize(1450,950); w.show()
w.project=execute_batch(Project(sheets=[Sheet(paper_size='A3')]),0,commands()); w._rebuild_tabs(); w._current_view().fit_page(); app.processEvents(); w.grab().save(str(out/'power-routing.png'))
w.show_command_panel(); panel=w.command_panel; panel.prepare(); panel.show_proposal()
def inspect():
    app.processEvents(); panel.preview.inspection_dialog.grab().save(str(out/'editable-preview.png')); panel.preview.inspection_dialog.reject()
QTimer.singleShot(50,inspect); panel.preview.inspect('pl')
panel.reject(); w.command_dock.hide()
b=Bench(); card=b.add('Karta RFID'); male=b.add('Goldpin'); female=b.add('Goldpin żeński')
for c,(x,y) in zip(b.components,((400,350),(740,350),(950,350))): c.x,c.y=x,y
w.project=Project(sheets=[Sheet(components=b.components)]); w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window; sim.resize(1450,950); sim.show(); sim.open_measurements()
sim.measurement_panel.hide(); sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-60,-60,60,60),Qt.AspectRatioMode.KeepAspectRatio); app.processEvents(); sim.grab().save(str(out/'rfid-goldpins-meter.png'))
keyboard=UsbKeyboard(sim,SimpleNamespace(state={})); keyboard.show(); app.processEvents(); keyboard.grab().save(str(out/'keyboard-glyphs.png')); keyboard.close()
sim.close(); w._saved_state=w.project.to_dict(); w.close()
