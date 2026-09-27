"""Regresje rc3: rzeczywiste zdarzenia Qt, granice rysowania i zapis ELS."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QMessageBox

from app.canvas.component_item import ComponentItem
from app.canvas.page import frame_rect, title_block_rect, drawing_rect
from app.core.models import ComponentInstance, Sheet
from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog

APP = QApplication.instance() or QApplication([])
font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"
if font_path.is_file():
    QFontDatabase.addApplicationFont(str(font_path))
BY_NAME = {item.name: item for item in BUILT_IN_ITEMS}


class Rc3Tests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(setup_complete=True), start_setup=False)
        self.window.resize(1200, 850)
        self.window.show()
        self.window.activateWindow()
        self.view = self.window._current_view()
        self.view.setFocus()
        APP.processEvents()

    def tearDown(self):
        self.view = self.window._current_view()
        self.view.finish_text_editing()
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def add(self, name, x=300, y=300):
        definition = BY_NAME[name]
        component = self.window.project.new_component(definition.id, x, y)
        self.view._sheet.components.append(component)
        self.view._add_component_item(component)
        self.window.record_history()
        return component

    def test_labels_stay_inside_and_read_the_same_at_opposite_rotations(self):
        definition = BY_NAME["Rezystor"]
        component = ComponentInstance(definition.id, 0, 0, display_name="Very long resistor name with all words retained", value="300", unit="Ω")
        item = ComponentItem(component)
        rect = item._hit_rect
        self.assertEqual(rect, QRectF(-40, -20, 80, 60))  # Krótka wartość mieści się przy rezystorze.
        text = component.display_name
        _, lines = item._fit_wrapped_text(text, rect.width(), 14, max_lines=3)
        self.assertGreaterEqual(len(lines), 2)
        self.assertLessEqual(len(lines), 3)
        self.assertEqual("".join("".join(lines).split()), "".join(text.split()))
        for name in (text, "XYZ"*600, "First\nSecond\nThird"):
            path = item._label_path(name, rect)
            self.assertTrue(rect.adjusted(-.001, -.001, .001, .001).contains(path.boundingRect()))
        images = []
        item.show_value = False  # Porównujemy orientację samej nazwy.
        for angle in (0, 90, 180, 270):
            item.setRotation(angle)
            image = QImage(300, 300, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            painter.translate(150, 150)
            painter.rotate(angle)
            # rc6 obraca tekst w osobnym pasie poza symbolem. Porównujemy
            # orientację glifów, niezależnie od położenia pasa po obrocie.
            painter.translate(-item.label_rects()[0].center())
            item._bottom_labels(painter)
            painter.end()
            images.append(image)
        self.assertEqual(images[0], images[2])
        self.assertEqual(images[1], images[3])

    def test_margins_all_formats_grid_and_full_size_mcu(self):
        for size in ("A0", "A1", "A2", "A3", "A4", "A5"):
            for orientation in ("portrait", "landscape"):
                frame = frame_rect(Sheet(paper_size=size, orientation=orientation))
                for edge in (frame.left(), frame.top(), frame.right(), frame.bottom()):
                    self.assertEqual(edge % 20, 0)
        definition = BY_NAME["Arduino Uno R3"]
        item = ComponentItem(ComponentInstance(definition.id, 0, 0))
        self.assertEqual(item.scale(), 1)
        self.assertEqual(item._hit_rect.width(), definition.width)
        self.assertEqual(item._hit_rect.height(), definition.height)

    def test_right_rectangle_left_single_and_middle_pan(self):
        first = self.add("Rezystor")
        second = self.add("Rezystor", 460, 300)
        start = self.view.mapFromScene(QPointF(240, 260))
        end = self.view.mapFromScene(QPointF(520, 340))
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.RightButton, pos=start)
        QTest.mouseMove(self.view.viewport(), end)
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.RightButton, pos=end)
        self.assertEqual(len(self.view.scene.selectedItems()), 2)
        QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.view.mapFromScene(QPointF(first.x, first.y)))
        self.assertEqual([i.data(1) for i in self.view.scene.selectedItems()], [first.id])
        self.view.scale(2, 2)
        self.view.centerOn(600, 400)
        before = self.view.horizontalScrollBar().value()
        origin = self.view.viewport().rect().center()
        QTest.mousePress(self.view.viewport(), Qt.MouseButton.MiddleButton, pos=origin)
        QTest.mouseMove(self.view.viewport(), origin+QPoint(60, 20))
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.MiddleButton, pos=origin+QPoint(60, 20))
        self.assertNotEqual(before, self.view.horizontalScrollBar().value())
        self.assertEqual((second.x, second.y), (460, 300))

    def test_inline_title_typing_save_and_undo(self):
        block = title_block_rect(self.view._sheet)
        point = self.view.mapFromScene(QPointF(block.left()+60, block.top()+20))
        QTest.mouseDClick(self.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.assertIsNotNone(self.view._title_editor)
        QTest.keyClicks(self.view.viewport(), "Resistor SD")
        QTest.keyClick(self.view.viewport(), Qt.Key.Key_Return)
        self.assertEqual(self.window.project.name, "Resistor SD")
        self.assertEqual(self.view.tool, "select")
        for field, text in (("sheet", "Power stage"), ("author", "Test Author")):
            self.view._begin_title_edit(field)
            QTest.keyClicks(self.view.viewport(), text)
            QTest.keyClick(self.view.viewport(), Qt.Key.Key_Return)
        self.assertEqual(self.window.tabs.tabText(0), "Power stage")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rc3.els"
            self.assertTrue(self.window._write_project(path))
            restored = load_project(path)
        self.assertEqual(restored.metadata["author"], "Test Author")
        self.assertEqual(restored.name, "Resistor SD")
        self.assertEqual(restored.sheets[0].name, "Power stage")
        self.window.undo()
        self.assertNotIn("author", self.window.project.metadata)

    def test_delete_sheet_from_name_dialog_and_restore_contents(self):
        self.add("Rezystor")
        self.window.add_sheet()
        def click_delete():
            dialog = APP.activeModalWidget()
            button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Delete sheet")
            button.click()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            QTimer.singleShot(0, click_delete)
            self.window.rename_sheet(0)
        self.assertEqual(self.window.tabs.count(), 1)
        self.assertFalse(self.window.project.sheets[0].components)
        self.window.undo()
        self.assertEqual(len(self.window.project.sheets[0].components), 1)
        self.assertEqual(self.window.tabs.count(), 2)

    def test_values_are_specific_to_component_and_extra_values_roundtrip(self):
        for name, expected_primary, extra in (("Rezystor", True, ""),
                ("Kondensator Elektrolityczny", True, "voltage"),
                ("Dioda LED 5mm", False, "color"), ("Arduino Uno R3", False, "")):
            definition = BY_NAME[name]
            component = self.window.project.new_component(definition.id, 300, 300)
            dialog = ComponentPropertiesDialog(component, definition)
            self.assertEqual(dialog._has_primary_value, expected_primary)
            self.assertEqual(dialog._extra_key, extra)
            if not expected_primary:
                self.assertFalse(any(label.text() in ("Value:", "Unit:") for label in dialog.findChildren(QLabel)))
            if extra:
                if extra == "voltage":
                    dialog.extra_value.setText("25")
                else:
                    dialog.extra_value.setCurrentIndex(dialog.extra_value.findData("red"))
                dialog.accept()
                self.assertEqual(dialog.values["extra_value"], "25 V" if extra == "voltage" else "red")
            dialog.deleteLater()

    def test_rotation_clamps_asymmetric_symbol_and_keeps_grid(self):
        component = self.add("Potencjometr Obrotowy", 120, 80)
        item = self.view._component_items[component.id]
        item.setSelected(True)
        for _ in range(4):
            self.view.rotate_selected_components()
            self.assertTrue(drawing_rect(self.view._sheet).contains(item.mapRectToScene(item._hit_rect)))
            self.assertEqual(component.x % 20, 0)
            self.assertEqual(component.y % 20, 0)

    def test_seven_standalone_gates(self):
        for kind in ("AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR"):
            definition = BY_NAME["Bramka " + kind]
            self.assertEqual(definition.symbol, "gate_"+kind.lower())
            self.assertEqual(len(definition.pins), 2 if kind == "NOT" else 3)


if __name__ == "__main__":
    unittest.main()
