"""Powtarzalny przegląd wizualny rc9, bez modyfikowania ustawień użytkownika."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QFontDatabase, QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
from app.core.models import ComponentInstance, Project, Wire
from app.core.settings import AppSettings
from app.canvas.component_item import ComponentItem
from app.canvas.page import title_block_rect
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.component_info_dialog import ComponentInfoDialog


def preview():
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/arial.ttf")
    app.setFont(QFont("Arial", 10))
    output = Path("tmp/qa/rc9")
    output.mkdir(parents=True, exist_ok=True)
    names = {d.name: d for d in BUILT_IN_ITEMS}
    # Każdy kafel ma własny klip, aby siatka sąsiada nie zakrywała tekstu.
    for group, entries, zoom in (
        ("compact", [("Rezystor",0),("Przycisk Tact Switch",0),("Kondensator Ceramiczny",0)], 4),
        ("relay-rotations", [("Przekaźnik Elektromechaniczny 5V", a) for a in (0,90,180,270)], 2),
        ("converter-rotations", [("Konwerter Poziomów Logicznych Iduino ST1167", a) for a in (0,90,180,270)], 2)):
        image = QImage(640*len(entries), 680, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, (name, angle) in enumerate(entries):
            c = ComponentInstance(names[name].id, 0, 0, rotation=angle)
            if name == "Rezystor":
                c.value, c.unit = "1", "kΩ"
            if name == "Kondensator Ceramiczny":
                c.value, c.unit = "300", "nF"
                c.properties = {"voltage":"25 V", "show_voltage":True}
            item = ComponentItem(c, language="pl")
            item.setSelected(True)
            p.save()
            p.setClipRect(QRectF(index*640, 0, 640, 680))
            p.translate(index*640+320, 340)
            p.scale(zoom, zoom)
            p.setPen(QColor("#e7edf1"))
            for step in range(-180,181,20):
                p.drawLine(step,-180,step,180)
                p.drawLine(-180,step,180,step)
            p.rotate(angle)
            item.paint(p, None)
            p.restore()
        p.end()
        image.save(str(output / (group+".png")))
    window = MainWindow(AppSettings(language="pl"), start_setup=False)
    window.resize(1400, 960)
    window.show()
    app.processEvents()
    view = window._current_view()
    block = title_block_rect(view._sheet)
    for x in (120, 300):
        c = window.project.new_component(names["Rezystor"].id, x, block.top()+60)
        c.value, c.unit = "1", "kΩ"
        view._sheet.components.append(c)
        view._add_component_item(c)
    view._sheet.wires.append(Wire(160, block.top()+60, 260, block.top()+60))
    view._add_wire_item(view._sheet.wires[-1])
    view.fit_page()
    app.processEvents()
    window.grab().save(str(output/"left-of-title.png"))
    for name in ("Dioda LED 3mm", "Dioda RGB"):
        d = names[name]
        c = ComponentInstance(d.id, 0, 0, properties={"color":"red"})
        dialog = ComponentPropertiesDialog(c, d, "pl", window)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(output/("rgb.png" if name.endswith("RGB") else "led.png")))
        dialog.close()
    d = names["Potencjometr Obrotowy"]
    info = ComponentInfoDialog(ComponentInstance(d.id, 0, 0), d, "pl", parent=window)
    info.show()
    app.processEvents()
    info.grab().save(str(output/"help.png"))
    info.close()
    window._saved_state = window.project.to_dict()
    window.close()
    print(output.resolve())


if __name__ == "__main__":
    preview()
