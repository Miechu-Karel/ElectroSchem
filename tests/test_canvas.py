"""Testy Qt offscreen faktycznych symboli, połączeń i zdarzeń myszy."""
import gc
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.canvas.component_item import ComponentItem
from app.canvas.schematic_view import SchematicView
from app.core.models import ComponentInstance, Project, Sheet, Wire
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS

APP = QApplication.instance() or QApplication([])
RESISTOR = next(item for item in BUILT_IN_ITEMS if item.name == "Rezystor")


class CanvasTests(unittest.TestCase):
    def setUp(self):
        self.project = Project()
        self.sheet = self.project.sheets[0]
        self.component = self.project.new_component(RESISTOR.id, 300, 300)
        self.sheet.components.append(self.component)
        self.view = SchematicView(project=self.project, settings=AppSettings(), sheet=self.sheet)
        self.view.resize(1100, 820)
        self.view.show()
        APP.processEvents()

    def tearDown(self):
        self.view.close()
        self.view.deleteLater()
        APP.processEvents()

    def test_click_does_not_remove_component_and_rotation_tracks_wire(self):
        item = self.view._component_items[self.component.id]
        point = self.view.mapFromScene(item.pos())
        for _ in range(5):
            QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton, pos=point)
            gc.collect()
            APP.processEvents()
        self.assertEqual(len(self.sheet.components), 1)
        self.assertIs(item.scene(), self.view.scene)
        self.assertTrue(item.isVisible())
        pin = item.pin_positions()[0]
        wire = Wire(pin.x(),pin.y(),100,100,start_component_id=self.component.id,start_pin_index=0)
        self.sheet.wires.append(wire)
        self.view._add_wire_item(wire)
        item.setSelected(True)
        self.view.rotate_selected_components()
        self.assertEqual(self.component.rotation,90)
        self.assertEqual(QPointF(wire.start_x,wire.start_y),item.pin_positions()[0])
        self.assertEqual(wire.start_pin_number,"1")

    def test_drag_commits_once_and_attaches_existing_free_end(self):
        changed = []
        self.view.on_change = lambda: changed.append(True)
        item = self.view._component_items[self.component.id]
        wire = Wire(400,300,500,300)
        self.sheet.wires.append(wire)
        self.view._add_wire_item(wire)
        # Prawy pin rezystora po przesunięciu środka na x=360 trafi w x=400.
        origin = self.view.mapFromScene(item.pos())
        target = self.view.mapFromScene(QPointF(360,300))
        QTest.mousePress(self.view.viewport(),Qt.MouseButton.LeftButton,pos=origin)
        QTest.mouseMove(self.view.viewport(),target,30)
        QTest.mouseRelease(self.view.viewport(),Qt.MouseButton.LeftButton,pos=target)
        APP.processEvents()
        self.assertEqual((self.component.x,self.component.y),(360,300))
        self.assertEqual(wire.start_component_id,self.component.id)
        self.assertEqual(wire.start_pin_index,1)
        self.assertEqual(self.view._wire_items[wire.id].endpoint_dots, (False, True))
        self.assertEqual(len(changed),1)

    def test_open_end_gets_node_again_when_its_neighboring_wire_is_deleted(self):
        first = Wire(100, 300, 200, 300, points=[[100, 300], [200, 300]])
        second = Wire(200, 300, 300, 300, points=[[200, 300], [300, 300]])
        self.sheet.wires.extend((first, second))
        self.view._add_wire_item(first)
        self.view._add_wire_item(second)
        self.view._join_coincident_ends()
        self.assertEqual(self.view._wire_items[first.id].endpoint_dots, (True, False))
        self.assertEqual(self.view._wire_items[second.id].endpoint_dots, (False, True))

        self.view._delete_item(self.view._wire_items[second.id])

        self.assertEqual(self.view._wire_items[first.id].endpoint_dots, (True, True))

    def test_end_with_missing_pin_anchor_is_shown_as_floating(self):
        wire = Wire(100, 300, 200, 300,
                    start_component_id=self.component.id, start_pin_index=99)
        wire.points = [[100, 300], [200, 300]]
        self.sheet.wires.append(wire)
        self.view._add_wire_item(wire)

        self.view._join_coincident_ends()

        self.assertEqual(self.view._wire_items[wire.id].endpoint_dots, (True, True))

    def test_shared_junction_id_hides_dots_even_if_legacy_coordinates_drift(self):
        first = Wire(100, 300, 200, 300, points=[[100, 300], [200, 300]])
        second = Wire(200.1, 300, 300, 300, points=[[200.1, 300], [300, 300]])
        first.end_junction_id = second.start_junction_id = "legacy-shared-node"
        self.view.load_sheet(Sheet(wires=[first, second]))

        self.assertEqual(self.view._wire_items[first.id].endpoint_dots, (True, False))
        self.assertEqual(self.view._wire_items[second.id].endpoint_dots, (False, True))

    def test_removing_component_turns_its_wire_pin_end_into_a_floating_node(self):
        pin = self.view._component_items[self.component.id].pin_positions()[0]
        wire = Wire(pin.x(), pin.y(), 200, 200,
                    start_component_id=self.component.id, start_pin_index=0)
        self.sheet.wires.append(wire)
        self.view._add_wire_item(wire)
        self.view._join_coincident_ends()
        self.assertFalse(self.view._wire_items[wire.id].endpoint_dots[0])

        self.view._delete_item(self.view._component_items[self.component.id])

        self.assertIsNone(wire.start_component_id)
        self.assertTrue(self.view._wire_items[wire.id].endpoint_dots[0])
        self.assertTrue(self.view._wire_items[wire.id].endpoint_dots[1])

    def test_dragging_pin_attached_end_to_empty_space_shows_floating_node(self):
        pin = self.view._component_items[self.component.id].pin_positions()[0]
        wire = Wire(pin.x(), pin.y(), 200, 200,
                    start_component_id=self.component.id, start_pin_index=0)
        wire.points = [[pin.x(), pin.y()], [200, 200]]
        self.sheet.wires.append(wire)
        self.view._add_wire_item(wire)
        self.view._join_coincident_ends()
        self.assertFalse(self.view._wire_items[wire.id].endpoint_dots[0])
        start = self.view.mapFromScene(pin)
        target = self.view.mapFromScene(QPointF(160, 160))

        QTest.mousePress(self.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(self.view.viewport(), target, 30)
        QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton, pos=target)
        APP.processEvents()

        self.assertIsNone(wire.start_component_id)
        self.assertTrue(self.view._wire_items[wire.id].endpoint_dots[0])

    def test_right_click_cancels_wire_and_does_not_delete(self):
        self.view.set_tool("wire")
        point = self.view.mapFromScene(QPointF(200,200))
        QTest.mouseClick(self.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertIsNotNone(self.view._wire_preview)
        QTest.mouseClick(self.view.viewport(),Qt.MouseButton.RightButton,pos=point)
        self.assertIsNone(self.view._wire_preview)
        self.assertFalse(self.sheet.wires)
        self.assertEqual(len(self.sheet.components),1)

    def test_midsegment_branch_creates_shared_node_preserving_far_pin(self):
        wire = Wire(100,300,260,300,end_component_id=self.component.id,end_pin_index=0)
        self.sheet.wires.append(wire)
        self.view._add_wire_item(wire)
        self.view._refresh_attached_wires()
        self.view._split_wires_at_point(QPointF(180,300))
        self.view._join_coincident_ends()
        self.view._refresh_attached_wires()
        self.assertEqual(len(self.sheet.wires),2)
        tail = self.sheet.wires[1]
        self.assertEqual(wire.end_junction_id,tail.start_junction_id)
        self.assertIsNotNone(wire.end_junction_id)
        self.assertEqual(tail.end_component_id,self.component.id)
        self.assertEqual(tail.end_pin_index,0)

    def test_loading_preserves_unattached_wire_waypoints(self):
        points = [[100,100],[100,200],[200,200],[200,100]]
        wire = Wire(100,100,200,100,points=points)
        self.sheet.wires.append(wire)
        self.view.load_sheet(self.sheet)
        self.assertEqual(wire.points,points)

    def test_every_builtin_renders_and_all_pin_hit_boxes_fit_grid(self):
        for definition in BUILT_IN_ITEMS:
            with self.subTest(component=definition.name):
                item = ComponentItem(ComponentInstance(definition.id,0,0))
                rect = item.shape().boundingRect()
                for edge in (rect.left(),rect.right(),rect.top(),rect.bottom()):
                    self.assertAlmostEqual(edge % 20,0)
                for point in item.pin_positions():
                    self.assertTrue(rect.contains(point), f"Pin outside {definition.name}")
                image = QImage(600,600,QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.white)
                painter = QPainter(image)
                painter.translate(300,300)
                scale=min(500/max(rect.width(),rect.height()),1)
                painter.scale(scale,scale)
                item.paint(painter,None)
                painter.end()
                self.assertFalse(image.isNull())


if __name__ == "__main__":
    unittest.main()
