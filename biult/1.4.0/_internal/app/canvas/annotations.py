"""Komentarze na schemacie: tekst bez HTML, Arial i snap do siatki."""
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QGraphicsItem,
                              QGraphicsTextItem, QPlainTextEdit, QSpinBox)

class AnnotationItem(QGraphicsTextItem):
    def __init__(self, annotation):
        super().__init__()
        self.annotation = annotation
        self.setPlainText(annotation.text)
        # Rozmiar podany przez użytkownika jest typograficznym pt. Scena ma
        # 4 jednostki/mm, więc jawnie przeliczamy go przed eksportem w innym DPI.
        font = QFont("Arial")
        font.setPixelSize(round(annotation.font_size * 25.4 / 72 * 4))
        self.setFont(font)
        self.setDefaultTextColor(QColor("#163449"))
        self.document().setDocumentMargin(0)
        self.setData(0, "comment")
        self.setData(1, annotation.id)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(annotation.x, annotation.y)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(value, QPointF):
            return QPointF(round(value.x()/20)*20, round(value.y()/20)*20)
        return super().itemChange(change, value)


class InlineAnnotationEditor(QGraphicsTextItem):
    """Edytor komentarza osadzony bezpośrednio na arkuszu.

    Enter kończy wpis (Shift+Enter wstawia nową linię), a utrata fokusu
    zapisuje tekst. Szerokość dokumentu jest wielokrotnością kratki 5 mm.
    """
    editing_finished = Signal(str)

    def __init__(self, text="", font_size=12):
        super().__init__()
        self.setPlainText(text)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setDefaultTextColor(QColor("#163449"))
        self.document().setDocumentMargin(0)
        self.setTextWidth(20 * 8)
        font = QFont("Arial")
        font.setPixelSize(round(font_size * 25.4 / 72 * 4))
        self.setFont(font)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.editing_finished.emit(self.toPlainText())
            event.accept()
            return
        super().keyPressEvent(event)

    def paint(self, painter, option, widget=None):
        # Tło komórki nie rysuje aktualnie edytowanej wartości. Nie zakrywamy
        # nic białą nakładką; kursor porusza się po tekście w jego miejscu.
        if self.data(0) == "title-editor" and hasattr(self, "title_cell"):
            painter.setClipRect(self.mapRectFromScene(self.title_cell))
        super().paint(painter, option, widget)

    def focusOutEvent(self, event):
        self.editing_finished.emit(self.toPlainText())
        super().focusOutEvent(event)

def edit_annotation(parent, language, text="", font_size=12):
    pl = language == "pl"
    dialog = QDialog(parent)
    dialog.setWindowTitle("Komentarz" if pl else "Comment")
    dialog.resize(440, 270)
    layout = QFormLayout(dialog)
    editor = QPlainTextEdit(text)
    editor.setFont(QFont("Arial", font_size))
    size = QSpinBox()
    size.setRange(6, 72)
    size.setValue(font_size)
    size.valueChanged.connect(lambda value: editor.setFont(QFont("Arial", value)))
    layout.addRow(editor)
    layout.addRow("Arial · " + ("Rozmiar" if pl else "Size"), size)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(buttons)
    editor.setFocus()
    if dialog.exec() == QDialog.DialogCode.Accepted and editor.toPlainText().strip():
        return editor.toPlainText()[:20000], size.value()
    return None
