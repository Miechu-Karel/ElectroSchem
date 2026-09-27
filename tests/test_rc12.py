"""Regresje rc12: zgoda, język i ponowne użycie działającego modelu."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from app.core.settings import AppSettings, remember_chat_consent, load_settings, save_settings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.libraries.catalog_text import catalog_text
from app.services.gemini import GeminiClient, request_body
from app.ui.i18n import install_ui_language
from app.ui.settings_dialog import SettingsDialog
from test_ai_settings import FakeReply

APP = QApplication.instance() or QApplication([])


class Rc12Tests(unittest.TestCase):
    def tearDown(self):
        install_ui_language("en")

    def test_consent_persists_without_saving_key_and_can_be_revoked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings = AppSettings(api_key="not-a-real-key")
            remember_chat_consent(settings, store)
            self.assertTrue(settings.ai_chat_consent)
            self.assertEqual(store.allKeys(), ["ai_chat_consent"])
            restored = load_settings(store)
            self.assertTrue(restored.ai_chat_consent)
            restored.ai_chat_consent = False
            save_settings(restored, store)
            self.assertFalse(load_settings(store).ai_chat_consent)

    def test_settings_exposes_and_preserves_consent(self):
        dialog = SettingsDialog(AppSettings(ai_chat_consent=True))
        self.assertTrue(dialog.ai_consent.isChecked())
        dialog.ai_consent.setChecked(False)
        dialog._accept()
        self.assertTrue(dialog.result_settings().ai_chat_consent)  # rc14 zachowuje ukryte preferencje
        dialog.deleteLater()

    def test_standard_yes_no_buttons_follow_application_language(self):
        for language, expected in (("pl", ("Tak", "Nie")), ("en", ("Yes", "No"))):
            install_ui_language(language)
            box = QMessageBox()
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            actual = tuple(box.button(button).text().replace("&", "") for button in
                           (QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No))
            self.assertEqual(actual, expected)
            box.deleteLater()

    def test_builtin_descriptions_are_translated_except_package_codes(self):
        codes = {"", "PC817 DIP-4", "TI PDIP-14", "DIP-14 / SOIC-14", "DIP-16 / SOIC-16",
                 "DIP-28 / SOIC-28", "DIP-8 / SOIC-8", "PDIP-18 / SOIC-18"}
        for definition in BUILT_IN_ITEMS:
            for text in (definition.variant, definition.pin_scope):
                self.assertEqual(catalog_text(text, "en"), text)
                if text not in codes:
                    self.assertNotEqual(catalog_text(text, "pl"), text, text)
        self.assertEqual(catalog_text("Standard AND Gate schematic symbol", "pl"), "Standardowy symbol bramki AND")
        self.assertEqual(catalog_text("User-defined text", "pl"), "User-defined text")

    def test_successful_model_reused_only_for_same_key(self):
        client = GeminiClient()
        models = {"models": [{"name": "models/" + name, "supportedGenerationMethods": ["generateContent"]}
                              for name in ("gemini-3.8-flash", "gemini-3.5-flash-lite")]}
        body = request_body("hello", {}, chat_only=True)
        success = FakeReply(body=json.dumps({"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": "Hello"}]}}]}).encode())
        with patch.object(client.manager, "post", return_value=success):
            client.start("dummy-key", "gemini-3.5-flash-lite", body)
            success.finished.emit()
        for key, expected in (("dummy-key", "gemini-3.5-flash-lite"), ("different-key", "gemini-3.8-flash")):
            listing = FakeReply(body=json.dumps(models).encode())
            with patch.object(client.manager, "get", return_value=listing), patch.object(client, "_generate_with") as generate:
                client.start(key, "auto", body)
                listing.finished.emit()
                generate.assert_called_once_with(expected)
                if key == "different-key":
                    self.assertEqual(client._fallback_model["name"], "models/gemini-3.5-flash-lite")
