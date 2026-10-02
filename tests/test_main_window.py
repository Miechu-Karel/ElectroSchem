"""Sprawdzenie zintegrowanego okna bez sieci i bez zapisu preferencji użytkownika."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox

from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import APP_VERSION, MainWindow

APP = QApplication.instance() or QApplication([])
RESISTOR = next(item for item in BUILT_IN_ITEMS if item.name == "Rezystor")


class MainWindowTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(), start_setup=False)
        self.window.show()
        self.window.activateWindow()
        self.window._current_view().setFocus()
        APP.processEvents()

    def tearDown(self):
        # Test nie otwiera pytania o zapis dokumentu podczas sprzątania.
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_version_localization_icons_and_no_properties_dock(self):
        window = self.window
        self.assertEqual(APP_VERSION, "1.1.0")
        self.assertFalse(window.windowIcon().isNull())
        self.assertEqual({size.width() for size in window.windowIcon().availableSizes()},
                         {72,144,432,576})
        self.assertEqual(window.tools_heading.text(), "BASIC TOOLS")
        self.assertFalse(window.ai_action.isEnabled())
        self.assertFalse(window.datasheet_action.isEnabled())
        self.assertFalse(window.comment_action.icon().isNull())
        self.assertFalse(hasattr(window, "properties_widget"))
        window.settings.language = "pl"
        window._translate_ui()
        self.assertEqual(window.tools_heading.text(), "PODSTAWOWE NARZĘDZIA")
        self.assertEqual(window.new_action.text(), "Nowy projekt…")

    def test_add_undo_redo_sheets_and_document_save(self):
        window = self.window
        component = window.add_component_from_id(RESISTOR.id)
        self.assertEqual(component.reference, "Res001")
        self.assertTrue(window._is_dirty())
        window.undo()
        self.assertFalse(window._is_dirty())
        window.redo()
        self.assertEqual(len(window.project.sheets[0].components), 1)
        window.add_sheet()
        self.assertEqual(window.tabs.count(), 2)
        window.undo()
        self.assertEqual(window.tabs.count(), 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "project.els"
            self.assertTrue(window._write_project(path))
            self.assertFalse(window._is_dirty())
            restored = load_project(path)
            self.assertEqual(restored.sheets[0].components[0].reference, "Res001")

    def test_select_does_not_open_properties_but_explicit_edit_does(self):
        window = self.window
        with patch("app.ui.main_window.ComponentPropertiesDialog") as dialog:
            component = window.add_component_from_id(RESISTOR.id)
            dialog.assert_not_called()
            self.assertTrue(window.properties_action.isEnabled())
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            window.edit_selected_properties()
            self.assertIs(dialog.call_args.args[0], component)

    def test_shortcuts_keep_ctrl_a_inside_text_fields(self):
        window = self.window
        view = window._current_view()
        QTest.keyClick(view, Qt.Key.Key_D)
        self.assertEqual(view.tool, "wire")
        QTest.keyClick(view, Qt.Key.Key_S)
        self.assertEqual(view.tool, "select")
        with patch.object(window, "open_library") as opened:
            QTest.keyClick(view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClick(view, Qt.Key.Key_E)
            opened.assert_called_once_with(0)
        text = QLineEdit("normal text", window)
        text.show()
        text.setFocus()
        APP.processEvents()
        QTest.keyClick(text, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(text.selectedText(), "normal text")
        self.assertIsNone(window.shortcuts.pending)
        text.deleteLater()

    def test_failed_save_retains_original_path_and_dirty_state(self):
        window = self.window
        window.add_component_from_id(RESISTOR.id)
        window.current_file = Path("original.els")
        with patch("app.ui.main_window.save_project", side_effect=OSError("test failure")), patch.object(window, "_error"):
            self.assertFalse(window._write_project(Path("new.els")))
        self.assertEqual(window.current_file, Path("original.els"))
        self.assertTrue(window._is_dirty())

    def test_ai_context_contains_pin_indices_without_api_key(self):
        window = self.window
        window.settings.api_key = "DO-NOT-SEND-THIS-AS-CONTEXT"
        window.add_component_from_id(RESISTOR.id)
        context = window._ai_context()
        self.assertNotIn(window.settings.api_key, repr(context))
        resistor = next(item for item in context["library"] if item["id"] == RESISTOR.id)
        self.assertEqual(resistor["pins"][0]["index"], 0)
        self.assertEqual(context["grid_step"], 20)


if __name__ == "__main__":
    unittest.main()
