import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPointF, Qt, QSettings
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QColorDialog

from app.canvas.component_item import ComponentItem
from app.canvas.schematic_view import SchematicView
from app.core.models import ComponentInstance, Project, Wire
from app.core.project_file import load_project, save_project
from app.core.settings import AppSettings, load_settings, save_settings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import APP_VERSION, ICON_DIR, MainWindow

APP = QApplication.instance() or QApplication([])


def item_named(name):
    return next(item for item in BUILT_IN_ITEMS if item.name == name)


class Alpha140A7Tests(unittest.TestCase):
    def test_version_shortcut_labels_and_toolbar_order(self):
        window = MainWindow(AppSettings(), start_setup=False)
        try:
            self.assertEqual(APP_VERSION, "1.4.0")
            self.assertNotIn("Alt+O", window.quick_open_action.text())
            self.assertNotIn("Alt+S", window.quick_save_action.text())
            self.assertEqual(window.quick_open_action.shortcut().toString(), "Alt+O")
            self.assertEqual(window.quick_save_action.shortcut().toString(), "Alt+S")
            self.assertLessEqual(len(window.quick_open_action.text()), 24)
            self.assertLessEqual(len(window.quick_save_action.text()), 24)
            window.settings.language = "pl"
            window._translate_ui()
            self.assertEqual(window.quick_open_action.text(), "Otwórz domyślny projekt")
            self.assertEqual(window.quick_save_action.text(), "Zapisz domyślny projekt")
            self.assertFalse(window.paint_wire_action.icon().isNull())
            self.assertTrue((ICON_DIR / "paint_wire.png").is_file())
            actions = window.toolbar.actions()
            positions = [actions.index(action) for action in (
                window.delete_action, window.paint_wire_action, window.wire_action)]
            self.assertEqual(positions, sorted(positions))
        finally:
            window._saved_state = window.project.to_dict()
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_flame_sensor_uses_plain_module_body(self):
        definition = item_named("Czujnik Płomienia")
        item = ComponentItem(ComponentInstance(definition.id, 0, 0))
        image = QImage(320, 180, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.translate(160, 90)
        item.paint(painter, None)
        painter.end()
        # The old board used a distinctive green fill; the default module
        # renderer now shows only its neutral rectangle, title and pins.
        colors={image.pixelColor(x,y).rgba() for y in range(image.height())
                for x in range(image.width())}
        self.assertNotIn(QColor("#267247").rgba(), colors)

    def test_two_terminal_motor_has_no_phantom_servo_pins(self):
        definition = item_named("Mini silnik MT64 3-6V")
        self.assertEqual(len(definition.pins), 2)
        item = ComponentItem(ComponentInstance(definition.id, 0, 0))
        image = QImage(400, 200, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.translate(200, 100)
        item.paint(painter, None)
        painter.end()
        # The old renderer drew two extra servo leads at y=±20 even though
        # this motor only has its two horizontal terminals.
        self.assertEqual(image.pixelColor(130, 80), QColor("white"))
        self.assertEqual(image.pixelColor(130, 120), QColor("white"))

    def test_servo_pin_labels_are_readable_outside_the_symbol(self):
        definition = item_named("Serwomechanizm SG90")
        item = ComponentItem(ComponentInstance(definition.id, 0, 0))
        image = QImage(400, 200, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.translate(200, 100)
        item.paint(painter, None)
        painter.end()
        # The controller and motor are shifted right, leaving longer leads;
        # each signal name is placed once above its lead.
        self.assertEqual(image.pixelColor(150, 80), QColor("#163247"))
        self.assertEqual(image.pixelColor(160, 80), QColor("#163247"))
        self.assertEqual(image.pixelColor(170, 80), QColor("white"))
        for y in (66, 86, 106):
            ink = sum(1 for py in range(y, y + 12) for px in range(121, 178)
                      if image.pixelColor(px, py).value() < 150)
            self.assertGreater(ink, 0, f"No pin label above lead near y={y}")

    def test_wire_color_paints_whole_routed_wire_and_only_changes_appearance(self):
        project = Project()
        sheet = project.sheets[0]
        points = [[100.0, 100.0], [160.0, 100.0], [160.0, 200.0], [240.0, 200.0]]
        wire = Wire(100, 100, 240, 200, points=points)
        sheet.wires.append(wire)
        view = SchematicView(project=project, settings=AppSettings(language="pl", wire_paint_color="#aabbcc"), sheet=sheet)
        view.resize(800, 600)
        view.show()
        view.set_tool("wire_color", "#aabbcc")
        before = (wire.start_x, wire.start_y, wire.end_x, wire.end_y,
                  [point[:] for point in wire.points], wire.start_component_id,
                  wire.end_component_id, wire.start_junction_id, wire.end_junction_id)
        changed = []
        view.on_change = lambda: changed.append(True)
        try:
            APP.processEvents()
            with patch.object(QColorDialog, "getColor") as choose_color:
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                                 pos=view.mapFromScene(QPointF(125, 100)))
                choose_color.assert_not_called()
            APP.processEvents()
            self.assertEqual(wire.paint_color, "#aabbcc")
            item = view._wire_items[wire.id]
            self.assertEqual(item.paint_color, "#aabbcc")
            self.assertEqual(item.points, [QPointF(*point) for point in points])
            image=QImage(300,300,QImage.Format.Format_ARGB32)
            image.fill(QColor("white"))
            painter=QPainter(image)
            item.paint(painter,None)
            painter.end()
            for x,y in ((125,100),(160,150),(220,200)):
                self.assertEqual(image.pixelColor(x,y),QColor("#aabbcc"))
            self.assertEqual((wire.start_x, wire.start_y, wire.end_x, wire.end_y,
                              wire.points, wire.start_component_id, wire.end_component_id,
                              wire.start_junction_id, wire.end_junction_id), before)
            self.assertEqual(len(changed), 1)
        finally:
            view.close()
            view.deleteLater()
            APP.processEvents()

    def test_wire_paint_follows_only_a_single_unbranched_wire_neighbor(self):
        project = Project()
        sheet = project.sheets[0]
        seed = Wire(100, 100, 200, 100)
        continuation = Wire(200, 100, 300, 100)
        tail = Wire(300, 100, 400, 100)
        sheet.wires.extend((seed, continuation, tail))
        view = SchematicView(project=project, settings=AppSettings(), sheet=sheet)
        try:
            self.assertTrue(view._paint_wire_chain(seed, "#123abc"))
            self.assertEqual([wire.paint_color for wire in sheet.wires], ["#123abc"] * 3)
        finally:
            view.close()
            view.deleteLater()
            APP.processEvents()

        project = Project()
        sheet = project.sheets[0]
        seed = Wire(100, 100, 200, 100)
        straight = Wire(200, 100, 300, 100)
        branch = Wire(300, 100, 300, 200)
        beyond_branch = Wire(300, 100, 400, 100)
        sheet.wires.extend((seed, straight, branch, beyond_branch))
        view = SchematicView(project=project, settings=AppSettings(), sheet=sheet)
        try:
            view._paint_wire_chain(seed, "#123abc")
            self.assertEqual(seed.paint_color, "#123abc")
            self.assertEqual(straight.paint_color, "#123abc")
            self.assertIsNone(branch.paint_color)
            self.assertIsNone(beyond_branch.paint_color)
        finally:
            view.close()
            view.deleteLater()
            APP.processEvents()

    def test_wire_paint_stops_at_component_pin(self):
        project = Project()
        sheet = project.sheets[0]
        seed = Wire(100, 100, 200, 100, end_component_id="pin-component")
        beyond_pin = Wire(200, 100, 300, 100)
        sheet.wires.extend((seed, beyond_pin))
        view = SchematicView(project=project, settings=AppSettings(), sheet=sheet)
        try:
            view._paint_wire_chain(seed, "#123abc")
            self.assertEqual(seed.paint_color, "#123abc")
            self.assertIsNone(beyond_pin.paint_color)
        finally:
            view.close()
            view.deleteLater()
            APP.processEvents()

    def test_wire_paint_walks_each_direction_and_stops_at_pin_or_branch(self):
        project = Project()
        sheet = project.sheets[0]
        # A meets the selected cable B at one end, and a VCC pin at the other.
        cable_a = Wire(100, 100, 200, 200, start_component_id="vcc-pin")
        cable_b = Wire(200, 200, 800, 200)
        cable_c = Wire(800, 200, 900, 100)
        cable_d = Wire(800, 200, 850, 300)
        beyond_vcc = Wire(100, 100, 50, 100)
        sheet.wires.extend((cable_a, cable_b, cable_c, cable_d, beyond_vcc))
        view = SchematicView(project=project, settings=AppSettings(), sheet=sheet)
        try:
            self.assertTrue(view._paint_wire_chain(cable_b, "#123abc"))
            self.assertEqual(cable_b.paint_color, "#123abc")
            self.assertEqual(cable_a.paint_color, "#123abc")
            self.assertIsNone(cable_c.paint_color)
            self.assertIsNone(cable_d.paint_color)
            self.assertIsNone(beyond_vcc.paint_color)
        finally:
            view.close()
            view.deleteLater()
            APP.processEvents()

    def test_wire_paint_uses_shared_junction_id_when_coordinates_drift(self):
        project = Project()
        sheet = project.sheets[0]
        seed = Wire(100, 100, 200, 100, end_junction_id="shared-node")
        continuation = Wire(200.01, 100, 300, 100, start_junction_id="shared-node")
        sheet.wires.extend((seed, continuation))
        view = SchematicView(project=project, settings=AppSettings(), sheet=sheet)
        view.resize(800, 600)
        view.show()
        view.set_tool("wire_color", "#123abc")
        try:
            APP.processEvents()
            with patch.object(QColorDialog, "getColor") as choose_color:
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                                 pos=view.mapFromScene(QPointF(125, 100)))
                choose_color.assert_not_called()
            APP.processEvents()
            self.assertEqual(seed.paint_color, "#123abc")
            self.assertEqual(continuation.paint_color, "#123abc")
        finally:
            view.close()
            view.deleteLater()
            APP.processEvents()

    def test_paint_color_is_chosen_on_tool_activation_and_persisted(self):
        settings = AppSettings(language="pl", wire_paint_color="#167d3d")
        window = MainWindow(settings, start_setup=False)
        try:
            with patch("app.ui.main_window.QColorDialog.getColor", side_effect=[QColor("#aabbcc"), QColor()]) as picker, \
                 patch("app.ui.main_window.save_settings") as save:
                window.set_active_tool("wire_color")
                window.set_active_tool("wire_color")
            self.assertEqual(picker.call_count, 2)
            self.assertEqual(picker.call_args_list[1].args[0], QColor("#aabbcc"))
            save.assert_called_once_with(settings)
            self.assertEqual(settings.wire_paint_color, "#aabbcc")
            self.assertEqual(window._current_view().wire_paint_color, "#aabbcc")
        finally:
            window._saved_state = window.project.to_dict()
            window.close()
            window.deleteLater()
            APP.processEvents()

    def test_paint_color_setting_round_trips_and_invalid_value_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            store = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings = AppSettings(wire_paint_color="#12abef")
            save_settings(settings, store)
            self.assertEqual(load_settings(store).wire_paint_color, "#12abef")
            store.setValue("wire_paint_color", "not-a-color")
            self.assertEqual(load_settings(store).wire_paint_color, AppSettings().wire_paint_color)

    def test_wire_color_survives_save_load_and_old_readers_reject_v5(self):
        project = Project()
        project.sheets[0].wires.append(Wire(
            100, 100, 200, 100,
            points=[[100, 100], [150, 100], [150, 140], [200, 100]],
            paint_color="#aabbcc"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "colored.els"
            save_project(path, project)
            restored = load_project(path)
            with patch("app.core.project_file.FORMAT_VERSION", 4):
                with self.assertRaisesRegex(ValueError, "Unsupported ELS package version"):
                    load_project(path)
        self.assertEqual(restored.sheets[0].wires[0].paint_color, "#aabbcc")
        self.assertEqual(restored.format_version, 5)


if __name__ == "__main__":
    unittest.main()
