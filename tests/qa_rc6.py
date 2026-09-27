"""Podglądy rc6: symbole w zbliżeniu oraz tekst tabliczki w trakcie edycji."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QFontDatabase, QFont, QColor
from PySide6.QtWidgets import QApplication
from app.core.models import Project, ComponentInstance
from app.core.settings import AppSettings
from app.canvas.component_item import ComponentItem
from app.canvas.schematic_view import SchematicView
from app.canvas.page import title_block_rect
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.libraries.built_in import BUILT_IN_ITEMS


def preview():
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(QFont("Arial", 10))
    output = Path("tmp/qa/rc6")
    output.mkdir(parents=True, exist_ok=True)
    by_name = {item.name: item for item in BUILT_IN_ITEMS}
    names = ["Przycisk Tact Switch", "Kondensator Ceramiczny", "Tranzystor NPN PN2222", "Bramka AND", "Bramka NOT", "Bramka XNOR"]
    image = QImage(1400, 840, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, name in enumerate(names):
        component = ComponentInstance(by_name[name].id, 0, 0)
        if name == "Kondensator Ceramiczny":
            component.value, component.unit = "300", "nF"
            component.properties = {"voltage": "25 V", "show_voltage": True}
        item = ComponentItem(component, language="pl")
        item.setSelected(True)
        painter.save()
        painter.translate(240+(index%3)*460, 190+(index//3)*390)
        painter.scale(4, 4)
        # Każdy kafel ma własny klip: siatka następnego rzędu nie może
        # zamalować napisów poprzedniego kafla podglądu.
        painter.setClipRect(QRectF(-55, -45, 110, 90))
        painter.setPen(QColor("#e7edf1"))
        for grid in range(-60, 81, 20):
            painter.drawLine(grid, -60, grid, 80)
            painter.drawLine(-60, grid, 60, grid)
        item.paint(painter, None)
        painter.restore()
    painter.end()
    image.save(str(output / "symbols.png"))
    project = Project(name="Zasilanie i sterowanie")
    project.metadata["author"] = "Autor projektu"
    sheet = project.sheets[0]
    view = SchematicView(project=project, settings=AppSettings(language="pl"), sheet=sheet)
    view.show()
    app.processEvents()
    for field in (None, "project", "sheet", "author"):
        if field:
            view._begin_title_edit(field)
            # Bez zaznaczenia całego tekstu łatwo porównać jego położenie.
            cursor = view._title_editor.textCursor()
            cursor.clearSelection()
            view._title_editor.setTextCursor(cursor)
        image = QImage(1440, 240, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        view.scene.render(painter, QRectF(0, 0, 1440, 240), title_block_rect(sheet))
        painter.end()
        image.save(str(output / (f"title-{field or 'static'}.png")))
        view.finish_text_editing()
    dialog = ComponentPropertiesDialog(ComponentInstance(by_name[names[1]].id, 0, 0,
        value="300", unit="nF", properties={"voltage": "25 V"}), by_name[names[1]], "pl")
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / "properties.png"))
    dialog.close()
    view.close()
    print(output.resolve())


if __name__ == "__main__":
    preview()
