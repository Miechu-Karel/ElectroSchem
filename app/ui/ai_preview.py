"""Podgląd jest renderowany z kopii projektu, nigdy z żywego edytora.

Korzysta z tych samych symboli, przewodów i ramki co eksport. Bitmapa nie
przyjmuje gestów edycji, więc kliknięcie podglądu nie zmienia dokumentu.
"""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget
from app.canvas.schematic_view import SchematicView


class AiPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.setMinimumHeight(180)
        self.setMaximumHeight(250)

    def sizeHint(self):
        return QSize(380, 210)

    def set_project(self, project, index, settings):
        view = SchematicView(project=project, settings=settings, sheet=project.sheets[index])
        try:
            self.image = QImage(1200, 850, QImage.Format.Format_ARGB32_Premultiplied)
            self.image.fill(Qt.GlobalColor.white)
            painter = QPainter(self.image)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                # W małej karcie powiększamy układ zamiast całej pustej kartki.
                source = view.scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
                if not view.scene.items():
                    source = view.paper_rect()
                view.scene.render(painter, QRectF(0, 0, 1200, 850), source)
            finally:
                painter.end()
        finally:
            view.deleteLater()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self.image.isNull():
            size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            painter.drawImage(QRectF((self.width()-size.width())/2, (self.height()-size.height())/2,
                                     size.width(), size.height()), self.image)
