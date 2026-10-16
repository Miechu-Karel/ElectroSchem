"""Offline visual QA: no provider calls, downloads or saved user preferences."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication,QGraphicsScene,QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QFontDatabase
from app.core.settings import AppSettings
from app.canvas.component_item import ComponentItem
from app.libraries.built_in import get_definition
from app.ui.settings_dialog import SettingsDialog
from test_simulation_alpha2 import Bench

app=QApplication.instance() or QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
out=Path(__file__).resolve().parents[1]/'output'/'alpha139'; out.mkdir(parents=True,exist_ok=True)
scene=QGraphicsScene(); view=QGraphicsView(scene); view.setBackgroundBrush(Qt.GlobalColor.white)
b=Bench()
for name,x,y,angle in [('Przełącznik wielostopniowy',180,160,0),('Przełącznik wielostopniowy',420,160,180),('Przełącznik wielostopniowy',650,160,90),('Goldpin',870,160,0),('Port USB A',200,470,0),('Port USB C',530,470,0),('Układ Scalony NE556',850,470,0)]:
    c=b.add(name,sim_outputs='3'); c.x,c.y,c.rotation=x,y,angle
    item=ComponentItem(c,get_definition(c.library_id)); scene.addItem(item)
view.resize(1300,850); view.show(); view.fitInView(scene.itemsBoundingRect().adjusted(-30,-30,30,30),Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents(); view.grab().save(str(out/'symbols.png')); view.close()
dialog=SettingsDialog(AppSettings(language='pl',ai_provider='local',local_ai_model='qwen2.5:7b'))
dialog.settings_tabs.setCurrentIndex(2); dialog.show(); app.processEvents()
dialog.grab().save(str(out/'local-ai-settings.png')); dialog.reject()
print(out)
