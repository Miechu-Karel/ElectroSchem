"""Geometria papieru i dekoracje wspólne dla widoku oraz eksportu.

Jednostka sceny to 0,25 mm. Siatka 20 jednostek odpowiada więc fizycznym
5 mm zarówno przy zoomie, jak i w PDF. Ramka nie jest obiektem do zaznaczania.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPen, QTextDocument, QAbstractTextDocumentLayout, QPalette
from datetime import datetime
from math import ceil, floor

MM = 4.0
GRID_STEP = 20


def modification_label(project, language="en"):
    """Stary dokument bez daty pokazuje kreskę; nie wymyślamy mu historii."""
    stamp = project.metadata.get("modified_at", "") if project else ""
    try:
        value = datetime.fromisoformat(stamp).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        value = "—"
    return ("Modyfikacja: " if language == "pl" else "Modified: ") + value

def page_rect(sheet):
    width, height = sheet.dimensions_mm() if sheet else (297, 210)
    return QRectF(0, 0, width * MM, height * MM)

def frame_rect(sheet):
    """Ramka rysunkowa z marginesami wyrównanymi do siatki 5 mm."""
    page = page_rect(sheet)
    # Format A4 ma szerokość 297 mm, więc jego krawędź nie wypada na
    # wielokrotności 5 mm. Ramkę zaokrąglamy do wewnętrznej linii siatki,
    # aby każdy margines kończył się dokładnie na kratce.
    left = 2 * GRID_STEP
    top = round((10 * MM) / GRID_STEP) * GRID_STEP
    right = (int((page.right() - 10 * MM) // GRID_STEP)) * GRID_STEP
    bottom = (int((page.bottom() - 10 * MM) // GRID_STEP)) * GRID_STEP
    return QRectF(left, top, max(GRID_STEP, right - left), max(GRID_STEP, bottom - top))

def title_block_rect(sheet):
    frame = frame_rect(sheet)
    width = min(180 * MM, frame.width())
    # 30 mm = 120 jednostek sceny, czyli wielokrotność kratki.
    return QRectF(frame.right() - width, frame.bottom() - 30 * MM, width, 30 * MM)

def drawing_rect(sheet):
    """Górny prostokąt roboczy; pełny obszar L opisuje drawing_regions()."""
    frame = frame_rect(sheet)
    block = title_block_rect(sheet)
    return QRectF(frame.left(), frame.top(), frame.width(), block.top() - frame.top())


def drawing_regions(sheet):
    """Dwa nakładające się prostokąty obejmują wszystko poza tabliczką."""
    frame, block = frame_rect(sheet), title_block_rect(sheet)
    regions = [drawing_rect(sheet)]
    if block.left() > frame.left():
        regions.append(QRectF(frame.left(), frame.top(), block.left()-frame.left(), frame.height()))
    return regions


def drawing_contains(sheet, geometry):
    return any(region.contains(geometry) for region in drawing_regions(sheet))


def fit_component_position(sheet, bounds, point):
    """Najbliższe legalne położenie na siatce, także po lewej od tabliczki."""
    candidates = []
    for area in drawing_regions(sheet):
        left = ceil((area.left()-bounds.left())/GRID_STEP)*GRID_STEP
        right = floor((area.right()-bounds.right())/GRID_STEP)*GRID_STEP
        top = ceil((area.top()-bounds.top())/GRID_STEP)*GRID_STEP
        bottom = floor((area.bottom()-bounds.bottom())/GRID_STEP)*GRID_STEP
        if right < left or bottom < top:
            continue
        x = min(max(round(point.x()/GRID_STEP)*GRID_STEP, left), right)
        y = min(max(round(point.y()/GRID_STEP)*GRID_STEP, top), bottom)
        candidates.append(QPointF(x, y))
    return min(candidates, key=lambda p: (p.x()-point.x())**2+(p.y()-point.y())**2) if candidates else None


def route_allowed(sheet, points):
    """Sprawdza całe odcinki, nie tylko końce leżące poza tabliczką.

    Przecięcie odcinka z wnętrzem prostokąta liczymy parametrycznie.
    Dotknięcie samej linii obramowania jest dozwolone.
    """
    if not points or not all(drawing_contains(sheet, p) for p in points):
        return False
    block = title_block_rect(sheet).adjusted(.001, .001, -.001, -.001)
    for a, b in zip(points, points[1:]):
        low, high = 0.0, 1.0
        for start, delta, minimum, maximum in ((a.x(), b.x()-a.x(), block.left(), block.right()),
                                                (a.y(), b.y()-a.y(), block.top(), block.bottom())):
            if abs(delta) < 1e-9:
                if start < minimum or start > maximum:
                    low, high = 1, 0
                    break
            else:
                first, last = sorted(((minimum-start)/delta, (maximum-start)/delta))
                low, high = max(low, first), min(high, last)
        if low <= high:
            return False
    return True

def title_field_layout(sheet, project, field, language="en"):
    """Jedna geometria/czcionka dla tekstu statycznego i jego edytora."""
    block = title_block_rect(sheet)
    pl = language == "pl"
    font = QFont("Arial")
    font.setPixelSize(13 if field == "project" else 11)
    prefix = {"project": "", "sheet": "Arkusz: " if pl else "Sheet: ",
              "author": "Autor: " if pl else "Author: "}[field]
    row = {"project": 0, "sheet": 1, "author": 2}[field]
    rect = QRectF(block.left()+8, block.top()+row*40+2,
                  block.width()*(1 if row == 0 else .65)-16, 36)
    value_rect = rect.adjusted(QFontMetricsF(font).horizontalAdvance(prefix), 0, 0, 0)
    value = {"project": project.name if project else "ElectroSchem",
             "sheet": sheet.name if sheet else "",
             "author": str(project.metadata.get("author", "")) if project else ""}[field]
    return rect, value_rect, prefix, font, value


def title_document(value, font, width):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setDefaultFont(font)
    doc.setPlainText(value)
    doc.setTextWidth(width)
    return doc


def draw_page(painter, sheet, project=None, settings=None, editing_field=None):
    page = page_rect(sheet)
    painter.save()
    painter.setClipRect(page)
    painter.fillRect(page, QColor("white"))
    visible = getattr(settings, "grid_visible", True)
    # Wyłączenie w ustawieniach oznacza zgodnie ze specyfikacją przygaszenie,
    # a nie wyłączenie snapowania lub całkowite usunięcie siatki.
    painter.setPen(QPen(QColor("#e7edf1" if visible else "#f7f8fa"), 0.6))
    for x in range(0, int(page.width()) + 1, GRID_STEP):
        painter.drawLine(x, 0, x, int(page.height()))
    for y in range(0, int(page.height()) + 1, GRID_STEP):
        painter.drawLine(0, y, int(page.width()), y)
    painter.setPen(QPen(QColor("#738596"), 0.8))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(page.adjusted(0.5, 0.5, -0.5, -0.5))
    frame = frame_rect(sheet)
    painter.setPen(QPen(QColor("#667786"), 1.0))
    painter.drawRect(frame)
    # Tabliczka jest dopasowana do małych arkuszy. Nie deklarujemy formalnej
    # certyfikacji ISO: przechowujemy jednoznaczne podstawowe pola dokumentu.
    width = min(180 * MM, frame.width())
    block = title_block_rect(sheet)
    painter.fillRect(block, QColor("white"))
    painter.drawRect(block)
    painter.drawLine(block.left(), block.top() + 40, block.right(), block.top() + 40)
    painter.drawLine(block.left(), block.top() + 80, block.right(), block.top() + 80)
    painter.drawLine(block.left() + width * .65, block.top() + 40, block.left() + width * .65, block.bottom())
    pl = getattr(settings, "language", "en") == "pl"
    painter.setPen(QColor("#233a4e"))
    # PixelSize to tutaj jednostki sceny (0,25 mm), nie fizyczne piksele
    # drukarki. PointSize zależałby od DPI PDF i powiększał tekst 3-krotnie.
    for field in ("project", "sheet", "author"):
        rect, value_rect, prefix, font, value = title_field_layout(sheet, project, field, "pl" if pl else "en")
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, prefix)
        if field == editing_field:
            continue  # Edytor JEST tekstem komórki, nie nakładką na drugi napis.
        doc = title_document(value, font, value_rect.width())
        painter.save()
        painter.setClipRect(value_rect)
        painter.translate(value_rect.left(), value_rect.top()+max(0, (value_rect.height()-doc.size().height())/2))
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QPalette.ColorRole.Text, QColor("#233a4e"))
        doc.documentLayout().draw(painter, context)
        painter.restore()
    index, total = 1, 1
    if project and sheet:
        total = len(project.sheets)
        index = next((i + 1 for i, value in enumerate(project.sheets) if value.id == sheet.id), 1)
    small_font = QFont("Arial")
    small_font.setPixelSize(11)
    painter.setFont(small_font)
    painter.drawText(QRectF(block.left()+width*.65+8, block.top()+42, width*.35-16, 36), Qt.AlignmentFlag.AlignVCenter,
                     f"{index} / {total} · {sheet.paper_size if sheet else 'A4'}")
    painter.drawLine(block.left()+width*.65, block.top()+100, block.right(), block.top()+100)
    small_font.setPixelSize(9)
    painter.setFont(small_font)
    painter.drawText(QRectF(block.left()+width*.65+8, block.top()+81, width*.35-16, 18), Qt.AlignmentFlag.AlignVCenter,
                     "ElectroSchem · " + getattr(sheet, "standard", getattr(settings, "standard", "EN")))
    painter.drawText(QRectF(block.left()+width*.65+8, block.top()+101, width*.35-16, 18), Qt.AlignmentFlag.AlignVCenter,
                     modification_label(project, "pl" if pl else "en"))
    painter.restore()
