import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.core.models import ComponentInstance
from app.libraries.built_in import BUILT_IN_ITEMS
from app.canvas.component_item import ComponentItem
from app.ui.main_window import APP_VERSION


APP = QApplication.instance() or QApplication([])


class Alpha141A4Tests(unittest.TestCase):
    def test_version_is_alpha7(self):
        self.assertEqual(APP_VERSION, "1.4.0")

    def test_rfid_chip_is_in_highlighted_area_left_of_labels(self):
        definition = next(item for item in BUILT_IN_ITEMS if item.name == "Karta RFID")
        item = ComponentItem(ComponentInstance(definition.id, 0, 0))
        image = QImage(240, 160, QImage.Format.Format_ARGB32)
        image.fill(QColor("transparent"))
        painter = QPainter(image)
        painter.translate(image.width() / 2, image.height() / 2)
        item.paint(painter, None)
        painter.end()

        # The chip stays its original size; its visible top/bottom match the
        # combined visible glyph bounds of ID + RFID, with the labels to its right.
        gold = QColor("#dfc36f")
        text = QColor("#243747")
        gold_points = [(x, y) for y in range(image.height()) for x in range(image.width())
                       if image.pixelColor(x, y) == gold]
        text_points = [(x, y) for y in range(image.height()) for x in range(80, image.width())
                       if image.pixelColor(x, y) == text]
        self.assertEqual((min(y for _, y in gold_points), max(y for _, y in gold_points)),
                         (min(y for _, y in text_points), max(y for _, y in text_points)))
        self.assertLess(max(x for x, _ in gold_points), min(x for x, _ in text_points))


if __name__ == "__main__":
    unittest.main()
