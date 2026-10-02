"""Expanded display previews must not pretend to decode firmware images."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication
from app.libraries.display_profiles import DISPLAY_PROFILES
from app.libraries.built_in import get_definition
from app.ui.display_preview import preview_rect
from app.ui.simulation_window import LiveSymbol
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])


def powered_display(name):
    bench=Bench(); supply,ground=bench.power()
    component=bench.add(name,sim_nominal_voltage="5 V",sim_load_current="10 mA")
    pins=[pin.name for pin in get_definition(component.library_id).pins]
    high=next(pin for pin in ("VCC","5V","VCC_IN") if pin in pins)
    low=next(pin for pin in ("GND","GND_IN") if pin in pins)
    bench.connect(supply,0,component,high); bench.connect(ground,0,component,low)
    return bench.circuit(),component


class DisplayPreviewTests(unittest.TestCase):
    def test_all_display_states_follow_actual_supply_without_inventing_pixels(self):
        for name,profile in DISPLAY_PROFILES.items():
            with self.subTest(name=name):
                circuit,component=powered_display(name)
                before=deepcopy(component)
                result=circuit.step()
                self.assertFalse(result.faults)
                state=result.displays[component.id]
                self.assertEqual((state["columns"],state["rows"]),(profile.columns,profile.rows))
                self.assertTrue(state["powered"])
                self.assertFalse(state["protocol_model"])
                self.assertNotIn("pixels",state)
                circuit.sources[0].parameters["value"]=0
                self.assertFalse(circuit.step().displays[component.id]["powered"])
                self.assertEqual(component,before)

    def test_preview_bounds_enclose_drawing_without_moving_any_pins(self):
        for name in DISPLAY_PROFILES:
            with self.subTest(name=name):
                circuit,component=powered_display(name)
                original=deepcopy(component)
                item=LiveSymbol(component,language="pl")
                panel=preview_rect(item)
                self.assertTrue(item.boundingRect().contains(panel.adjusted(-2,-2,2,2)))
                self.assertGreaterEqual(panel.width(),220)
                self.assertEqual(component,original)
                self.assertEqual(item.definition.pins,get_definition(component.library_id).pins)

    def test_all_previews_render_and_power_indicator_changes(self):
        for name in DISPLAY_PROFILES:
            with self.subTest(name=name):
                circuit,component=powered_display(name)
                item=LiveSymbol(component)
                def render(powered):
                    item.display_state={"powered":powered}
                    image=QImage(600,600,QImage.Format.Format_ARGB32)
                    image.fill(Qt.GlobalColor.black)
                    painter=QPainter(image); painter.translate(300,500)
                    item.paint(painter,None); painter.end()
                    return image
                off,on=render(False),render(True)
                self.assertNotEqual(off,on)
                panel=preview_rect(item)
                self.assertEqual(on.pixelColor(int(panel.left()+309),int(panel.bottom()+486)),QColor("#47b975"))
