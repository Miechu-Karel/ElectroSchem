"""Regresje rc5: menu nie zmieniają starych ID ani połączeń ELS."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu

from app.canvas.page import modification_label
from app.core.models import Project
from app.core.project_file import save_project, load_project
from app.core.settings import AppSettings
from app.libraries.built_in import AVAILABLE_ITEMS, BUILT_IN_ITEMS, HIDDEN_NAMES, get_definition
from app.libraries.menu_groups import subgroup
from app.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
BY_NAME = {item.name: item for item in BUILT_IN_ITEMS}


def placement_actions(menu):
    """Przechodzimy także podmenu; akcje administracyjne nie mają ID."""
    for action in menu.actions():
        if action.menu():
            yield from placement_actions(action.menu())
        elif action.data():
            yield action


class Rc5CatalogTests(unittest.TestCase):
    def test_hidden_definitions_still_load_without_replacement(self):
        self.assertFalse(HIDDEN_NAMES & {item.name for item in AVAILABLE_ITEMS})
        project = Project()
        for name in HIDDEN_NAMES:
            item = BY_NAME[name]
            self.assertIs(get_definition(item.id), item)
            project.sheets[0].components.append(project.new_component(item.id, 200, 200))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.els"
            save_project(path, project)
            self.assertEqual(load_project(path).to_dict(), project.to_dict())
        self.assertEqual(len(AVAILABLE_ITEMS), 145)

    def test_mcp3008_pdip_pinout(self):
        item = BY_NAME["Przetwornik ADC MCP3008"]
        expected = "CH0 CH1 CH2 CH3 CH4 CH5 CH6 CH7 DGND CS/SHDN DIN DOUT CLK AGND VREF VDD".split()
        self.assertEqual({pin.number: pin.name for pin in item.pins},
                         {str(i): name for i, name in enumerate(expected, 1)})
        self.assertNotEqual(item.id, BY_NAME["Układ MCP2008 (niezweryfikowany)"].id)

    def test_new_modules_use_named_terminals(self):
        relay = BY_NAME["Moduł Przekaźnika 1-kanałowy z optoizolacją 5V"]
        servo = BY_NAME["Serwomechanizm EF90D 360° (praca ciągła)"]
        self.assertEqual({p.number for p in relay.pins}, {"VCC", "GND", "IN", "NO", "COM", "NC"})
        self.assertEqual({p.number for p in servo.pins}, {"GND", "VCC", "PWM"})

    def test_separate_boards_and_logic_packages(self):
        self.assertEqual(subgroup(BY_NAME["Arduino Uno R3"]), ("Arduino", "Arduino"))
        self.assertEqual(subgroup(BY_NAME["Raspberry Pi Pico"]), ("Raspberry Pi", "Raspberry Pi"))
        self.assertNotEqual(subgroup(BY_NAME["Bramka AND"]), subgroup(BY_NAME["Bramka Logiczna 74HC00"]))

    def test_old_document_has_no_fabricated_date(self):
        data = Project().to_dict()
        data.pop("metadata", None)
        self.assertEqual(modification_label(Project.from_dict(data)), "Modified: —")


class Rc5WindowTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(), start_setup=False)
        self.window.show()
        self.window.activateWindow()
        self.window._current_view().setFocus()
        APP.processEvents()

    def tearDown(self):
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_every_available_item_has_one_primary_menu_action(self):
        ids = []
        for index in range(5):
            menu = QMenu(self.window)
            self.window._populate_library_menu(menu, index, QPoint(200, 200))
            actions = list(placement_actions(menu))
            ids.extend(action.data() for action in actions if not action.property("secondaryEntry"))
            if index == 1:
                self.assertTrue(any("ef90d" in action.data().lower() for action in actions))
            menu.deleteLater()
        self.assertCountEqual(ids, [item.id for item in AVAILABLE_ITEMS])
        self.assertEqual(len(ids), len(set(ids)))

    def test_add_anything_shortcut_with_ctrl_held_or_released(self):
        view = self.window._current_view()
        for modifier in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier):
            with patch.object(self.window, "open_add_menu") as opened:
                QTest.keyClick(view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
                QTest.keyClick(view, Qt.Key.Key_A, modifier)
                opened.assert_called_once_with()

    def test_menu_placement_uses_original_cursor_position(self):
        menu = QMenu(self.window)
        position = QPoint(400, 250)
        self.window._populate_library_menu(menu, 2, position)
        action = next(placement_actions(menu))
        with patch.object(self.window, "add_component_from_id") as add:
            action.trigger()
            add.assert_called_once_with(action.data(), global_pos=position)

    def test_modification_date_changes_only_on_content_changes_and_survives_save(self):
        window = self.window
        old = window.project.metadata["modified_at"]
        stamp = datetime(2030, 1, 2, 12, 30, tzinfo=timezone.utc)
        with patch("app.ui.main_window.datetime") as clock:
            clock.now.return_value = stamp
            window.record_history()
            self.assertEqual(window.project.metadata["modified_at"], old)
            window.project.name = "Changed title"
            window.record_history()
            expected = stamp.astimezone().isoformat(timespec="seconds")
            self.assertEqual(window.project.metadata["modified_at"], expected)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "date.els"
            self.assertTrue(window._write_project(path))
            self.assertEqual(load_project(path).metadata["modified_at"], expected)
        self.assertIn("2030-01-02", modification_label(window.project, "pl"))
