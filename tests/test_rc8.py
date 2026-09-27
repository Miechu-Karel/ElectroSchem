"""Ukrywanie wartości zwalnia pas, ale nie odłącza pinów ani drugiej wartości."""
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


class Rc8Tests(unittest.TestCase):
    def test_value_toggle_shrinks_top_band_and_restores_it_after_rotation(self):
        for name, unit in (("Rezystor", "Ω"), ("Kondensator Ceramiczny", "nF"),
                           ("Cewka Indukcyjna", "mH"), ("Bateria 9V", "V")):
            for angle in (0, 90, 180, 270):
                with self.subTest(name=name, angle=angle):
                    c = ComponentInstance(BY_NAME[name].id, 300, 300, rotation=angle, value="100", unit=unit)
                    item = ComponentItem(c)
                    before, pins, position = item._hit_rect, item.pin_positions(), item.pos()
                    name_band, value_band = item.label_rects()
                    c.show_value = False
                    item.update_labels()
                    external = before.top() < item._symbol_rect.top()
                    self.assertEqual(item._hit_rect.top(), before.top()+(20 if external else 0))
                    self.assertEqual(item._hit_rect.bottom(), before.bottom())
                    self.assertEqual(item.shape().contains(value_band.center()), not external)
                    self.assertTrue(item.label_rects()[1].isEmpty())
                    self.assertEqual(item.label_rects()[0], name_band)
                    self.assertEqual(item.pin_positions(), pins)
                    self.assertEqual(item.pos(), position)
                    c.show_value = True
                    item.update_labels()
                    self.assertEqual(item._hit_rect, before)
                    self.assertEqual(item.label_rects()[1], value_band)

    def test_capacitor_band_exists_if_either_value_is_visible(self):
        for primary, secondary in ((True, True), (False, True), (True, False), (False, False)):
            c = ComponentInstance(BY_NAME["Kondensator Ceramiczny"].id, 0, 0, value="300", unit="nF",
                                  show_value=primary, properties={"voltage": "25 V", "show_voltage": secondary})
            item = ComponentItem(c)
            self.assertEqual(item.label_rects()[1].isEmpty(), not (primary or secondary))
            self.assertEqual(item._hit_rect.top(), item._symbol_rect.top()-(20 if primary or secondary else 0))

    def test_extra_colour_also_releases_band(self):
        c = ComponentInstance(BY_NAME["Dioda LED 5mm"].id, 0, 0,
                              properties={"color": "red", "show_color": True})
        item = ComponentItem(c)
        self.assertFalse(item.label_rects()[1].isEmpty())
        c.properties["show_color"] = False
        item.update_labels()
        self.assertTrue(item.label_rects()[1].isEmpty())

    def test_both_hidden_and_empty_values_leave_no_reserved_bands(self):
        for name in ("Rezystor", "Przycisk Tact Switch", "Bramka AND"):
            for value, unit, visible in (("100", "Ω", False), ("", "", True)):
                c = ComponentInstance(BY_NAME[name].id, 0, 0, value=value, unit=unit,
                                      show_value=visible, show_name=False)
                item = ComponentItem(c)
                self.assertEqual(item._hit_rect, item._symbol_rect)
                self.assertTrue(all(rect.isEmpty() for rect in item.label_rects()))

    def test_module_body_keeps_its_geometry(self):
        c = ComponentInstance(BY_NAME["Stabilizator Liniowy LM7805"].id, 0, 0, value="5", unit="V")
        item = ComponentItem(c)
        before, pins = item._hit_rect, item.pin_positions()
        c.show_name = c.show_value = False
        item.update_labels()
        self.assertEqual(item._hit_rect, before)
        self.assertEqual(item.pin_positions(), pins)

    def test_scene_hit_testing_wire_undo_and_file_roundtrip(self):
        window = MainWindow(AppSettings(), start_setup=False)
        try:
            c = window.add_component_from_id(BY_NAME["Kondensator Ceramiczny"].id)
            view = window._current_view()
            c.value, c.unit = "10", "nF"
            view.refresh_component(c.id)
            item = view._component_items[c.id]
            before = item._hit_rect
            value_point = item.mapToScene(item.label_rects()[1].center())
            pin = item.pin_positions()[0]
            wire = Wire(pin.x()-40, pin.y(), pin.x(), pin.y(), end_component_id=c.id, end_pin_index=0)
            view._sheet.wires.append(wire)
            view._add_wire_item(wire)
            window.record_history()
            self.assertIn(item, view.scene.items(value_point))
            c.show_value = False
            view.refresh_component(c.id)
            window.record_history()
            self.assertNotIn(item, view.scene.items(value_point))
            self.assertEqual(item.pin_positions()[0], QPointF(wire.end_x, wire.end_y))
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "rc8.els"
                save_project(path, window.project)
                restored = load_project(path)
                loaded = ComponentItem(restored.sheets[0].components[0])
                self.assertEqual(loaded._hit_rect, item._hit_rect)
                self.assertEqual(loaded.value_text, "10 nF")  # Dane są ukryte, nie usunięte.
                self.assertFalse(loaded.show_value)
            window.undo()
            self.assertEqual(window._current_view()._component_items[c.id]._hit_rect, before)
            window.redo()
            self.assertEqual(window._current_view()._component_items[c.id]._hit_rect.height(), before.height()-20)
        finally:
            window._saved_state = window.project.to_dict()
            window.close()
            window.deleteLater()
            APP.processEvents()
