"""Panel czatu, format Gemini i ustawienie katalogu. Testy bez sieci."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QDockWidget, QDialog

from app.core.settings import AppSettings, documents_directory, file_dialog_directory, load_settings, save_settings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.services.gemini import GeminiClient, request_body
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.ai_dialog import AiDialog
from test_ai_settings import FakeReply, empty_proposal

APP = QApplication.instance() or QApplication([])
RES = next(d for d in BUILT_IN_ITEMS if d.name == "Rezystor")


class FolderTests(unittest.TestCase):
    def test_system_documents_default_and_missing_folder_fallback(self):
        self.assertEqual(AppSettings().default_directory, documents_directory())
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(default_directory=directory)
            self.assertEqual(file_dialog_directory(settings), directory)
            settings.default_directory = str(Path(directory) / "not-created")
            self.assertEqual(file_dialog_directory(settings), documents_directory())
            self.assertFalse(Path(settings.default_directory).exists())

    def test_folder_settings_roundtrip_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "preferences.ini"), QSettings.Format.IniFormat)
            settings = AppSettings(default_directory=directory)
            save_settings(settings, store)
            self.assertEqual(load_settings(store).default_directory, directory)
            dialog = SettingsDialog(settings)
            dialog.directory.setText("this is invalid")
            with patch("app.ui.settings_dialog.QMessageBox.warning") as warning:
                dialog._accept()
                warning.assert_called_once()
                self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            dialog.directory.setText(directory)
            dialog._accept()
            self.assertEqual(dialog.result_settings().default_directory, directory)
            self.assertEqual(settings.default_directory, directory)
            dialog.deleteLater()


class GeminiFormatTests(unittest.TestCase):
    def test_build_json_is_locally_validated_without_server_compiler(self):
        body = json.loads(request_body("add a resistor", {}))
        config = body["generationConfig"]
        self.assertNotIn("responseJsonSchema", config)
        self.assertNotIn("responseSchema", config)
        self.assertNotIn("temperature", config)
        self.assertEqual(config["responseMimeType"], "application/json")
        instruction = body["systemInstruction"]["parts"][0]["text"]
        self.assertIn('"custom_components"', instruction)
        self.assertIn("never executable code", instruction)

    def test_plain_chat_is_separate_from_proposal_parser(self):
        body = request_body("explain", {}, chat_only=True)
        self.assertEqual(json.loads(body)["generationConfig"]["responseMimeType"], "text/plain")
        reply = FakeReply(body=json.dumps({"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": "A resistor limits current."}]}}]}).encode())
        client, completed = GeminiClient(), []
        client.completed.connect(completed.append)
        with patch.object(client.manager, "post", return_value=reply):
            client.start("dummy-key", "gemini-test-flash", body)
            reply.finished.emit()
        self.assertEqual(completed[0]["summary"], "A resistor limits current.")
        self.assertEqual(completed[0]["components"], [])

    def test_json_mode_never_accepts_arbitrary_commands(self):
        proposal = empty_proposal()
        proposal["execute"] = "unsafe"
        reply = FakeReply(body=json.dumps({"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps(proposal)}]}}]}).encode())
        client, errors, complete = GeminiClient(), [], []
        client.failed.connect(errors.append)
        client.completed.connect(complete.append)
        with patch.object(client.manager, "post", return_value=reply):
            client.start("dummy-key", "gemini-test-flash", request_body("build", {}))
            reply.finished.emit()
        self.assertEqual(errors, ["invalid_response"])
        self.assertEqual(complete, [])

    def test_delayed_retry_keeps_busy_and_can_be_cancelled(self):
        client = GeminiClient()
        reply = FakeReply(status=503)
        cancelled = []
        client.cancelled.connect(lambda: cancelled.append(True))
        with patch.object(client.manager, "post", return_value=reply) as post:
            client.start("dummy-key", "gemini-test-flash", request_body("build", {}))
            reply.finished.emit()
            self.assertTrue(client.busy)
            with self.assertRaises(ValueError):
                client.start("dummy-key", "auto", request_body("again", {}))
            client.cancel()
            client._run_retry()
            self.assertEqual(post.call_count, 1)
        self.assertEqual(cancelled, [True])
        self.assertFalse(client.busy)
        self.assertEqual(client._api_key, "")


@unittest.skip("Historyczna integracja AI wycofana w rc14; blokady sprawdza test_rc14")
class PanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow(AppSettings(language="pl", api_key="dummy-test-key", default_directory=self.temp.name), start_setup=False)
        self.window.show()
        self.window.show_ai()
        APP.processEvents()
        self.panel = self.window.ai_panel
        self.panel._consented = True

    def tearDown(self):
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def send_fake(self, text="Dodaj rezystor", mode="build"):
        self.panel.mode.setCurrentIndex(self.panel.mode.findData(mode))
        self.panel.prompt.setPlainText(text)
        with patch.object(self.panel.client, "start") as start:
            self.panel.send()
            self.assertTrue(start.called)
            return json.loads(start.call_args.args[2])

    def proposal(self):
        proposal = empty_proposal()
        proposal["summary"] = "Przygotowano rezystor."
        proposal["components"] = [{"key": "r", "library_id": RES.id, "x": 200, "y": 200, "value": "1", "unit": "kΩ"}]
        return proposal

    def test_nonmodal_dock_reopens_without_losing_conversation(self):
        self.assertIsInstance(self.window.ai_dock, QDockWidget)
        self.assertIsNone(QApplication.activeModalWidget())
        self.send_fake()
        self.panel._completed(self.proposal())
        self.window.ai_dock.hide()
        self.window.show_ai()
        self.assertIs(self.window.ai_panel, self.panel)
        self.assertEqual(len(self.panel.history), 2)
        self.assertFalse(self.panel.proposal_card.isHidden())

    def test_build_apply_then_followup_uses_fresh_sheet(self):
        self.send_fake()
        self.panel._completed(self.proposal())
        self.assertEqual(len(self.window.project.sheets[0].components), 0)
        self.panel.apply()
        self.assertEqual(len(self.window.project.sheets[0].components), 1)
        self.assertIsNone(self.panel._proposal)
        body = self.send_fake("Co teraz?", "ask")
        self.assertEqual(body["generationConfig"]["responseMimeType"], "text/plain")
        self.assertIn("Res001", body["contents"][-1]["parts"][0]["text"])
        self.assertNotIn("dummy-test-key", json.dumps(body))
        self.panel._completed(empty_proposal())
        self.window.undo()
        self.assertEqual(len(self.window.project.sheets[0].components), 0)

    def test_stale_response_cannot_overwrite_manual_changes(self):
        self.send_fake()
        self.panel._completed(self.proposal())
        self.window.project.metadata["author"] = "Updated while waiting"
        snapshot = deepcopy(self.window.project.to_dict())
        self.panel.apply()
        self.assertEqual(self.window.project.to_dict(), snapshot)
        self.assertFalse(self.panel.apply_button.isEnabled())
        self.assertIn("zmienił", self.panel.status.text())

    def test_proposal_stays_on_original_sheet_if_user_switches_tabs(self):
        self.window.add_sheet()
        self.window.tabs.setCurrentIndex(0)
        self.send_fake()
        self.window.tabs.setCurrentIndex(1)
        self.panel._completed(self.proposal())
        self.panel.apply()
        self.assertEqual(len(self.window.project.sheets[0].components), 1)
        self.assertEqual(len(self.window.project.sheets[1].components), 0)

    def test_ask_never_offers_modifications_and_errors_restore_input(self):
        self.send_fake("Wyjaśnij", "ask")
        self.panel._completed(self.proposal())
        self.assertIsNone(self.panel._proposal)
        self.assertTrue(self.panel.proposal_card.isHidden())
        self.assertEqual(len(self.window.project.sheets[0].components), 0)
        self.send_fake("Dodaj układ")
        self.panel._failed("http_429")
        self.assertEqual(self.panel.prompt.toPlainText(), "Dodaj układ")
        self.assertFalse(self.panel._busy)

    def test_enter_sends_shift_enter_adds_line(self):
        self.panel.prompt.setFocus()
        self.panel.prompt.setPlainText("test")
        QTest.keyClick(self.panel.prompt, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.assertIn("\n", self.panel.prompt.toPlainText())
        with patch.object(self.panel.client, "start") as start:
            QTest.keyClick(self.panel.prompt, Qt.Key.Key_Return)
            start.assert_called_once()
        self.panel._cancelled()

    def test_new_chat_clears_proposal_and_history(self):
        self.send_fake()
        self.panel._completed(self.proposal())
        self.panel.new_chat()
        self.assertIsNone(self.panel._proposal)
        self.assertEqual(self.panel.history, [])
        self.assertTrue(self.panel.proposal_card.isHidden())

    def test_consent_is_once_per_session_not_each_message(self):
        self.panel._consented = False
        with patch("app.ui.ai_panel.remember_chat_consent"), patch("app.ui.ai_panel.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes) as confirm:
            self.send_fake()
            self.panel._completed(empty_proposal())
            self.send_fake("Następne pytanie")
            self.assertEqual(confirm.call_count, 1)
        self.panel._cancelled()

    def test_file_dialogs_always_start_in_configured_folder(self):
        folder = self.temp.name
        with patch("app.ui.main_window.QFileDialog.getOpenFileName", return_value=("", "")) as opened:
            self.window.open_project()
            self.assertEqual(opened.call_args.args[2], folder)
        self.window.current_file = Path(folder).parent / "elsewhere.els"
        with patch("app.ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")) as save:
            self.window.save_project_as()
            self.assertEqual(Path(save.call_args.args[2]).parent, Path(folder))
            self.assertEqual(Path(save.call_args.args[2]).name, "elsewhere.els")
            self.window.export_pdf()
            self.assertEqual(Path(save.call_args.args[2]).parent, Path(folder))
        dialog = AiDialog(self.window.settings, {}, lambda p: None, documentation=True)
        with patch("app.ui.ai_dialog.QFileDialog.getOpenFileName", return_value=("", "")) as pdf:
            dialog._choose_pdf()
            self.assertEqual(pdf.call_args.args[2], folder)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
