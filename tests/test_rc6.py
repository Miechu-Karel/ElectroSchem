"""Regresje rc6: SI, opisy bez kolizji, geometria bramek i edycja w miejscu."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication
from app.core.models import Project, ComponentInstance, Wire
from app.core.units import parse_value
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.libraries.menu_groups import subgroup
from app.canvas.component_item import ComponentItem
from app.canvas.page import title_field_layout, title_document, draw_page
from app.canvas.schematic_view import SchematicView
from app.ui.properties_dialog import ComponentPropertiesDialog

APP = QApplication.instance() or QApplication([])
BY_NAME = {item.name: item for item in BUILT_IN_ITEMS}


class Rc6Tests(unittest.TestCase):
    def test_engineering_units_and_idempotence(self):
        cases = [("10000", "Ω", ("10", "kΩ")), ("1000000", "Ω", ("1", "MΩ")),
                 ("0.000000047", "F", ("47", "nF")), ("1000", "mV", ("1", "V")),
                 ("0.1", "µF", ("100", "nF")), ("-0.003", "A", ("-3", "mA")),
                 ("0", "kΩ", ("0", "Ω")), ("1e-12", "H", ("1", "pH")),
                 ("1e15", "Hz", ("1", "PHz")), ("1e-15", "F", ("1", "fF")),
                 ("1,5e3", "V", ("1.5", "kV")), ("4k7", "Ω", ("4.7", "kΩ"))]
        for value, unit, expected in cases:
            with self.subTest(value=value, unit=unit):
                self.assertEqual(parse_value(value, unit), expected)
                self.assertEqual(parse_value(*expected), expected)

    def test_xiao_and_esp32_are_one_group(self):
        for name in ("Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)", "ESP32 DevKitC", "ESP32-S3 NodeMCU"):
            self.assertEqual(subgroup(BY_NAME[name]), ("ESP32", "ESP32"))

    def test_pn2222_has_its_own_numbering_and_reference(self):
        definition = BY_NAME["Tranzystor NPN PN2222"]
        self.assertEqual({p.number: p.name for p in definition.pins}, {"1": "E", "2": "B", "3": "C"})
        self.assertEqual(Project().new_component(definition.id, 0, 0).reference, "oth_PN2222__001")

    def test_logic_gates_are_two_by_two_with_grid_pins(self):
        for definition in BUILT_IN_ITEMS:
            if not definition.symbol.startswith("gate_"):
                continue
            item = ComponentItem(ComponentInstance(definition.id, 0, 0))
            self.assertEqual((item._symbol_rect.width(), item._symbol_rect.height()), (40, 40))
            self.assertLessEqual(item._hit_rect.width(), 60)
            self.assertLessEqual(item._hit_rect.height(), 60)
            for pin in item.pin_positions():
                self.assertEqual(pin.x() % 20, 0)
                self.assertEqual(pin.y() % 20, 0)
                self.assertTrue(item._symbol_rect.contains(pin))

    def test_name_and_value_bands_do_not_intersect_symbol(self):
        for name in ("Przycisk Tact Switch", "Kondensator Ceramiczny", "Tranzystor NPN PN2222", "Dioda LED 5mm", "Bramka NAND"):
            item = ComponentItem(ComponentInstance(BY_NAME[name].id, 0, 0))
            for rect in item.label_rects():
                if rect.isEmpty():
                    continue
                self.assertFalse(rect.intersects(item._symbol_rect), name)
                self.assertTrue(item._hit_rect.contains(rect), name)
                for angle in (0, 90, 180, 270):
                    item.setRotation(angle)
                    self.assertFalse(item.mapRectToScene(rect).intersects(item.mapRectToScene(item._symbol_rect)))

    def test_capacitor_separate_voltage_fields_and_legacy_read(self):
        d = BY_NAME["Kondensator Ceramiczny"]
        c = ComponentInstance(d.id, 0, 0, value="0.0000003", unit="F", properties={"voltage": "25000 mV"})
        dialog = ComponentPropertiesDialog(c, d)
        self.assertEqual(dialog.extra_value.text(), "25")
        self.assertEqual(dialog.extra_unit.text(), "V")
        dialog.extra_value.setText("10000")
        dialog.accept()
        self.assertEqual(dialog.values["value"], "300")
        self.assertEqual(dialog.values["unit"], "nF")
        self.assertEqual(dialog.values["extra_value"], "10 kV")
        self.assertEqual(dialog.extra_value.text(), "10")
        self.assertEqual(dialog.extra_unit.text(), "kV")
        dialog.deleteLater()

    def test_value_separator_is_slash(self):
        c = ComponentInstance(BY_NAME["Kondensator Ceramiczny"].id, 0, 0, value="300", unit="nF",
                              properties={"voltage": "25 V", "show_voltage": True})
        item = ComponentItem(c)
        image = QImage(200, 200, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        with patch.object(item, "_draw_fitted_label") as draw:
            item._bottom_labels(painter)
            self.assertIn("300 nF / 25 V", [call.args[1] for call in draw.call_args_list])
        painter.end()

    def test_small_gate_preserves_wire_attachment_after_reload(self):
        project = Project()
        c = project.new_component(BY_NAME["Bramka AND"].id, 300, 300)
        project.sheets[0].components.append(c)
        wire = Wire(100, 280, 260, 280, end_component_id=c.id, end_pin_index=0, end_pin_number="1")
        project.sheets[0].wires.append(wire)
        view = SchematicView(project=project, settings=AppSettings(), sheet=project.sheets[0])
        self.assertEqual((wire.end_x, wire.end_y), (280, 280))
        self.assertEqual(wire.end_component_id, c.id)
        view.deleteLater()

    def test_title_editor_matches_static_text_geometry(self):
        project = Project(name="New circuit")
        project.metadata["author"] = "Test Author"
        sheet = project.sheets[0]
        view = SchematicView(project=project, settings=AppSettings(language="pl"), sheet=sheet)
        for field in ("project", "sheet", "author"):
            _, rect, _, font, value = title_field_layout(sheet, project, field, "pl")
            doc = title_document(value, font, rect.width())
            view._begin_title_edit(field)
            editor = view._title_editor
            self.assertEqual(editor.toPlainText(), value)
            self.assertEqual(editor.font(), font)
            self.assertEqual(editor.pos(), QPointF(rect.left(), rect.top()+max(0, (rect.height()-doc.size().height())/2)))
            image = QImage(1200, 850, QImage.Format.Format_ARGB32)
            painter = QPainter(image)
            with patch("app.canvas.page.title_document", wraps=title_document) as layout:
                draw_page(painter, sheet, project, view.settings, editing_field=field)
                self.assertEqual(layout.call_count, 2)  # brak drugiej kopii edytowanego tekstu
            painter.end()
            view.finish_text_editing()
        view.deleteLater()
