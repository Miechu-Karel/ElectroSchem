"""Paint secondary aliases after Qt's stylesheet, which overrides palettes."""
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QPalette,QPainter


class LibrarySubMenu(QMenu):
    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self)
        dark=self.palette().color(QPalette.ColorRole.Window).lightness()<128
        for action in self.actions():
            if not action.property("secondaryEntry"): continue
            rect=self.actionGeometry(action)
            painter.save(); painter.setClipRect(rect.adjusted(1,0,-1,0))
            background=self.palette().color(QPalette.ColorRole.Highlight if action==self.activeAction() else QPalette.ColorRole.Base)
            painter.fillRect(rect,background)
            painter.setFont(self.font()); painter.setPen(QColor("#9baab8" if dark else "#7b858e"))
            painter.drawText(rect.adjusted(16,0,-8,0),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,action.text())
            painter.restore()
