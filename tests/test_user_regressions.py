"""Focused regressions for wire route choice and document history shortcuts."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copy import deepcopy
from math import hypot
import unittest

from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.canvas.routing import safe_route, editor_route, overlap_allowed
from app.core.models import Wire
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
RESISTOR = next(item for item in BUILT_IN_ITEMS if item.name == "Rezystor")


class WireRoutingRegressionTests(unittest.TestCase):
    def test_application_version(self):
        from app.ui.main_window import APP_VERSION

        self.assertEqual(APP_VERSION, "1.4.0")

    def test_overlapping_wire_uses_nearest_shortest_legal_detour(self):
        from app.core.models import Sheet

        sheet = Sheet(wires=[Wire(100, 100, 300, 100, points=[[100, 100], [300, 100]])])
        start, end = QPointF(100, 100), QPointF(350, 100)
        route = safe_route(sheet, start, end)

        self.assertIsNotNone(route)
        self.assertTrue(overlap_allowed(sheet, route))
        length = sum(hypot(b.x() - a.x(), b.y() - a.y()) for a, b in zip(route, route[1:]))
        self.assertAlmostEqual(length, 250 + 2 * hypot(10, 10) - 20, places=5)
        self.assertLess(max(abs(point.y() - start.y()) for point in route), 40)

    def test_cursor_progress_keeps_detour_local_instead_of_jumping_away(self):
        from app.core.models import Sheet

        sheet = Sheet(wires=[Wire(100, 100, 300, 100, points=[[100, 100], [300, 100]])])
        for end_x in (320, 340, 360, 400, 500):
            with self.subTest(end_x=end_x):
                route = safe_route(sheet, QPointF(100, 100), QPointF(end_x, 100))
                self.assertTrue(overlap_allowed(sheet, route))
                length = sum(hypot(b.x() - a.x(), b.y() - a.y()) for a, b in zip(route, route[1:]))
                detour_overhead = 2 * hypot(10, 10) - 20
                self.assertAlmostEqual(length, end_x - 100 + detour_overhead, places=5)
                self.assertLessEqual(max(abs(point.y() - 100) for point in route), 20)

    def test_editor_route_uses_half_cell_clearance_without_extra_bends(self):
        from app.core.models import Sheet

        sheet = Sheet(wires=[Wire(100, 100, 300, 100, points=[[100, 100], [300, 100]])])
        route = editor_route(sheet, QPointF(285, 100), QPointF(315, 100))
        self.assertTrue(overlap_allowed(sheet, route))
        length = sum(hypot(b.x() - a.x(), b.y() - a.y()) for a, b in zip(route, route[1:]))
        self.assertAlmostEqual(length, 30 + 2 * hypot(10, 10) - 20, places=5)
        self.assertLessEqual(len(route), 4)

    def test_editor_route_keeps_the_start_anchored_bend_as_cursor_moves(self):
        from app.core.models import Sheet

        sheet = Sheet()
        start = QPointF(200, 200)
        routes = [editor_route(sheet, start, QPointF(x, 220)) for x in (240, 260, 280, 300)]
        self.assertTrue(all(route[:2] == [start, QPointF(220, 220)] for route in routes))

    def test_subdivided_wire_cannot_bypass_half_cell_overlap_limit(self):
        from app.core.models import Sheet

        old = Wire(100, 100, 120, 100, points=[[100, 100], [110, 100], [120, 100]])
        sheet = Sheet(wires=[old])
        new = [QPointF(100, 100), QPointF(110, 100), QPointF(120, 100)]
        self.assertFalse(overlap_allowed(sheet, new))


class DocumentUndoRedoRegressionTests(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow(AppSettings(), start_setup=False)
        self.window.show()
        self.window.activateWindow()
        APP.processEvents()

    def tearDown(self):
        self.window._sync_positions()
        self.window._saved_state = self.window.project.to_dict()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def shortcut(self, key):
        view = self.window._current_view()
        view.setFocus()
        APP.processEvents()
        QTest.keyClick(view.viewport(), key, Qt.KeyboardModifier.ControlModifier)
        APP.processEvents()

    def test_repeated_ctrl_z_y_keeps_sheet_and_schematic_contents(self):
        window = self.window
        original_name = window.project.name
        initial = deepcopy(window.project.to_dict())

        component = window.add_component_from_id(RESISTOR.id)
        window._current_view().setFocus()
        sheet = window.project.sheets[0]
        wire = Wire(200, 200, 300, 300, points=[[200, 200], [300, 300]])
        sheet.wires.append(wire)
        window._current_view()._add_wire_item(wire)
        window.record_history()
        window.add_sheet()
        window.project.name = "History checkpoint"
        window.record_history()

        self.assertEqual(len(window._history), 5)
        self.assertEqual(len(window.project.sheets), 2)
        self.assertEqual(len(window.project.sheets[0].components), 1)
        self.assertEqual(len(window.project.sheets[0].wires), 1)

        # Use real keyboard shortcuts, with a fresh active canvas after each
        # restore (undo/redo deliberately rebuilds the tab widgets).
        expected = (
            (2, 1, 1, original_name),
            (1, 1, 1, original_name),
            (1, 1, 0, original_name),
            (1, 0, 0, original_name),
        )
        for sheet_count, component_count, wire_count, name in expected:
            self.shortcut(Qt.Key.Key_Z)
            self.assertEqual(window.project.name, name)
            self.assertEqual(len(window.project.sheets), sheet_count)
            self.assertEqual(len(window.project.sheets[0].components), component_count)
            self.assertEqual(len(window.project.sheets[0].wires), wire_count)
        self.assertEqual(window.project.to_dict(), initial)

        expected_redo = (
            (1, 1, 0, original_name),
            (1, 1, 1, original_name),
            (2, 1, 1, original_name),
            (2, 1, 1, "History checkpoint"),
        )
        for sheet_count, component_count, wire_count, name in expected_redo:
            self.shortcut(Qt.Key.Key_Y)
            self.assertEqual(window.project.name, name)
            self.assertEqual(len(window.project.sheets), sheet_count)
            self.assertEqual(len(window.project.sheets[0].components), component_count)
            self.assertEqual(len(window.project.sheets[0].wires), wire_count)

        self.assertEqual(window.project.sheets[0].components[0].id, component.id)
        self.assertTrue(window.undo_action.isEnabled())
        self.assertFalse(window.redo_action.isEnabled())

    def test_canvas_wire_draw_uses_router_and_is_undoable(self):
        window = self.window
        view = window._current_view()
        old = Wire(100, 100, 300, 100, points=[[100, 100], [300, 100]])
        window.project.sheets[0].wires.append(old)
        view._add_wire_item(old)
        window._reset_history()
        baseline = deepcopy(window.project.to_dict())
        view.set_tool("wire")

        for scene_point in (QPointF(280, 100), QPointF(320, 100)):
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                             pos=view.mapFromScene(scene_point))
            APP.processEvents()

        new_wire = next(wire for wire in window.project.sheets[0].wires
                        if any(round(point[0]) == 290 and round(point[1]) == 110 for point in wire.points))
        straight_tail = next(wire for wire in window.project.sheets[0].wires
                             if {round(wire.start_x), round(wire.end_x)} == {300, 320})
        route = [QPointF(*point) for point in new_wire.points]
        route += [QPointF(*point) for point in straight_tail.points[1:]]
        self.assertTrue(overlap_allowed(window.project.sheets[0], route,
                                        exclude=(new_wire.id, straight_tail.id)))
        length = sum(hypot(b.x() - a.x(), b.y() - a.y()) for a, b in zip(route, route[1:]))
        self.assertAlmostEqual(length, 40 + 2 * hypot(10, 10) - 20, places=5)
        drawn_state = deepcopy(window.project.to_dict())
        drawn_wire_count = len(window.project.sheets[0].wires)

        for _ in range(3):
            self.shortcut(Qt.Key.Key_Z)
            self.assertEqual(window.project.to_dict(), baseline)
            self.shortcut(Qt.Key.Key_Y)
            self.assertEqual(len(window.project.sheets[0].wires), drawn_wire_count)
            self.assertEqual(window.project.to_dict(), drawn_state)
        restored = next(wire for wire in window.project.sheets[0].wires
                        if any(round(point[0]) == 290 and round(point[1]) == 110 for point in wire.points))
        self.assertEqual(restored.points, new_wire.points)

    def test_wire_drawing_cancels_after_each_completed_segment(self):
        view = self.window._current_view()
        view.set_tool("wire")
        for point in (QPointF(200, 200), QPointF(300, 200)):
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=view.mapFromScene(point))
            APP.processEvents()
        self.assertEqual(len(self.window.project.sheets[0].wires), 1)
        self.assertIsNone(view._wire_start)
        self.assertIsNone(view._wire_preview)

        # The next line is independent: its first click establishes a fresh start.
        for point in (QPointF(400, 200), QPointF(500, 200)):
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=view.mapFromScene(point))
            APP.processEvents()
        self.assertEqual(len(self.window.project.sheets[0].wires), 2)
        first, second = self.window.project.sheets[0].wires
        self.assertEqual((first.start_x, first.start_y, first.end_x, first.end_y),
                         (200, 200, 300, 200))
        self.assertEqual((second.start_x, second.start_y, second.end_x, second.end_y),
                         (400, 200, 500, 200))
        self.assertIsNone(view._wire_start)
        self.assertIsNone(view._wire_preview)

    def test_drag_wire_release_reanchors_at_the_released_endpoint(self):
        view = self.window._current_view()
        view.set_tool("wire")
        start, end = QPointF(200, 200), QPointF(300, 260)
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=view.mapFromScene(start))
        QTest.mouseMove(view.viewport(), view.mapFromScene(end), delay=10)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                           pos=view.mapFromScene(end))
        APP.processEvents()

        self.assertEqual(len(self.window.project.sheets[0].wires), 1)
        self.assertIsNone(view._wire_start)
        self.assertIsNone(view._wire_preview)
        self.assertEqual((self.window.project.sheets[0].wires[0].start_x,
                          self.window.project.sheets[0].wires[0].start_y,
                          self.window.project.sheets[0].wires[0].end_x,
                          self.window.project.sheets[0].wires[0].end_y),
                         (200, 200, 300, 260))

    def test_malformed_single_vertex_wire_does_not_abort_commit_or_keep_anchor(self):
        from app.core.models import Sheet

        view = self.window._current_view()
        malformed = Wire(100, 100, 100, 100, points=[[100, 100]])
        sheet = Sheet(wires=[malformed])
        view.load_sheet(sheet)
        view.set_tool("wire")
        view._start_wire_preview((QPointF(200, 200), None, None))

        self.assertTrue(view._complete_wire_at((QPointF(300, 200), None, None)))
        self.assertIsNone(view._wire_start)
        self.assertIsNone(view._wire_preview)
        self.assertEqual(len(sheet.wires), 2)

    @staticmethod
    def _route_length(wire):
        return sum(hypot(b[0] - a[0], b[1] - a[1])
                   for a, b in zip(wire.points, wire.points[1:]))

    def _add_detoured_wire(self, start=(200, 200), end=(400, 200)):
        view = self.window._current_view()
        wire = Wire(*start, *end, points=[list(start), [start[0], start[1] + 100],
                                          [end[0], end[1] + 100], list(end)])
        self.window.project.sheets[0].wires.append(wire)
        view._add_wire_item(wire)
        return view, wire

    def test_dragging_wire_endpoint_recalculates_shortest_route(self):
        view, wire = self._add_detoured_wire()
        old_length = self._route_length(wire)

        view._move_wire_endpoint(wire.id, True, QPointF(220, 200), None, None)

        self.assertEqual((wire.points[0], wire.points[-1]), ([220, 200], [400, 200]))
        self.assertLess(self._route_length(wire), old_length)
        self.assertEqual(wire.points, [[220.0, 200.0], [400.0, 200.0]])

    def test_moving_selected_wire_recalculates_even_when_entire_path_translates(self):
        view, wire = self._add_detoured_wire()
        old_length = self._route_length(wire)
        item = view._wire_items[wire.id]
        item.setSelected(True)

        view._begin_selection_group(QPointF(200, 200))
        self.assertTrue(view._move_selection_group(QPointF(20, 0)))

        self.assertEqual((wire.points[0], wire.points[-1]), ([220.0, 200.0], [420.0, 200.0]))
        self.assertLess(self._route_length(wire), old_length)
        self.assertEqual(wire.points, [[220.0, 200.0], [420.0, 200.0]])

    def test_moving_shared_junction_does_not_accumulate_tiny_route_elbows(self):
        from app.core.models import Sheet

        def moved_paths(waypoints):
            wires = [
                Wire(200, 100, 200, 200, id="vertical", points=[[200, 100], [200, 200]]),
                Wire(200, 200, 400, 200, id="right", points=[[200, 200], [400, 200]]),
                Wire(200, 200, 200, 400, id="down", points=[[200, 200], [200, 400]]),
            ]
            view = self.window._current_view()
            view.load_sheet(Sheet(wires=wires))
            view._wire_gesture_points = {wire.id: deepcopy(wire.points) for wire in wires}
            for x, y in waypoints:
                view._move_wire_endpoint("vertical", False, QPointF(x, y), None, None)
            return {wire.id: deepcopy(wire.points) for wire in view._sheet.wires}

        incremental = moved_paths(((220, 220), (240, 240)))
        direct = moved_paths(((240, 240),))
        self.assertEqual(incremental, direct)

    def test_moving_connected_component_recalculates_attached_wire_route(self):
        view = self.window._current_view()
        component = self.window.project.new_component(RESISTOR.id, 200, 300)
        self.window.project.sheets[0].components.append(component)
        view._add_component_item(component)
        component_item = view._component_items[component.id]
        pin = component_item.pin_positions()[0]
        end = QPointF(pin.x() + 200, pin.y())
        wire = Wire(pin.x(), pin.y(), end.x(), end.y(), start_component_id=component.id,
                    start_pin_index=0, points=[[pin.x(), pin.y()], [pin.x(), pin.y() + 100],
                                               [end.x(), end.y() + 100], [end.x(), end.y()]])
        self.window.project.sheets[0].wires.append(wire)
        view._add_wire_item(wire)
        old_length = self._route_length(wire)

        component_item.setPos(component_item.pos() + QPointF(20, 0))

        self.assertEqual(wire.points[0], [component_item.pin_positions()[0].x(),
                                          component_item.pin_positions()[0].y()])
        self.assertLess(self._route_length(wire), old_length)


if __name__ == "__main__":
    unittest.main()
