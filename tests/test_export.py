"""Eksport ma zachować format papieru, zawartość i poprzedni plik przy błędzie."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF, QRectF, QSize
from PySide6.QtGui import QFontDatabase, QImage, QPainter, QPainterPath
from PySide6.QtPdf import QPdfDocument
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from app.canvas.schematic_view import SchematicView
from app.canvas.page import title_block_rect
from app.core.models import Annotation, Project, Sheet, Wire
from app.core.settings import AppSettings
from app.libraries.built_in import BUILT_IN_ITEMS
from app.services.export import export_pdf, export_png, export_svg, PNG_DPI

APP = QApplication.instance() or QApplication([])
# Windowsowy plugin offscreen nie enumeruje fontów systemowych (w przeciwieństwie
# do normalnego GUI). Ładujemy ten sam Arial jawnie, aby QA nie testowało tofu.
if not QFontDatabase.families():
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
RESISTOR = next(item for item in BUILT_IN_ITEMS if item.name == "Rezystor")


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="elektroschem-export-")
        self.directory = Path(self.temp.name)
        self.project = Project(name="Export regression")
        self.project.sheets = [Sheet(name="A4 landscape"),
                               Sheet(name="A5 portrait", paper_size="A5", orientation="portrait"),
                               Sheet(name="A3 landscape", paper_size="A3")]
        self.views = []
        for sheet in self.project.sheets:
            component = self.project.new_component(RESISTOR.id, 300, 300)
            component.value, component.unit = "1", "kΩ"
            sheet.components.append(component)
            sheet.comments.append(Annotation("Arial 12 - Export test", 180, 180))
            sheet.wires.append(Wire(100, 300, 260, 300, points=[[100, 300], [260, 300]],
                                    end_component_id=component.id, end_pin_index=0))
            self.views.append(SchematicView(project=self.project, settings=AppSettings(), sheet=sheet))

    def tearDown(self):
        for view in self.views:
            view.close()
            view.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def test_pdf_all_pages_keep_physical_size_and_render(self):
        destination = self.directory / "sheets.pdf"
        self.assertEqual(export_pdf(destination, self.views), destination)
        document = QPdfDocument()
        self.assertEqual(document.load(str(destination)), QPdfDocument.Error.None_)
        self.assertEqual(document.pageCount(), 3)
        for index, sheet in enumerate(self.project.sheets):
            page = document.pagePointSize(index)
            width, height = sheet.dimensions_mm()
            # PDF MediaBox is expressed in 1/72 inch and Qt rounds slightly.
            self.assertAlmostEqual(page.width(), width * 72 / 25.4, delta=0.6)
            self.assertAlmostEqual(page.height(), height * 72 / 25.4, delta=0.6)
            image = document.render(index, QSize(round(width * 2), round(height * 2)))
            self.assertFalse(image.isNull())
            # Real content exists: more than just a blank page/header.
            # Próbkowanie co trzeci piksel pomija cienkie linie, gdy po
            # wyrównaniu marginesów wypadną między próbkami. Sprawdź kabel
            # we właściwym miejscu, niezależnie od rozmiaru papieru.
            scale = image.width() / (width * 4)
            green = sum(image.pixelColor(x, y).green() > image.pixelColor(x, y).red() + 20
                        for x in range(round(120*scale), round(230*scale))
                        for y in range(round(300*scale)-2, round(300*scale)+3))
            self.assertGreater(green, 10)
            self.assertIn("Export", document.getAllText(index).text())
        document.close()

    def test_png_has_150dpi_page_size_and_real_content(self):
        destination = self.directory / "sheet.png"
        export_png(destination, self.views[0])
        image = QImage(str(destination))
        self.assertEqual(image.size(), QSize(round(297 * PNG_DPI / 25.4), round(210 * PNG_DPI / 25.4)))
        self.assertAlmostEqual(image.dotsPerMeterX() * 0.0254, 150, delta=0.02)
        self.assertAlmostEqual(image.dotsPerMeterY() * 0.0254, 150, delta=0.02)
        # The drawn wire is green at the exact physical location in the image.
        scale = image.width() / self.views[0].paper_rect().width()
        pixel = image.pixelColor(round(180 * scale), round(300 * scale))
        self.assertGreater(pixel.green(), pixel.red())

    def test_svg_is_vector_and_has_physical_dimensions(self):
        destination = self.directory / "sheet.svg"
        export_svg(destination, self.views[0])
        root = ET.parse(destination).getroot()
        self.assertEqual(root.attrib["width"], "297mm")
        self.assertEqual(root.attrib["height"], "210mm")
        self.assertEqual(root.attrib["viewBox"], "0 0 1188 840")
        self.assertGreater(len(root.findall(".//{http://www.w3.org/2000/svg}path")), 0)
        self.assertFalse(root.findall(".//{http://www.w3.org/2000/svg}image"))

    def test_text_size_is_consistent_across_output_device_dpi(self):
        """PDF300dpi/PNG150dpi/SVG254dpi muszą mieć ten sam fizyczny tekst."""
        png, pdf, svg = (self.directory / ("font." + ext) for ext in ("png", "pdf", "svg"))
        export_png(png, self.views[0])
        export_pdf(pdf, [self.views[0]])
        export_svg(svg, self.views[0])
        raster = QImage(str(png))
        document = QPdfDocument()
        self.assertEqual(document.load(str(pdf)), QPdfDocument.Error.None_)
        pdf_image = document.render(0, raster.size())
        svg_image = QImage(raster.size(), QImage.Format.Format_ARGB32_Premultiplied)
        svg_image.fill(0xFFFFFFFF)
        renderer = QSvgRenderer(str(svg))
        self.assertTrue(renderer.isValid())
        painter = QPainter(svg_image)
        renderer.render(painter)
        painter.end()
        scale = raster.width() / self.views[0].paper_rect().width()

        def dark_bounds(image, scene_area):
            area = QRectF(scene_area.x()*scale, scene_area.y()*scale,
                          scene_area.width()*scale, scene_area.height()*scale).toRect()
            pixels = [(x, y) for x in range(area.left(), area.right())
                      for y in range(area.top(), area.bottom())
                      if image.pixelColor(x, y).lightness() < 95]
            self.assertTrue(pixels)
            return (min(x for x, y in pixels), min(y for x, y in pixels),
                    max(x for x, y in pixels), max(y for x, y in pixels))

        # Pierwszy obszar to komentarz Arial12, drugi tytuł tabliczki. Omijamy
        # ramki, aby test porównywał litery, nie wymiary tabeli.
        block = title_block_rect(self.project.sheets[0])
        title_area = QRectF(block.left()+4, block.top()+3, 250, 34)
        for area in (QRectF(175, 175, 250, 50), title_area):
            expected = dark_bounds(raster, area)
            for image in (pdf_image, svg_image):
                actual = dark_bounds(image, area)
                for a, b in zip(actual, expected):
                    self.assertAlmostEqual(a, b, delta=3)
        document.close()

    def test_export_restores_selection_and_wire_preview(self):
        view = self.views[0]
        item = next(iter(view._component_items.values()))
        item.setSelected(True)
        preview = QPainterPath(QPointF(100, 100))
        preview.lineTo(200, 200)
        view._wire_preview = view.scene.addPath(preview)
        # A selected item must remain selected after PDF/PNG/SVG export.
        for function, suffix in ((export_png, "png"), (export_svg, "svg")):
            function(self.directory / ("selection." + suffix), view)
            self.assertTrue(item.isSelected())
            self.assertTrue(view._wire_preview.isVisible())
        export_pdf(self.directory / "selection.pdf", [view])
        self.assertTrue(item.isSelected())

    def test_render_failure_never_replaces_existing_file(self):
        for function, suffix in ((export_pdf, "pdf"), (export_png, "png"), (export_svg, "svg")):
            destination = self.directory / ("existing." + suffix)
            destination.write_bytes(b"previous user file")
            with patch.object(self.views[0], "render_page", side_effect=RuntimeError("injected failure")):
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    function(destination, [self.views[0]] if suffix == "pdf" else self.views[0])
            self.assertEqual(destination.read_bytes(), b"previous user file")
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()),
                         ["existing.pdf", "existing.png", "existing.svg"])

    def test_unwritable_target_and_empty_document_are_errors(self):
        with self.assertRaises(OSError):
            export_pdf(self.directory / "missing" / "fail.pdf", self.views)
        with self.assertRaises(ValueError):
            export_pdf(self.directory / "empty.pdf", [])
        self.assertFalse((self.directory / "empty.pdf").exists())

    def test_png_memory_cap_checked_before_allocation(self):
        with patch.object(self.views[0]._sheet, "dimensions_mm", return_value=(100000, 100000)):
            with self.assertRaisesRegex(ValueError, "memory limit"):
                export_png(self.directory / "huge.png", self.views[0])
        self.assertFalse((self.directory / "huge.png").exists())


if __name__ == "__main__":
    unittest.main()
