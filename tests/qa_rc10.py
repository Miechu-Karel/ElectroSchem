"""Podglądy UI rc10 bez sieci i rzeczywistych ustawień użytkownika."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.ai_dialog import AiDialog
from app.ui.settings_dialog import SettingsDialog


def preview():
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(QFont("Arial", 10))
    output = Path("tmp/qa/rc10")
    output.mkdir(parents=True, exist_ok=True)
    settings = AppSettings(language="pl", api_key="dummy-visual-test")
    window = MainWindow(settings, start_setup=False)
    for name, dialog in (("chat", AiDialog(settings, {}, lambda p: None, window)),
                         ("documentation", AiDialog(settings, {}, lambda p: None, window, documentation=True)),
                         ("settings", SettingsDialog(AppSettings(language="pl"), window))):
        if name == "chat":
            dialog._pending_prompt = "Jak dodać rezystor i podłączyć go do LED?"
            dialog._completed({"summary": "Wybierz rezystor i LED z biblioteki, a następnie połącz ich piny narzędziem D. Mogę też przygotować propozycję schematu do zastosowania.",
                               "components": [], "wires": [], "custom_components": []})
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(output / (name + ".png")))
        dialog.close()
    window._saved_state = window.project.to_dict()
    window.close()
    print(output.resolve())


if __name__ == "__main__":
    preview()
