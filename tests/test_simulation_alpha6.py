"""Logic I/O visual regressions for alfa6."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
import unittest
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
from app.canvas.component_item import ComponentItem
from app.core.models import Sheet
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.simulation_window import LiveSymbol
from test_simulation import component
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])


class Alpha6Tests(unittest.TestCase):
    def test_bounds_follow_pin_side_and_grid_without_moving_pins(self):
        for name,left,right,pin in (("Input",-20,40,40),("Output",-40,20,-40)):
            for rotation in (0,90,180,270):
                c=component(name,200,200); c.rotation=rotation; c.show_name=False
                item=ComponentItem(c)
                self.assertEqual(item._hit_rect,QRectF(left,-20,60,40))
                self.assertEqual(item.pin_positions()[0],item.mapToScene(QPointF(pin,0)))
                for point in (item.mapToScene(item._hit_rect.topLeft()), item.mapToScene(item._hit_rect.bottomRight())):
                    self.assertAlmostEqual(point.x()%20,0)
                    self.assertAlmostEqual(point.y()%20,0)
                c.show_name=True; item.update_labels()
                self.assertEqual(item._hit_rect,QRectF(left,-20,60,60))
                self.assertTrue(item.boundingRect().contains(item._name_rect))

    def test_input_output_frames_and_numeric_font_render_identically(self):
        for rotation in (0,90,180,270):
            images=[]
            for name in ("Input","Output"):
                c=component(name,0,0); c.show_name=False; c.rotation=rotation
                item=LiveSymbol(c); item.logic_label="1"
                image=QImage(100,100,QImage.Format.Format_ARGB32); image.fill(QColor("#10151c"))
                painter=QPainter(image); painter.translate(50,50)
                item.paint(painter,None); painter.end()
                images.append(image.copy(29,29,42,42))
                self.assertNotEqual(image.pixelColor(50,30),QColor("#10151c"))
            self.assertEqual(images[0],images[1])

    def test_both_glows_are_white_and_follow_state(self):
        window=MainWindow(AppSettings(),start_setup=False)
        try:
            b=Bench(); source=b.add("Input"); output=b.add("Output"); b.connect(source,0,output,0)
            window.project.sheets=[Sheet(components=b.components,wires=b.wires)]; window._rebuild_tabs()
            before=deepcopy(window.project.to_dict())
            window.show_simulation(); sim=window.simulation_window
            for expected in ("0","1","0"):
                sim.single_step()
                for c in (source,output):
                    self.assertEqual(sim.symbols[c.id].logic_label,expected)
                    glow=sim.glows[c.id]
                    self.assertEqual(glow.isVisible(),expected=="1")
                    if expected=="1":
                        self.assertLess(glow.zValue(),sim.symbols[c.id].zValue())
                        for _,color in glow.brush().gradient().stops():
                            self.assertEqual((color.red(),color.green(),color.blue()),(255,255,255))
                sim.toggle(source.id)
            self.assertEqual(window.project.to_dict(),before)
        finally:
            window._saved_state=deepcopy(window.project.to_dict())
            window.close(); window.deleteLater(); APP.processEvents()
