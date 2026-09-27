"""Ukryta nazwa nie zostawia pustego, klikalnego pasa pod symbolem."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from app.canvas.component_item import ComponentItem
from app.core.models import ComponentInstance, Wire
from app.core.settings import AppSettings
from app.core.project_file import save_project, load_project
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
BY_NAME = {item.name: item for item in BUILT_IN_ITEMS}


class Rc7Tests(unittest.TestCase):
    def test_toggle_removes_name_band_without_moving_symbol_pins_or_values(self):
        for definition in BUILT_IN_ITEMS:
            if definition.symbol in {"module", "ic", "connector"}:
                continue
            for angle in (0, 90, 180, 270):
                with self.subTest(name=definition.name, angle=angle):
                    c = ComponentInstance(definition.id, 300, 300, rotation=angle)
                    item = ComponentItem(c)
                    before = item._hit_rect
                    pins, position = item.pin_positions(), item.pos()
                    name_rect, value_rect = item.label_rects()
                    old_name_point = name_rect.center()
                    self.assertTrue(item.shape().contains(old_name_point))
                    c.show_name = False
                    item.update_labels()
                    external = before.bottom() > item._symbol_rect.bottom()
                    self.assertEqual(item._hit_rect.height(), before.height()-(20 if external else 0))
                    self.assertEqual(item._hit_rect.top(), before.top())
                    self.assertEqual(item.shape().contains(old_name_point), not external)
                    self.assertTrue(item.label_rects()[0].isEmpty())
                    self.assertEqual(item.label_rects()[1], value_rect)
                    self.assertEqual(item.pin_positions(), pins)
                    self.assertEqual(item.pos(), position)
                    for pin in pins:
                        self.assertTrue(item.shape().contains(item.mapFromScene(pin)) or
                                        item._hit_rect.contains(item.mapFromScene(pin)))
                    c.show_name = True
                    item.update_labels()
                    self.assertEqual(item._hit_rect, before)
                    self.assertEqual(item.pin_positions(), pins)

    def test_hidden_gate_initializes_as_two_by_two(self):
        c = ComponentInstance(BY_NAME["Bramka AND"].id, 0, 0, show_name=False)
        item = ComponentItem(c)
        self.assertEqual(item._hit_rect, item._symbol_rect)
        self.assertEqual(item._hit_rect.width(), 40)
        self.assertEqual(item._hit_rect.height(), 40)

    def test_module_body_is_not_a_removable_name_band(self):
        for name in ("Arduino Uno R3", "Układ Scalony NE555"):
            c = ComponentInstance(BY_NAME[name].id, 0, 0)
            item = ComponentItem(c)
            before, pins = item._hit_rect, item.pin_positions()
            c.show_name = False
            item.update_labels()
            self.assertEqual(item._hit_rect, before)
            self.assertEqual(item.pin_positions(), pins)

    def test_scene_hit_testing_undo_and_els_preserve_hidden_geometry(self):
        window = MainWindow(AppSettings(), start_setup=False)
        try:
            c = window.add_component_from_id(BY_NAME["Kondensator Ceramiczny"].id)
            view = window._current_view()
            item = view._component_items[c.id]
            original = item._hit_rect
            name_point = item.mapToScene(item.label_rects()[0].center())
            self.assertIn(item, view.scene.items(name_point))
            pin = item.pin_positions()[0]
            wire = Wire(pin.x()-40, pin.y(), pin.x(), pin.y(), end_component_id=c.id, end_pin_index=0)
            view._sheet.wires.append(wire)
            view._add_wire_item(wire)
            window.record_history()
            c.show_name = False
            view.refresh_component(c.id)
            window.record_history()
            self.assertNotIn(item, view.scene.items(name_point))
            self.assertEqual(item.pin_positions()[0], QPointF(wire.end_x, wire.end_y))
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "hidden.els"
                save_project(path, window.project)
                restored = load_project(path)
                loaded = ComponentItem(restored.sheets[0].components[0])
                self.assertEqual(loaded._hit_rect, item._hit_rect)
            window.undo()
            self.assertEqual(window._current_view()._component_items[c.id]._hit_rect, original)
            window.redo()
            self.assertEqual(window._current_view()._component_items[c.id]._hit_rect.height(), original.height()-20)
        finally:
            window._saved_state = window.project.to_dict()
            window.close()
            window.deleteLater()
            APP.processEvents()
