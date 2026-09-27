"""Eksport arkuszy przez wspólny renderer, bez zmiany ich stanu w edytorze.

PDF i SVG zachowują wektorowe symbole, linie i tekst. PNG jest rastrem 150 dpi.
Każdy format najpierw trafia do pliku tymczasowego QSaveFile: dopiero udany
koniec renderowania zastępuje istniejący plik użytkownika. Błąd zapisu lub
rysowania nie pozostawia pustego dokumentu pod docelową nazwą.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import math

from PySide6.QtCore import QIODevice, QMarginsF, QRectF, QSaveFile, QSize, QSizeF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator

PNG_DPI = 150
# A0 przy 150 dpi ma ok. 35 mln pikseli (~140 MB bufora RGBA). Ograniczenie
# chroni przed przypadkowym utworzeniem wielogigabajtowej bitmapy z błędnych danych.
MAX_PNG_PIXELS = 36_000_000
PDF_DPI = 300


@contextmanager
def _atomic_output(path):
    destination = Path(path)
    output = QSaveFile(str(destination))
    # Nie wolno przejść na bezpośredni zapis, gdy brak miejsca/praw do temp.
    output.setDirectWriteFallback(False)
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(output.errorString())
    try:
        yield output
        if not output.commit():
            raise OSError(output.errorString())
    except BaseException:
        output.cancelWriting()
        raise


def _dimensions(view):
    """Wymiary fizycznego papieru, nie bieżącego zoomu ani rozmiaru okna."""
    if getattr(view, "_sheet", None) is None:
        raise ValueError("No sheet to export / Brak arkusza do eksportu")
    width, height = view._sheet.dimensions_mm()
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError("Invalid page dimensions / Niepoprawne wymiary arkusza")
    return width, height


def _page_layout(view):
    width, height = _dimensions(view)
    # Rozmiar QPageSize definiujemy w orientacji pionowej; QPageLayout obraca
    # go tylko raz. Jest to istotne przy PDF zawierającym różne formaty stron.
    page_size = QPageSize(QSizeF(min(width, height), max(width, height)),
                          QPageSize.Unit.Millimeter, "", QPageSize.SizeMatchPolicy.ExactMatch)
    orientation = (QPageLayout.Orientation.Landscape if width > height
                   else QPageLayout.Orientation.Portrait)
    layout = QPageLayout(page_size, orientation, QMarginsF(0, 0, 0, 0),
                         QPageLayout.Unit.Millimeter)
    # Ramkę i tabliczkę rysuje sam arkusz. Marginesy urządzenia PDF mają być
    # zerowe, inaczej nastąpiłoby dodatkowe pomniejszenie całego schematu.
    layout.setMode(QPageLayout.Mode.FullPageMode)
    return layout


def _begin_painter(device):
    painter = QPainter()
    if not painter.begin(device):
        raise OSError("Cannot start export renderer / Nie można rozpocząć eksportu")
    painter.setRenderHints(QPainter.RenderHint.Antialiasing |
                           QPainter.RenderHint.TextAntialiasing)
    return painter


def export_pdf(path, views):
    """Zapisz wszystkie podane arkusze, każdy we własnym formacie papieru."""
    views = list(views)
    if not views:
        raise ValueError("No sheets to export / Brak arkuszy do eksportu")
    # Sprawdzamy dane przed otwarciem pliku, również dla dalszych stron.
    layouts = [_page_layout(view) for view in views]
    with _atomic_output(path) as output:
        writer = QPdfWriter(output)
        writer.setCreator("ElectroSchem")
        writer.setTitle(getattr(getattr(views[0], "project", None), "name", "ElectroSchem"))
        writer.setResolution(PDF_DPI)
        if not writer.setPageLayout(layouts[0]):
            raise OSError("Cannot set PDF page format")
        painter = _begin_painter(writer)
        try:
            for index, (view, layout) in enumerate(zip(views, layouts)):
                if index:
                    if not writer.setPageLayout(layout) or not writer.newPage():
                        raise OSError("Cannot create PDF page")
                view.render_page(painter, QRectF(writer.pageLayout().fullRectPixels(PDF_DPI)))
        except BaseException:
            painter.end()
            raise
        if not painter.end():
            raise OSError("Cannot finish PDF rendering")
        # QPdfWriter musi skończyć zapis zanim QSaveFile zamknie urządzenie.
        del writer
        if output.error() != QSaveFile.FileError.NoError:
            raise OSError(output.errorString())
    return Path(path)


def export_png(path, view):
    """Zapisz bieżący arkusz w 150 dpi, bez zależności od przybliżenia GUI."""
    width_mm, height_mm = _dimensions(view)
    width = max(1, round(width_mm * PNG_DPI / 25.4))
    height = max(1, round(height_mm * PNG_DPI / 25.4))
    if width * height > MAX_PNG_PIXELS:
        raise ValueError("Page exceeds PNG memory limit / Arkusz przekracza limit pamięci PNG")
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    if image.isNull():
        raise MemoryError("Cannot allocate PNG image / Brak pamięci dla obrazu PNG")
    image.fill(QColor("white"))
    image.setDotsPerMeterX(round(PNG_DPI / 0.0254))
    image.setDotsPerMeterY(round(PNG_DPI / 0.0254))
    painter = _begin_painter(image)
    try:
        view.render_page(painter, QRectF(0, 0, width, height))
    finally:
        ended = painter.end()
    if not ended:
        raise OSError("Cannot finish PNG rendering")
    with _atomic_output(path) as output:
        if not image.save(output, "PNG"):
            raise OSError(output.errorString() or "Cannot write PNG image")
    return Path(path)


def export_svg(path, view):
    """Zapisz bieżący arkusz jako wektorowy SVG z fizycznym rozmiarem strony."""
    width_mm, height_mm = _dimensions(view)
    paper = view.paper_rect()
    with _atomic_output(path) as output:
        generator = QSvgGenerator()
        generator.setOutputDevice(output)
        # 254 dpi oznacza 10 jednostek na milimetr i daje dokładne wymiary
        # formatów A bez zaokrąglania ich do całych pikseli przy 96 dpi.
        generator.setResolution(254)
        generator.setSize(QSize(round(width_mm * 10), round(height_mm * 10)))
        generator.setViewBox(paper)
        generator.setTitle(getattr(view._sheet, "name", "ElectroSchem"))
        generator.setDescription("Electrical schematic exported by ElectroSchem")
        painter = _begin_painter(generator)
        try:
            view.render_page(painter, paper)
        except BaseException:
            painter.end()
            raise
        if not painter.end():
            raise OSError("Cannot finish SVG rendering")
        del generator
        if output.error() != QSaveFile.FileError.NoError:
            raise OSError(output.errorString())
    return Path(path)
