"""Program stdin/stdout, not a host shell or unrestricted Python REPL."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit, QLineEdit

class PythonConsole(QWidget):
    def __init__(self, window, cid):
        super().__init__(window, Qt.WindowType.Window)
        self.window, self.cid = window, cid
        self.setWindowIcon(window.windowIcon())
        self.setWindowTitle(window.symbols[cid].component.reference+" - Python")
        self.resize(720, 420)
        layout=QVBoxLayout(self)
        self.note=QLabel(window.t("Simulated program I/O: print, input, sys.stdin/stdout/stderr. No OS shell or arbitrary host execution.",
            "Wejście i wyjście programu: print, input, sys.stdin/stdout/stderr. Bez powłoki systemowej i wykonywania kodu na komputerze."))
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.output=QPlainTextEdit(); self.output.setReadOnly(True); layout.addWidget(self.output)
        self.entry=QLineEdit(); self.entry.setPlaceholderText(window.t("Program input; Enter to send", "Wejście programu; Enter wysyła"))
        self.entry.returnPressed.connect(self.submit); layout.addWidget(self.entry)
        from app.ui.theme import apply_theme
        apply_theme(self, window.editor.settings)

    def submit(self):
        script=self.window.console_script(self.cid)
        if script is None: return
        script.submit_input(self.entry.text()); self.entry.clear()
        if not self.window.timer.isActive(): self.window.single_step()
        self.window.refresh_consoles()

    def toPlainText(self): return self.output.toPlainText()
    def setPlainText(self, text): self.output.setPlainText(text)
    def verticalScrollBar(self): return self.output.verticalScrollBar()
