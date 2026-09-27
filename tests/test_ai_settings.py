"""Testy offline: żaden test nie wysyła danych ani nie używa prawdziwego API.

Każdy QSettings używa osobnego pliku tymczasowego, więc uruchomienie testów
nie zmienia preferencji ani klucza API zapisanego przez użytkownika.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QObject, QSettings, Signal
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QDialog

from app.core.settings import AppSettings, _dpapi, default_editor, load_settings, save_settings
from app.services.gemini import GeminiClient, MAX_RESPONSE_BYTES, parse_proposal, request_body, validate_proposal
from app.ui.ai_dialog import AiDialog
from app.ui.settings_dialog import SettingsDialog


def empty_proposal():
    return {"summary": "Example", "components": [], "wires": [], "custom_components": []}


def custom_definition():
    return {"id": "custom-demo", "name": "Przykład", "name_en": "Example",
            "reference_prefix": "Cus", "width": 120, "height": 80,
            "pins": [{"number": "1", "name": "VCC", "x": -20, "y": 40},
                     {"number": "2", "name": "GND", "x": 20, "y": 40}]}


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = QSettings(str(Path(self.directory.name) / "settings.ini"), QSettings.Format.IniFormat)

    def tearDown(self):
        self.store.sync()
        self.directory.cleanup()

    def test_defaults_and_no_secret_in_repr(self):
        with patch("app.core.settings.detected_editors", return_value=[]):
            settings = load_settings(self.store)
        self.assertEqual((settings.language, settings.standard, settings.paper_size), ("en", "EN", "A4"))
        self.assertFalse(settings.setup_complete)
        self.assertEqual(settings.api_key, "")
        self.assertNotIn("fake-test-secret", repr(AppSettings(api_key="fake-test-secret")))

    def test_editor_priority_matches_user_request(self):
        editors = [("VSCodium", "codium.exe"), ("Notepad++", "notepad++.exe"), ("Notepad", "notepad.exe")]
        self.assertEqual(default_editor(editors), "notepad.exe")
        editors.append(("Visual Studio Code", "Code.exe"))
        self.assertEqual(default_editor(editors), "Code.exe")

    def test_encrypted_storage_and_removal(self):
        settings = AppSettings(language="pl", api_key="fake-test-secret", setup_complete=True, grid_visible=False)
        with patch("app.core.settings._dpapi", return_value=b"encrypted-test-blob"):
            save_settings(settings, self.store)
        self.assertFalse(self.store.contains("api_key"))
        self.assertFalse(self.store.contains("gemini_api_key"))
        self.assertNotIn("fake-test-secret", str(self.store.value("gemini_key_dpapi")))
        with patch("app.core.settings._dpapi", return_value=b"fake-test-secret"):
            restored = load_settings(self.store)
        self.assertEqual(restored.api_key, settings.api_key)
        self.assertEqual(restored.language, "pl")
        self.assertFalse(restored.grid_visible)
        self.assertTrue(restored.setup_complete)
        restored.api_key = ""
        save_settings(restored, self.store)
        self.assertFalse(self.store.contains("gemini_key_dpapi"))

    def test_crypto_failure_does_not_write_plaintext_or_other_settings(self):
        self.store.setValue("language", "en")
        with patch("app.core.settings._dpapi", side_effect=OSError("test")):
            with self.assertRaises(OSError):
                save_settings(AppSettings(language="pl", api_key="fake-test-secret"), self.store)
        self.assertEqual(self.store.value("language"), "en")
        self.assertFalse(self.store.contains("api_key"))

    def test_corrupt_settings_recover(self):
        for key in ("language", "standard", "paper_size", "orientation", "gemini_model"):
            self.store.setValue(key, "invalid/value")
        self.store.setValue("gemini_key_dpapi", "invalid base64 !")
        settings = load_settings(self.store)
        self.assertEqual(settings.language, "en")
        self.assertEqual(settings.standard, "EN")
        self.assertEqual(settings.paper_size, "A4")
        self.assertEqual(settings.orientation, "landscape")
        self.assertEqual(settings.gemini_model, AppSettings().gemini_model)
        self.assertEqual(settings.api_key, "")

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI")
    def test_real_dpapi_roundtrip_with_dummy_bytes(self):
        protected = _dpapi(b"public-test-value-not-a-real-key")
        self.assertNotEqual(protected, b"public-test-value-not-a-real-key")
        self.assertEqual(_dpapi(protected, decrypt=True), b"public-test-value-not-a-real-key")


class ProposalTests(unittest.TestCase):
    def test_valid_proposal_and_pdf_request(self):
        proposal = empty_proposal()
        proposal["custom_components"] = [custom_definition()]
        self.assertEqual(parse_proposal(json.dumps(proposal)), proposal)
        body = json.loads(request_body("Create example", {"sheet": {"name": "Demo"}}, "pl", b"%PDF-1.7\nexample"))
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("Polish", body["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(body["contents"][0]["parts"][1]["inline_data"]["mime_type"], "application/pdf")
        self.assertNotIn("api_key", body)

    def test_unknown_fields_and_duplicate_json_rejected(self):
        proposal = empty_proposal()
        proposal["execute_code"] = "arbitrary executable content"
        with self.assertRaises(ValueError):
            validate_proposal(proposal)
        with self.assertRaises(ValueError):
            parse_proposal('{"summary":"one","summary":"two","components":[],"wires":[],"custom_components":[]}')

    def test_nonfinite_boolean_and_duplicate_component_coordinates_rejected(self):
        for coordinate in (float("nan"), float("inf"), True, "20"):
            proposal = empty_proposal()
            proposal["components"] = [{"key": "a", "library_id": "resistor", "x": coordinate, "y": 20}]
            with self.subTest(coordinate=coordinate), self.assertRaises(ValueError):
                validate_proposal(proposal)
        proposal = empty_proposal()
        component = {"key": "a", "library_id": "resistor", "x": 20, "y": 20}
        proposal["components"] = [component, deepcopy(component)]
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_custom_pin_geometry_and_id_rejected(self):
        invalid_definitions = []
        for field, value in (("width", 123), ("height", -40), ("id", "builtin-resistor"),
                             ("reference_prefix", "bad\nprefix")):
            definition = custom_definition()
            definition[field] = value
            invalid_definitions.append(definition)
        for point in ((0, 0), (11, 40), (200, 40)):
            definition = custom_definition()
            definition["pins"][0].update(x=point[0], y=point[1])
            invalid_definitions.append(definition)
        for definition in invalid_definitions:
            proposal = empty_proposal()
            proposal["custom_components"] = [definition]
            with self.subTest(definition=definition), self.assertRaises(ValueError):
                validate_proposal(proposal)

    def test_pin_duplicates_and_boolean_indexes_rejected(self):
        proposal = empty_proposal()
        definition = custom_definition()
        definition["pins"][1]["number"] = "1"
        proposal["custom_components"] = [definition]
        with self.assertRaises(ValueError):
            validate_proposal(proposal)
        proposal = empty_proposal()
        proposal["wires"] = [{"from": "a", "to": "b", "from_pin": True, "to_pin": 0}]
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_invalid_request_and_attachment_rejected(self):
        with self.assertRaises(ValueError):
            request_body("", {})
        with self.assertRaises(ValueError):
            request_body("test", {}, pdf_data=b"not a PDF")
        with self.assertRaises(ValueError):
            request_body("test", {"x": float("inf")})


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_setup_can_be_completed_without_key_and_translated(self):
        settings = AppSettings()
        dialog = SettingsDialog(settings, first_run=True)
        self.assertEqual(dialog.language.currentData(), "en")
        self.assertEqual(dialog.windowTitle(), "Welcome to ElectroSchem")
        dialog.language.setCurrentIndex(dialog.language.findData("pl"))
        self.assertEqual(dialog.windowTitle(), "Witaj w ElectroSchem")
        dialog._accept()
        result = dialog.result_settings()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(result.api_key, "")
        self.assertTrue(result.setup_complete)
        self.assertFalse(settings.setup_complete)
        self.assertEqual(settings.language, "en")
        dialog.deleteLater()

    def test_ai_disabled_without_key(self):
        dialog = AiDialog(AppSettings(), {}, lambda value: None)
        self.assertFalse(dialog.generate_button.isEnabled())
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.reject()
        dialog.deleteLater()

    def test_proposal_is_previewed_then_applied_once(self):
        applied = []
        dialog = AiDialog(AppSettings(), {}, applied.append)
        proposal = empty_proposal()
        proposal["custom_components"] = [custom_definition()]
        dialog._completed(proposal)
        self.assertEqual(applied, [])
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertIn("custom-demo", dialog.preview.toPlainText())
        dialog._apply()
        dialog._apply()
        self.assertEqual(len(applied), 1)
        self.assertNotIn("summary", applied[0])
        dialog.deleteLater()

    def test_client_rejects_invalid_secret_before_network(self):
        client = GeminiClient()
        with patch.object(client.manager, "post") as post:
            for key in ("", "has spaces", "non-ascii-ą"):
                with self.assertRaises(ValueError):
                    client.start(key, "gemini-2.5-flash", b"{}")
            with self.assertRaises(ValueError):
                client.start("fake-test-key", "../evil", b"{}")
            post.assert_not_called()


class FakeReply(QObject):
    """Minimalny dubler odpowiedzi Qt; nie otwiera żadnego połączenia."""
    readyRead = Signal()
    finished = Signal()

    def __init__(self, status=200, body=b""):
        super().__init__()
        self.status, self.body, self.aborted = status, body, False

    def read(self, limit):
        result, self.body = self.body[:limit], self.body[limit:]
        return QByteArray(result)

    def attribute(self, attribute):
        return self.status

    def error(self):
        return (QNetworkReply.NetworkError.OperationCanceledError if self.aborted
                else QNetworkReply.NetworkError.NoError)

    def abort(self):
        if not self.aborted:
            self.aborted = True
            self.finished.emit()


class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def start_client(self, reply):
        client = GeminiClient()
        self.completed, self.failed, self.cancelled = [], [], []
        client.completed.connect(self.completed.append)
        client.failed.connect(self.failed.append)
        client.cancelled.connect(lambda: self.cancelled.append(True))
        with patch.object(client.manager, "post", return_value=reply) as post:
            client.start("dummy-key", "gemini-2.5-flash", b"{}")
            self.request = post.call_args.args[0]
        return client

    def test_request_key_is_in_header_not_url_and_success_parses(self):
        proposal = empty_proposal()
        response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(proposal)}]}}]}
        reply = FakeReply(body=json.dumps(response).encode())
        client = self.start_client(reply)
        self.assertNotIn("dummy-key", self.request.url().toString())
        self.assertEqual(bytes(self.request.rawHeader("x-goog-api-key")), b"dummy-key")
        self.assertEqual(self.request.attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute),
                         QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        reply.readyRead.emit()
        reply.finished.emit()
        self.assertEqual(self.completed, [proposal])
        self.assertEqual(self.failed, [])
        self.assertIsNone(client.reply)

    def test_http_error_does_not_expose_response_body(self):
        reply = FakeReply(status=403, body=b"private project text and dummy-key")
        client = self.start_client(reply)
        reply.finished.emit()
        self.assertEqual(self.failed, ["http_403"])
        self.assertEqual(self.completed, [])
        self.assertIsNone(client.reply)

    def test_cancel_timeout_and_oversized_response(self):
        for reason in ("cancel", "timeout", "size"):
            reply = FakeReply(body=b"x" * (MAX_RESPONSE_BYTES + 100) if reason == "size" else b"")
            client = self.start_client(reply)
            if reason == "cancel":
                client.cancel()
                self.assertEqual(self.cancelled, [True])
                self.assertEqual(self.failed, [])
            elif reason == "timeout":
                client._timeout()
                self.assertEqual(self.failed, ["timeout"])
            else:
                reply.readyRead.emit()
                self.assertEqual(self.failed, ["response_too_large"])
            self.assertEqual(self.completed, [])
            self.assertIsNone(client.reply)

    def test_incomplete_and_invalid_response_never_applied(self):
        for body, expected in ((b'{"candidates":[{"finishReason":"MAX_TOKENS"}]}', "incomplete"),
                               (b'{"candidates":[]}', "blocked"),
                               (b'not json', "invalid_response")):
            reply = FakeReply(body=body)
            client = self.start_client(reply)
            reply.finished.emit()
            self.assertEqual(self.completed, [])
            self.assertEqual(self.failed, [expected])
            self.assertIsNone(client.reply)


if __name__ == "__main__":
    unittest.main()
