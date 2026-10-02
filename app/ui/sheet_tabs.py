"""Zakładki projektu: pionowe lewe ramię, prawe pod 60° i mała szczelina."""
from pathlib import Path
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPolygon
from PySide6.QtWidgets import QTabBar


class SheetTabBar(QTabBar):
    add_requested = Signal()
    rename_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setUsesScrollButtons(True)
        self._plus_rect = QRect()
        self._add_icon = QIcon(str(Path(__file__).resolve().parents[2] / "Ikonki" / "Dodaj Arkusz.png"))

    def tabSizeHint(self, index):
        width = max(100, self.fontMetrics().horizontalAdvance(self.tabText(index)) + 48)
        return QSize(width + (32 if index == self.count()-1 else 0), 34)

    def minimumTabSizeHint(self, index):
        # Nie ściskamy nazw do pojedynczej litery — długi pasek ma strzałki.
        return self.tabSizeHint(index)

    def paintEvent(self, event):
        dark=getattr(getattr(self.window(),"settings",None),"theme","light")=="dark"
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#17212d" if dark else "#e6eef5"))
        self._plus_rect = QRect()
        for index in range(self.count()):
            rect = self.tabRect(index)
            if index == self.count()-1:
                self._plus_rect = QRect(rect.right()-27, 5, 24, 24)
                rect = rect.adjusted(0, 0, -32, 0)
            rect = rect.adjusted(0, 0, -4, -1)
            inset = round(rect.height()/1.7320508)
            polygon = QPolygon([rect.topLeft(), rect.topRight(),
                                rect.bottomRight()-QPoint(inset, 0), rect.bottomLeft()])
            selected = index == self.currentIndex()
            painter.setBrush(QColor(("#315772" if selected else "#202c3a") if dark else ("#ffffff" if selected else "#d4e2ec")))
            painter.setPen(QColor("#7b95a8"))
            painter.drawPolygon(polygon)
            painter.setPen(QColor("#e0e9f2" if dark else ("#096b92" if selected else "#254b63")))
            painter.drawText(rect.adjusted(8, 0, -inset, 0), Qt.AlignmentFlag.AlignCenter, self.tabText(index))
        if self.count():
            painter.setBrush(QColor("#315772" if dark else "#ccecf5"))
            painter.setPen(QColor("#3981a0"))
            painter.drawRoundedRect(self._plus_rect, 4, 4)
            if dark:
                from app.ui.theme import themed_icon
                icon=themed_icon(Path(__file__).resolve().parents[2]/"Ikonki"/"Dodaj Arkusz.png",True)
            else: icon=self._add_icon
            icon.paint(painter, self._plus_rect.adjusted(3, 3, -3, -3))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._plus_rect.contains(event.position().toPoint()):
            self.add_requested.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.position().toPoint())
        if index >= 0 and not self._plus_rect.contains(event.position().toPoint()):
            self.rename_requested.emit(index)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
