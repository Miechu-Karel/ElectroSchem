"""Word-wrapped labels that cannot be compressed below their text height."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class WrappingLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit_height()

    def _fit_height(self):
        height = self.heightForWidth(max(1,self.width()))
        if height > 0 and self.minimumHeight() != height:
            self.setMinimumHeight(height)
