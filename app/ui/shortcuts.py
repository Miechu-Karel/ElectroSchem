"""Skróty edytora nie mogą przechwytywać pisania w formularzach.

Sekwencję zaczyna Ctrl+A albo Shift+A; druga litera może być naciśnięta
po puszczeniu modyfikatora lub przy nadal wciśniętym Ctrl/Shift.
"""
from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox


class EditorShortcuts(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.pending = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.clear)
        QApplication.instance().installEventFilter(self)

    def clear(self):
        self.pending = None
        self.timer.stop()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ShortcutOverride:
            view = self.window._current_view()
            if view is not None and view.is_editing_text():
                # Pozwól edytorowi obsłużyć Ctrl+A/Z/Y/C/V bez wywołania
                # globalnej historii projektu ani sekwencji dodawania.
                if event.key() in (Qt.Key.Key_A, Qt.Key.Key_Z, Qt.Key.Key_Y,
                                   Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_X,
                                   Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                    event.accept()
                    return True
        if event.type() != QEvent.Type.KeyPress or event.isAutoRepeat():
            return False
        focus = QApplication.focusWidget()
        view = self.window._current_view()
        if view is not None and view.is_editing_text():
            self.clear()
            return False
        if QApplication.activeModalWidget() or (focus and focus.window() is not self.window):
            self.clear()
            return False
        if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)) or (
                isinstance(focus, QComboBox) and focus.isEditable()):
            self.clear()
            return False
        key, mods = event.key(), event.modifiers()
        if mods == Qt.KeyboardModifier.ControlModifier and key in (
                Qt.Key.Key_D, Qt.Key.Key_X, Qt.Key.Key_C, Qt.Key.Key_V):
            self.clear()
            operation = {Qt.Key.Key_D: "duplicate", Qt.Key.Key_X: "cut",
                         Qt.Key.Key_C: "copy", Qt.Key.Key_V: "paste"}[key]
            self.window.selection_command(operation)
            return True
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt):
            return False
        if self.pending:
            group = self.pending
            self.clear()
            if key == Qt.Key.Key_Escape:
                return True
            if group == "component":
                if key == Qt.Key.Key_A:
                    self.window.open_add_menu()
                    return True
                categories = {Qt.Key.Key_E: 0, Qt.Key.Key_S: 1, Qt.Key.Key_I: 2,
                              Qt.Key.Key_C: 3, Qt.Key.Key_M: 4}
                if key in categories:
                    self.window.open_library(categories[key])
                    return True
            elif key == Qt.Key.Key_S:
                self.window.add_sheet()
                return True
        if key == Qt.Key.Key_A and mods in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier):
            self.pending = "component" if mods == Qt.KeyboardModifier.ControlModifier else "tools"
            self.timer.start(2000)
            self.window.statusBar().showMessage(self.window.t("Choose the next shortcut letter…", "Naciśnij drugą literę skrótu…"), 2000)
            return True
        if not mods:
            if key == Qt.Key.Key_H:
                self.window.show_component_info()
                return True
            if key == Qt.Key.Key_S:
                self.window.select_action.trigger()
                return True
            if key == Qt.Key.Key_D:
                self.window.wire_action.trigger()
                return True
            if key == Qt.Key.Key_X:
                self.window.delete_action.trigger()
                return True
            if key == Qt.Key.Key_Delete:
                if view is not None: view.delete_selected()
                return True
        return False
