import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import time

from PySide6.QtCore import QPointF, Qt, QElapsedTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from unittest.mock import patch

from app.canvas.schematic_view import SchematicView
from app.core.models import Project, Sheet, Wire
from app.libraries.built_in import BUILT_IN_ITEMS
from app.core.settings import AppSettings
from app.ui.main_window import APP_VERSION
from app.ui.theme import canvas_colors


APP = QApplication.instance() or QApplication([])


class Alpha131a1Tests(unittest.TestCase):
    def tearDown(self):
        view = getattr(self, "view", None)
        if view:
            view.close()
            view.deleteLater()
            APP.processEvents()

    def test_version_and_darker_dark_canvas(self):
        self.assertEqual(APP_VERSION, "1.3.1")
        colours = canvas_colors(AppSettings(theme="dark"))
        self.assertEqual(colours["paper"], "#b9b9b9")
        self.assertEqual(colours["faint_paper"], "#b6b6b6")
        self.assertEqual(colours["table"], "#b9b9b9")

    def test_large_selection_does_not_start_sync_route_search(self):
        resistor = next(definition for definition in BUILT_IN_ITEMS if definition.name == "Rezystor")
        project = Project(sheets=[Sheet()])
        components = [project.new_component(resistor.id, 100 + (index % 10) * 100,
                                            100 + (index // 10) * 100)
                      for index in range(40)]
        project.sheets[0].components = components
        self.view = SchematicView(project=project, settings=AppSettings(), sheet=project.sheets[0])
        self.view.resize(1000, 750)
        self.view.show()
        APP.processEvents()
        for component in components:
            self.view._component_items[component.id].setSelected(True)
        origin = QPointF(100, 100)
        self.view._begin_selection_group(origin)

        with patch.object(self.view, "_routes_after_movement",
                          side_effect=AssertionError("blocking route ran during drag")):
            self.assertTrue(self.view._move_selection_group(QPointF(20, 20)))
            self.assertTrue(self.view._group_drag["defer_routing"])
            QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton,
                               pos=self.view.mapFromScene(origin))

        self.assertFalse(self.view._route_task_running)
        self.assertEqual(len(components), 40)
        self.assertTrue(all(component.x == 120 + (index % 10) * 100 and
                            component.y == 120 + (index // 10) * 100
                            for index, component in enumerate(components)))

    def test_deferred_routes_finish_after_release(self):
        wires = [
            Wire(100, 100, 200, 100, points=[[100, 100], [100, 140], [200, 140], [200, 100]]),
            Wire(100, 200, 200, 200, points=[[100, 200], [100, 240], [200, 240], [200, 200]]),
            Wire(300, 100, 400, 100, points=[[300, 100], [300, 140], [400, 140], [400, 100]]),
            Wire(300, 200, 400, 200, points=[[300, 200], [300, 240], [400, 240], [400, 200]]),
        ]
        self.view = SchematicView(settings=AppSettings(), sheet=Sheet(wires=wires))
        self.view.resize(1000, 750)
        self.view.show()
        APP.processEvents()
        for wire in wires:
            self.view._wire_items[wire.id].setSelected(True)
        origin = QPointF(100, 100)
        self.view._begin_selection_group(origin)

        with patch.object(self.view, "_routes_after_movement",
                          side_effect=AssertionError("blocking route ran during drag")):
            self.assertTrue(self.view._move_selection_group(QPointF(20, 20)))
            self.assertTrue(self.view._group_drag["defer_routing"])
            QTest.mouseRelease(self.view.viewport(), Qt.MouseButton.LeftButton,
                               pos=self.view.mapFromScene(origin))

        timer = QElapsedTimer()
        timer.start()
        while self.view._route_task_running or self.view._route_pending_ids:
            APP.processEvents()
            QTest.qWait(5)
            self.assertLess(timer.elapsed(), 5000, "background route task did not finish")

        self.assertIsNone(self.view._last_route_error)
        for wire in wires:
            self.assertEqual(len(wire.points), 2)
            self.assertEqual(wire.points[0], [wire.start_x, wire.start_y])
            self.assertEqual(wire.points[-1], [wire.end_x, wire.end_y])

    def test_closing_canvas_while_worker_runs_keeps_task_alive_safely(self):
        from app.canvas import schematic_view

        wire = Wire(100, 100, 200, 100)
        self.view = SchematicView(settings=AppSettings(), sheet=Sheet(wires=[wire]))

        def slow_route(_sheet, _wire_ids):
            time.sleep(.05)
            return {}

        with patch.object(schematic_view, "_compute_wire_routes", side_effect=slow_route):
            self.view._schedule_wire_routes({wire.id})
            self.view.close()
            self.view.deleteLater()
            self.view = None
            timer = QElapsedTimer()
            timer.start()
            while schematic_view._ACTIVE_WIRE_ROUTE_TASKS and timer.elapsed() < 2000:
                QTest.qWait(10)
            APP.processEvents()

        self.assertFalse(schematic_view._ACTIVE_WIRE_ROUTE_TASKS)

