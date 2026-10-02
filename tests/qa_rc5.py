"""Display preview gallery from electrically powered fixture circuits."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter,QFont,QFontDatabase,QColor
from PySide6.QtWidgets import QApplication,QGraphicsScene
from test_simulation_rc5 import powered_display
from app.libraries.display_profiles import DISPLAY_PROFILES
from app.ui.simulation_window import LiveSymbol

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","segoeui.ttf","cour.ttf"):
    QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts")/name))
app.setFont(QFont("Segoe UI",9))
scene=QGraphicsScene(); keep=[]
for i,name in enumerate(DISPLAY_PROFILES):
    circuit,component=powered_display(name)
    component.x=(i%3)*500+250; component.y=(i//3)*520+450
    item=LiveSymbol(component,language="pl")
    item.display_state=circuit.step().displays[component.id]
    scene.addItem(item); keep.append(item)
image=QImage(1500,1040,QImage.Format.Format_ARGB32); image.fill(QColor("#10151c"))
painter=QPainter(image); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
scene.render(painter,QRectF(0,0,1500,1040),QRectF(0,0,1500,1040)); painter.end()
out=Path(__file__).resolve().parents[1]/"output/rc5"; out.mkdir(parents=True,exist_ok=True)
image.save(str(out/"displays.png")); print(out/"displays.png")
