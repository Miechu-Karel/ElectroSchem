"""Jawny (--live) test panelu z Gemini na NOWYM, SZTUCZNYM dokumencie.

Nie czyta projektów użytkownika, nie zapisuje ustawień, nie wypisuje klucza.
Sprawdza propozycję -> przycisk zastosowania -> połączenie pinów -> dalszy czat.
"""
import os
import sys
import getpass
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from app.core.project_file import save_project
from app.core.settings import AppSettings, load_settings
from app.ui.main_window import MainWindow


def main():
    replay = "--replay-blinker" in sys.argv
    if "--live" not in sys.argv and not replay:
        print("SKIPPED: use --live for the synthetic API test.")
        return 0
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(QFont("Arial", 10))
    key = "offline-replay" if replay else ((getpass.getpass("Temporary API key (hidden): ") if sys.stdin.isatty() else sys.stdin.readline().strip()) if "--key-stdin" in sys.argv else load_settings().api_key)
    if not key:
        print("SKIPPED: no saved API key.")
        return 0
    window = MainWindow(AppSettings(api_key=key, language="pl"), start_setup=False)
    window.resize(1440, 1000)
    window.show()
    window.show_ai()
    panel = window.ai_panel
    panel._consented = True  # --live jest jawną zgodą na wysłanie syntetycznych danych
    phase, result = ["build"], [1]

    def finish(code):
        result[0] = code
        panel.cancel()
        window._saved_state = window.project.to_dict()
        window.close()
        app.quit()

    def completed(proposal):
        if "--blinker" in sys.argv or replay:
            # Wyłącznie syntetyczny wynik AI, bez klucza i bez istniejących plików.
            output = Path("tmp/qa/rc13-blinker")
            output.mkdir(parents=True, exist_ok=True)
            from PySide6.QtCore import QFile, QIODevice
            data = QFile(str(output / "proposal.json"))
            if data.open(QIODevice.OpenModeFlag.WriteOnly):
                data.write(json.dumps(proposal, ensure_ascii=False, indent=2).encode("utf-8"))
                data.close()
            app.processEvents()
            window.grab().save(str(output / "preview.png"))
            print("PREVIEW:", panel._candidate is not None, flush=True)
            panel.apply()
            if not window.project.sheets[0].components:
                print("FAIL:", panel.status.text().encode("ascii", "backslashreplace").decode(), flush=True)
                finish(1)
                return
            save_project(output / "blinker.els", window.project)
            app.processEvents()
            window.grab().save(str(output / "applied.png"))
            print("PASS: applied blinker; inspect tmp/qa/rc13-blinker", flush=True)
            finish(0)
            return
        if phase[0] == "build":
            panel.apply()
            sheet = window.project.sheets[0]
            if len(sheet.components) != 2 or len(sheet.wires) != 1:
                print("FAIL: expected two components and one applied wire.", flush=True)
                finish(1)
                return
            wire = sheet.wires[0]
            if not wire.start_component_id or not wire.end_component_id:
                print("FAIL: missing pin anchors.", flush=True)
                finish(1)
                return
            print("PASS: live panel generated and applied two resistors and an anchored wire.", flush=True)
            phase[0] = "ask"
            panel.mode.setCurrentIndex(panel.mode.findData("ask"))
            panel.prompt.setPlainText("Jaką rezystancję mają dodane rezystory? Odpowiedz krótko.")
            QTimer.singleShot(0, panel.send)
        else:
            if not proposal["summary"].strip() or panel._proposal is not None:
                finish(1)
                return
            print("PASS: follow-up chat returned an answer without modifying the schematic.", flush=True)
            window.undo()
            if window.project.sheets[0].components or window.project.sheets[0].wires:
                print("FAIL: undo did not restore the initial document.", flush=True)
                finish(1)
                return
            print("PASS: undo restored the initial synthetic document.", flush=True)
            finish(0)

    def failed(code):
        print("FAIL:", code, flush=True)
        finish(1)

    panel.client.completed.connect(completed)
    panel.client.failed.connect(failed)
    panel.client.progress.connect(lambda stage: print("STAGE:", stage, flush=True))
    QTimer.singleShot(240000, lambda: failed("test_timeout"))
    panel.prompt.setPlainText("Dodaj dokładnie dwa rezystory po 1 kΩ, pierwszy w x=200 y=200, drugi w x=440 y=200. Połącz prawy pin pierwszego z lewym pinem drugiego jednym przewodem. Nie dodawaj innych elementów ani definicji customowych.")
    if "--blinker" in sys.argv or replay:
        panel.prompt.setPlainText("Zrób obwód elektroniczny zasilany z 5V sprawiający że Dioda LED będzie migać co ok. 1s użyj tranzystorów PN2222")
    if replay:
        from copy import deepcopy
        def replay_result():
            panel._snapshot = deepcopy(window.project.to_dict())
            panel._sheet_id = window.project.sheets[0].id
            panel._pending_prompt = panel.prompt.toPlainText()
            panel._message("user", panel._pending_prompt)
            panel.prompt.clear()
            proposal = json.loads(Path("tmp/qa/rc13-blinker/proposal.json").read_text(encoding="utf-8"))
            panel._completed(proposal)
            completed(proposal)
        QTimer.singleShot(0, replay_result)
    else:
        QTimer.singleShot(0, panel.send)
    app.exec()
    return result[0]


if __name__ == "__main__":
    raise SystemExit(main())
