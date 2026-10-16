"""Offline RC3 visual inspection. No provider or user-profile access."""
import os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['APPDATA']=str(root/'output'/'qa-appdata-rc3'); os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtCore import Qt
from app.core.settings import AppSettings
from app.core.models import Project,Sheet
from app.core.editor_commands import execute_batch
from app.services.power_recipe import commands
from app.ui.main_window import MainWindow
from app.ui.usb_keyboard import UsbKeyboard
from test_simulation_alpha2 import Bench
from types import SimpleNamespace

app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=root/'output'/'rc1303'; out.mkdir(parents=True,exist_ok=True)
w=MainWindow(AppSettings(language='pl',theme='dark',window_mode='windowed'),start_setup=False); w.resize(1400,900); w.show()
w.project=execute_batch(Project(sheets=[Sheet(paper_size='A3')]),0,commands()); w._rebuild_tabs(); w._current_view().fit_page(); app.processEvents(); w.grab().save(str(out/'power-reference.png'))
b=Bench(); source=b.add('Źródło napięcia przemiennego','5','V'); scope=b.add('Oscyloskop')
source.x,source.y=300,800; scope.x,scope.y=850,800
b.connect(source,0,scope,0); b.connect(source,1,scope,1)
w.project=Project(sheets=[Sheet(paper_size='A3',components=b.components,wires=b.wires)]); w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window; sim.resize(1400,900); sim.show(); sim.open_scope(scope.id)
sim.view.fitInView(sim.scene.itemsBoundingRect().adjusted(-20,-20,20,20),Qt.AspectRatioMode.KeepAspectRatio); app.processEvents(); sim.grab().save(str(out/'scope-beside.png'))
keyboard=UsbKeyboard(sim,SimpleNamespace(state={})); keyboard.show(); app.processEvents(); keyboard.grab().save(str(out/'keyboard.png')); keyboard.close()
sim.close(); w._saved_state=w.project.to_dict(); w.close()
