"""Regresje marginesów oraz edycji/usuwania definicji customowych."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QMenu
from app.canvas.page import frame_rect, page_rect
from app.core.models import Project, Sheet, Wire
from app.core.custom_library import replace_custom
from app.core.settings import AppSettings
from app.core.project_file import load_project
from app.ui.component_dialogs import CustomComponentDialog
from app.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])


def definition():
    return dict(id="custom-rc4", name="Test", name_en="Test", reference_prefix="CusTes",
                width=160, height=120, symbol="module", behavior="preserve notes",
                pins=[dict(number="1", name="IN", x=-80, y=-40),
                      dict(number="2", name="OUT", x=80, y=20)])


class Rc4Tests(unittest.TestCase):
    def test_custom_menu_passes_definition_id_to_edit_and_delete(self):
        window = MainWindow(AppSettings(), start_setup=False)
        window.project.custom_components.append(definition())
        def execute():
            menu = APP.activePopupWidget()
            submenu = menu.actions()[0].menu()
            submenu.actions()[0].trigger()
            submenu.actions()[1].trigger()
            menu.close()
        with patch.object(window, "edit_custom_component") as edit, patch.object(window, "delete_custom_component") as delete:
            QTimer.singleShot(0, execute)
            window.open_library(3)
            edit.assert_called_once_with("custom-rc4")
            delete.assert_called_once_with("custom-rc4")
        window._saved_state = window.project.to_dict()
        window.close()
        window.deleteLater()
        APP.processEvents()

    def test_all_margins_two_cells_plus_fraction(self):
        for size in ("A0", "A1", "A2", "A3", "A4", "A5"):
            for orientation in ("portrait", "landscape"):
                sheet = Sheet(paper_size=size, orientation=orientation)
                frame, page = frame_rect(sheet), page_rect(sheet)
                self.assertEqual(frame.left(), 40)
                self.assertEqual(frame.top(), 40)
                self.assertEqual(page.right()-frame.right(), 40+page.width()%20)
                self.assertEqual(page.bottom()-frame.bottom(), 40+page.height()%20)

    def test_edit_name_preserves_id_metadata_and_exact_pin_coordinates(self):
        old = definition()
        dialog = CustomComponentDialog(definition=old)
        dialog.name.setPlainText("Renamed\nmodule")
        dialog.accept()
        self.assertIsNotNone(dialog.definition)
        self.assertEqual(dialog.definition["id"], old["id"])
        self.assertEqual(dialog.definition["reference_prefix"], "CusTes")
        self.assertEqual(dialog.definition["behavior"], "preserve notes")
        for before, after in zip(old["pins"], dialog.definition["pins"]):
            self.assertEqual((before["x"], before["y"]), (after["x"], after["y"]))
        self.assertEqual(old, definition())
        dialog.deleteLater()

    def test_reordering_pins_uses_numbers_and_removed_pin_disconnects(self):
        old = definition()
        project = Project(custom_components=[old])
        component = project.new_component(old["id"], 300, 300)
        project.sheets[0].components.append(component)
        wire = Wire(220, 260, 380, 320, start_component_id=component.id, start_pin_index=0,
                    end_component_id=component.id, end_pin_index=1)
        project.sheets[0].wires.append(wire)
        new = deepcopy(old)
        new["pins"].reverse()
        replace_custom(project, new)
        self.assertEqual(wire.start_pin_index, 1)
        self.assertEqual(wire.start_pin_number, "1")
        new["pins"] = new["pins"][:1]
        replace_custom(project, new)
        self.assertIsNone(wire.start_component_id)
        self.assertEqual((wire.start_x, wire.start_y), (220, 260))
        self.assertEqual(wire.end_component_id, component.id)
        self.assertEqual(wire.end_pin_index, 0)

    def test_delete_confirm_cancel_undo_and_els(self):
        window = MainWindow(AppSettings(), start_setup=False)
        window.project.custom_components.append(definition())
        component = window.project.new_component("custom-rc4", 300, 300)
        window.project.sheets[0].components.append(component)
        wire = Wire(220, 260, 120, 260, start_component_id=component.id, start_pin_index=0)
        window.project.sheets[0].wires.append(wire)
        window._rebuild_tabs()
        window.record_history()
        before = deepcopy(window.project.to_dict())
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            window.delete_custom_component("custom-rc4")
        self.assertEqual(window.project.to_dict(), before)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            window.delete_custom_component("custom-rc4")
        self.assertFalse(window.project.custom_components)
        self.assertFalse(window.project.sheets[0].components)
        self.assertIsNone(window.project.sheets[0].wires[0].start_component_id)
        window.undo()
        self.assertEqual(window.project.to_dict(), before)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"custom.els"
            self.assertTrue(window._write_project(path))
            self.assertEqual(load_project(path).to_dict(), window.project.to_dict())
        window._saved_state = window.project.to_dict()
        window.close()
        window.deleteLater()
        APP.processEvents()
