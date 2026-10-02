"""rc14: AI nie jest dostępne także przy zachowanym kluczu ze starszej wersji."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow, APP_VERSION
from app.ui.settings_dialog import SettingsDialog

APP = QApplication.instance() or QApplication([])


class Rc14Tests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(api_key="legacy-dummy-key", ai_chat_consent=True), start_setup=False)
        self.window.show()
        self.window.activateWindow()
        self.window._current_view().setFocus()
        APP.processEvents()

    def tearDown(self):
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_no_ai_actions_with_legacy_key_in_both_languages(self):
        self.assertEqual(APP_VERSION, "1.1.0")
        for language in ("en", "pl"):
            self.window.settings.language = language
            self.window._translate_ui()
            for action in (self.window.ai_action, self.window.datasheet_action):
                self.assertFalse(action.isVisible())
                self.assertFalse(action.isEnabled())
                self.assertNotIn(action, self.window.toolbar.actions())
                for top in self.window.menuBar().actions():
                    if top.menu():
                        self.assertNotIn(action, top.menu().actions())

    def test_direct_calls_and_old_shortcut_do_nothing(self):
        self.window.show_ai()
        self.window.show_datasheet_ai()
        self.window.ai_action.trigger()
        self.assertIsNone(self.window.ai_panel)
        self.assertIsNone(self.window.ai_dock)
        with patch.object(self.window, "show_ai") as call:
            QTest.keyClick(self.window._current_view(), Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)
            QTest.keyClick(self.window._current_view(), Qt.Key.Key_I)
            call.assert_not_called()

    def test_settings_and_welcome_hide_all_ai_rows(self):
        for language in ("en", "pl"):
            for first in (False, True):
                settings = AppSettings(language=language, api_key="legacy-dummy-key", ai_chat_consent=True)
                dialog = SettingsDialog(settings, first_run=first)
                dialog.show()
                APP.processEvents()
                for field in (dialog.key, dialog.model, dialog.ai_consent):
                    self.assertFalse(field.isVisible())
                    self.assertFalse(dialog.form.labelForField(field).isVisible())
                self.assertFalse(dialog.key_note.isVisible())
                visible = " ".join(label.text() for label in dialog.findChildren(QLabel) if label.isVisible())
                self.assertNotIn("Gemini", visible)
                self.assertNotIn("AI", visible)
                dialog._accept()
                self.assertEqual(dialog.result_settings().api_key, "legacy-dummy-key")
                self.assertTrue(dialog.result_settings().ai_chat_consent)
                dialog.deleteLater()

    def test_help_does_not_advertise_retired_features(self):
        for language in ("en", "pl"):
            self.window.settings.language = language
            from app.ui.manual_dialog import ManualDialog
            captured=[]
            def capture(dialog):
                captured.append(dialog.browser.toPlainText())
                return 0
            with patch.object(ManualDialog,"exec",capture):
                self.window.show_help()
            text = captured[0]
            self.assertNotIn("AI", text)
            self.assertNotIn("datasheet", text)
            self.assertNotIn("dokumentacji", text)


if __name__ == "__main__":
    # Ręczny podgląd PL/EN nie czyta ani nie zapisuje ustawień użytkownika.
    from PySide6.QtGui import QFont, QFontDatabase
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    APP.setFont(QFont("Arial", 10))
    output = Path("tmp/qa/rc14")
    output.mkdir(parents=True, exist_ok=True)
    for language in ("pl", "en"):
        window = MainWindow(AppSettings(language=language, api_key="legacy-dummy-key"), start_setup=False)
        window.resize(1200, 800)
        window.show()
        APP.processEvents()
        window.grab().save(str(output / (language + "-main.png")))
        dialog = SettingsDialog(window.settings, first_run=True)
        dialog.show()
        APP.processEvents()
        dialog.grab().save(str(output / (language + "-settings.png")))
        dialog.close()
        window.close()
