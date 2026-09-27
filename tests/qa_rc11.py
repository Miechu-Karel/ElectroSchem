"""Podgląd pełnego okna z bocznym panelem i ustawieniami. Bez sieci."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.libraries.built_in import BUILT_IN_ITEMS


def preview():
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(QFont("Arial", 10))
    output = Path("tmp/qa/rc13")
    output.mkdir(parents=True, exist_ok=True)
    window = MainWindow(AppSettings(language="pl", api_key="offline-preview"), start_setup=False)
    window.resize(1440, 900)
    window.show()
    window.show_ai()
    app.processEvents()
    panel = window.ai_panel
    panel._pending_prompt = "Dodaj dwa rezystory po 1 kΩ i połącz je ze sobą."
    panel._message("user", panel._pending_prompt)
    panel._snapshot = deepcopy(window.project.to_dict())
    panel._sheet_id = window.project.sheets[0].id
    resistor = next(d for d in BUILT_IN_ITEMS if d.name == "Rezystor")
    panel._completed({"summary": "Przygotowałem dwa rezystory po 1 kΩ i przewód łączący ich piny. Sprawdź propozycję poniżej i kliknij Zastosuj zmiany.",
                      "components": [{"key": "r1", "library_id": resistor.id, "x": 200, "y": 200, "value": "1", "unit": "kΩ"},
                                     {"key": "r2", "library_id": resistor.id, "x": 440, "y": 200, "value": "1", "unit": "kΩ"}],
                      "wires": [{"from": "r1", "to": "r2", "from_pin": 1, "to_pin": 0}], "custom_components": []})
    app.processEvents()
    window.grab().save(str(output / "proposal.png"))
    panel.apply()
    app.processEvents()
    window.grab().save(str(output / "applied.png"))
    dialog = SettingsDialog(window.settings, window)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / "settings.png"))
    dialog.close()
    window._saved_state = window.project.to_dict()
    window.close()
    print(output.resolve())


if __name__ == "__main__":
    preview()
