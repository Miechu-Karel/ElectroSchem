"""Regresje rc9: wolne miejsce, piny, LED, obszar L i pomoc kontekstowa."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit
from app.canvas.component_item import ComponentItem
from app.canvas.page import drawing_contains, frame_rect, title_block_rect, route_allowed, fit_component_position
from app.core.models import ComponentInstance, Sheet
from app.core.settings import AppSettings
from app.libraries.built_in import AVAILABLE_ITEMS, BUILT_IN_ITEMS, get_definition
from app.libraries.menu_groups import subgroup
from app.libraries.component_info import explanation
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog

APP = QApplication.instance() or QApplication([])
BY_NAME = {d.name: d for d in BUILT_IN_ITEMS}


class Rc9Tests(unittest.TestCase):
    def test_resistor_uses_internal_bands_but_long_name_expands(self):
        c = ComponentInstance(BY_NAME["Rezystor"].id, 0, 0, value="1", unit="kΩ")
        item = ComponentItem(c, language="pl")
        self.assertEqual(item._hit_rect, QRectF(-40, -20, 80, 40))
        name, value = item.label_rects()
        self.assertGreaterEqual(name.top(), 9)
        self.assertLessEqual(value.bottom(), -9)
        pins = item.pin_positions()
        c.display_name = "Bardzo długa nazwa rezystora pomiarowego"
        item.update_labels()
        self.assertEqual(item._hit_rect.bottom(), 40)
        self.assertEqual(item._hit_rect.top(), -20)
        self.assertEqual(item.pin_positions(), pins)
        c.show_name = False
        item.update_labels()
        self.assertEqual(item._hit_rect, item._symbol_rect)

    def test_switch_keeps_external_band_clear_of_contacts(self):
        item = ComponentItem(ComponentInstance(BY_NAME["Przycisk Tact Switch"].id, 0, 0), language="pl")
        self.assertGreater(item.label_rects()[0].top(), 20)
        self.assertEqual(item._hit_rect.bottom(), 40)

    def test_pin_labels_are_upright_for_every_board_and_item_rotation(self):
        item = ComponentItem(ComponentInstance(BY_NAME["Przekaźnik Elektromechaniczny 5V"].id, 0, 0))
        font = QFont("Arial")
        font.setPixelSize(14)
        text = "1 COIL+"
        bounds = QFontMetricsF(font).boundingRect(text)
        for base_angle in (0, 90, -90):
            images = []
            for angle in (0, 90, 180, 270):
                image = QImage(220, 220, QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.white)
                p = QPainter(image)
                p.setFont(font)
                p.translate(110, 110)
                p.rotate(angle+base_angle)
                p.translate(-bounds.center())
                item.setRotation(angle)
                item._pin_label(p, QPointF(0, 0), text, base_angle)
                p.end()
                images.append(image)
            self.assertEqual(images[0], images[2])
            self.assertEqual(images[1], images[3])

    def test_colour_list_has_seven_choices_with_stable_keys(self):
        for language in ("en", "pl"):
            d = BY_NAME["Dioda LED 3mm"]
            c = ComponentInstance(d.id, 0, 0, properties={"color": "Czerwony", "show_color": True})
            dialog = ComponentPropertiesDialog(c, d, language)
            self.assertIsInstance(dialog.extra_value, QComboBox)
            self.assertFalse(dialog.extra_value.isEditable())
            self.assertEqual(dialog.extra_value.count(), 7)
            self.assertEqual(dialog.extra_value.currentData(), "red")
            dialog.extra_value.setCurrentIndex(dialog.extra_value.findData("ir"))
            dialog.accept()
            self.assertEqual(dialog.values["extra_value"], "ir")
            c.properties["color"] = "ir"
            self.assertIn("IR", ComponentItem(c, language=language).extra_text)
            dialog.deleteLater()

    def test_rgb_has_no_single_colour_setting_or_legacy_colour_caption(self):
        d = BY_NAME["Dioda RGB"]
        c = ComponentInstance(d.id, 0, 0, properties={"color": "red", "show_color": True})
        dialog = ComponentPropertiesDialog(c, d)
        self.assertEqual(dialog._extra_key, "")
        self.assertIsNone(dialog.extra_value)
        self.assertEqual(ComponentItem(c).extra_text, "")
        dialog.deleteLater()

    def test_single_board_families_are_other(self):
        for name in ("STM32 Nucleo-F401RE", "Teensy 4.1", "Microbit V2", "Banana Pi M5", "Orange Pi 3 LTS"):
            self.assertEqual(subgroup(BY_NAME[name]), ("Other", "Inne"))

    def test_converter_menu_replacement_preserves_legacy_id(self):
        old = BY_NAME["Konwerter Poziomów Logicznych"]
        new = BY_NAME["Konwerter Poziomów Logicznych Iduino ST1167"]
        self.assertNotIn(old, AVAILABLE_ITEMS)
        self.assertIn(new, AVAILABLE_ITEMS)
        self.assertIs(get_definition(old.id), old)
        self.assertNotEqual(old.id, new.id)
        self.assertEqual(len(new.pins), 12)
        self.assertEqual({p.number for p in new.pins}, {"LV", "LV.GND", "HV", "HV.GND", "CH1.RXO", "CH1.RXI", "CH1.TXO", "CH1.TXI", "CH2.RXO", "CH2.RXI", "CH2.TXO", "CH2.TXI"})

    def test_drawing_area_accepts_left_strip_but_not_table(self):
        for size in ("A0", "A1", "A2", "A3", "A4", "A5"):
            for orientation in ("portrait", "landscape"):
                sheet = Sheet(paper_size=size, orientation=orientation)
                frame, block = frame_rect(sheet), title_block_rect(sheet)
                self.assertFalse(drawing_contains(sheet, block.center()))
                self.assertFalse(drawing_contains(sheet, QPointF(0, 0)))
                if block.left() > frame.left():
                    point = QPointF(frame.left()+20, block.top()+40)
                    self.assertTrue(drawing_contains(sheet, point))
                    bounds = QRectF(-20, -20, 40, 40)
                    fitted = fit_component_position(sheet, bounds, point)
                    self.assertEqual(fitted, point)
                    self.assertTrue(drawing_contains(sheet, bounds.translated(fitted)))

    def test_potentiometer_is_three_terminal_with_separate_wiper(self):
        definition = BY_NAME["Potencjometr Obrotowy"]
        self.assertEqual(len(definition.pins), 3)
        self.assertEqual(next(p.name for p in definition.pins if p.number == "2"), "W")
        self.assertIn("suwak", explanation(definition, "pl"))

    def test_help_covers_menu_and_custom_notes_without_network(self):
        for definition in AVAILABLE_ITEMS:
            for language in ("en", "pl"):
                info = explanation(definition, language)
                self.assertGreater(len(info), 20)  # NOT ma poprawny, bardzo krótki opis.
                self.assertNotIn("not yet available", info)
                self.assertNotIn("nie dodano jeszcze", info)
        self.assertIn("RXI", explanation(BY_NAME["Konwerter Poziomów Logicznych Iduino ST1167"], "pl"))
        self.assertEqual(explanation(BY_NAME["Rezystor"], "pl", {"description": "Notatka", "behavior": "Opis działania"}), "Notatka\n\nOpis działania")


class Rc9WindowTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(language="pl"), start_setup=False)
        self.window.resize(1200, 850)
        self.window.show()
        self.window.activateWindow()
        self.view = self.window._current_view()
        self.view.setFocus()
        APP.processEvents()

    def tearDown(self):
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_wire_and_component_can_be_placed_beside_title_block(self):
        block = title_block_rect(self.view._sheet)
        start = QPointF(100, block.top()+40)
        end = QPointF(200, block.top()+80)
        self.view.set_tool("wire")
        for point in (start, end):
            QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton, pos=self.view.mapFromScene(point))
        self.assertEqual(len(self.view._sheet.wires), 1)
        self.assertTrue(route_allowed(self.view._sheet, [QPointF(*p) for p in self.view._sheet.wires[0].points]))
        c = self.window.add_component_from_id(BY_NAME["Rezystor"].id,
                 global_pos=self.view.mapToGlobal(self.view.mapFromScene(QPointF(300, block.top()+60))))
        self.assertGreater(c.y, block.top())
        self.assertTrue(drawing_contains(self.view._sheet, self.view._component_items[c.id].mapRectToScene(self.view._component_items[c.id]._hit_rect)))

    def test_routes_between_arms_do_not_cross_table(self):
        b = title_block_rect(self.view._sheet)
        start, end = QPointF(b.left()-20, b.bottom()-20), QPointF(b.right()-20, b.top()-20)
        direct = [start, QPointF(end.x(), start.y()), end]
        self.assertFalse(route_allowed(self.view._sheet, direct))
        route = self.view._route_in_drawing_area(start, end)
        self.assertTrue(route_allowed(self.view._sheet, route))
        for a, b in zip(route, route[1:]):
            dx, dy = abs(b.x()-a.x()), abs(b.y()-a.y())
            self.assertTrue(dx == 0 or dy == 0 or dx == dy)

    def test_h_opens_selected_component_info_but_not_in_text_field(self):
        c = self.window.add_component_from_id(BY_NAME["Rezystor"].id)
        before = self.window.project.to_dict()
        with patch("app.ui.main_window.ComponentInfoDialog") as dialog:
            QTest.keyClick(self.view, Qt.Key.Key_H)
            dialog.assert_called_once()
            self.assertIs(dialog.call_args.args[0], c)
            self.assertEqual(self.window.project.to_dict(), before)
            dialog.reset_mock()
            text = QLineEdit(self.window)
            text.show()
            text.setFocus()
            APP.processEvents()
            QTest.keyClicks(text, "h")
            self.assertEqual(text.text(), "h")
            dialog.assert_not_called()
            text.deleteLater()

    def test_export_menu_actions_are_only_formats(self):
        for language in ("pl", "en"):
            self.window.settings.language = language
            self.window._translate_ui()
            self.assertEqual([self.window.export_pdf_action.text(), self.window.export_png_action.text(), self.window.export_svg_action.text()], ["PDF", "PNG", "SVG"])
