"""Code-native cable fallback; icons/cables.png takes precedence."""
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPixmap,QPainter,QPainterPath,QPen,QColor,QIcon

def cable_icon(dark=False):
    pixmap=QPixmap(48,48); pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#e3edf5' if dark else '#13374b'),2.5)); painter.setBrush(Qt.BrushStyle.NoBrush)
    path=QPainterPath(); path.moveTo(11,18); path.cubicTo(7,42,41,42,37,18); painter.drawPath(path)
    for x in (5,31):
        painter.drawRect(QRectF(x,10,12,9)); painter.drawRect(QRectF(x+2,6,8,4))
    painter.end(); return QIcon(pixmap)
