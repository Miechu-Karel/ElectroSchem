"""Opcjonalny test prawdziwego API: uruchamiaj jawnie z --live.

Wysyła wyłącznie syntetyczne polecenie. Nie wypisuje klucza, ustawień ani
danych projektu. Diagnostyka 400 dotyczy tylko sztucznego żądania i usuwa
klucz z komunikatu. Nie należy do unittest discover.
"""
import os
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtWidgets import QApplication
from app.core.settings import load_settings
from app.services.gemini import GeminiClient, request_body
from app.services.proposals import apply_proposal
from app.core.models import Project
from app.libraries.built_in import BUILT_IN_ITEMS


def main():
    if "--live" not in sys.argv:
        print("SKIPPED: pass --live to send a synthetic test to Gemini.")
        return 0
    app = QApplication.instance() or QApplication([])
    settings = load_settings()
    if "--key-stdin" in sys.argv:
        settings.api_key = sys.stdin.readline().strip()
    if not settings.api_key:
        print("SKIPPED: no saved Gemini API key.")
        return 0
    definition = next(d for d in BUILT_IN_ITEMS if d.name == "Rezystor")
    context = {"sheet": {"components": [], "wires": []}, "grid_step": 20,
               "drawing_area_scene": [40, 40, 1120, 640],
               "library": [{"id": definition.id, "name": "Resistor", "pins": [
                   {"index": i, "number": p.number, "name": p.name, "x": p.x, "y": p.y}
                   for i, p in enumerate(definition.pins)]}]}
    class SyntheticDiagnosticClient(GeminiClient):
        def _finished(self):
            if self.reply and "--plain" in sys.argv and self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 200 and self._phase == "generate":
                self._read_available()
                response = json.loads(bytes(self._buffer))
                print("PLAIN GENERATION:", bool(response.get("candidates")), flush=True)
            if self.reply and self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) == 400:
                self._read_available()
                try:
                    message = json.dumps(json.loads(bytes(self._buffer)).get("error", {}))
                    print("SYNTHETIC REQUEST DIAGNOSTIC:", message.replace(settings.api_key, "[redacted]")[:2000])
                except (ValueError, AttributeError):
                    pass
            super()._finished()
    client = SyntheticDiagnosticClient()
    client.progress.connect(lambda stage: print("STAGE:", stage, flush=True))
    code = [1]
    def complete(proposal):
        try:
            if "--plain" in sys.argv:
                if not proposal["summary"].strip():
                    raise ValueError("Empty answer")
                print("PASS: real Gemini chat answer received.")
                code[0] = 0
                app.quit()
                return
            result = apply_proposal(Project(), 0, proposal)
            if len(result.sheets[0].components) != 1:
                raise ValueError("Expected one resistor")
            print("PASS: model detection, generation, validation and application of one synthetic resistor.")
            code[0] = 0
        except (ValueError, TypeError, KeyError):
            print("FAIL: synthetic proposal could not be applied.")
        app.quit()
    def failed(reason):
        print("FAIL:", reason)  # wyłącznie lokalny, kontrolowany kod błędu
        app.quit()
    client.completed.connect(complete)
    client.failed.connect(failed)
    client.cancelled.connect(app.quit)
    QTimer.singleShot(180000, client.cancel)
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "auto"
    body = request_body("Add exactly one 1 kOhm resistor at x=200 y=200. No wires or custom components. Summary: API test.", context)
    if "--plain" in sys.argv:
        body = json.dumps({"contents": [{"role": "user", "parts": [{"text": "Reply with the single word OK."}]}],
                           "generationConfig": {"maxOutputTokens": 1024, "responseMimeType": "text/plain"}}).encode()
    client.start(settings.api_key, model, body)
    app.exec()
    return code[0]


if __name__ == "__main__":
    raise SystemExit(main())
