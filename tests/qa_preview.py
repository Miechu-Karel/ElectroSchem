"""Powtarzalne obrazy QA bez uruchamiania sieci i ustawień użytkownika.

Uruchom z katalogu projektu: python -m tests.qa_preview (lub przez runpy).
Pliki w tmp/qa są materiałem testowym, nie projektami użytkownika.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFontDatabase, QFont, QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication
from app.core.models import Annotation, ComponentInstance, Project, Sheet, Wire
from app.core.settings import AppSettings
from app.canvas.component_item import ComponentItem
from app.libraries.built_in import BUILT_IN_ITEMS
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog


def preview():
    app = QApplication.instance() or QApplication([])
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for font in ("arial.ttf", "arialbd.ttf", "segoeui.ttf", "segoeuib.ttf"):
        if (fonts / font).is_file():
            QFontDatabase.addApplicationFont(str(fonts / font))
    app.setFont(QFont("Segoe UI", 9))
    output = Path("tmp/qa")
    output.mkdir(parents=True, exist_ok=True)
    settings = AppSettings(language="en", setup_complete=True)
    window = MainWindow(settings=settings, start_setup=False)
    window.resize(1440, 950)
    project = Project(name="ElectroSchem • RC6 verification", sheets=[Sheet(name="Main circuit"), Sheet(name="Controller")])
    by_name = {i.name: i for i in BUILT_IN_ITEMS}
    sheet = project.sheets[0]
    entries = [("Rezystor", 340, 220), ("Dioda LED 5mm", 540, 220),
               ("Czujnik Odległości HC-SR04", 330, 410), ("Układ Scalony NE555", 780, 410),
               ("Optoizolator PC817", 580, 590)]
    for name, x, y in entries:
        sheet.components.append(project.new_component(by_name[name].id, x, y))
    sheet.components[0].value, sheet.components[0].unit = "1", "kΩ"
    sheet.comments.append(Annotation("ElectroSchem 1.0.0rc6\nSymbols, named pins and editable values", 160, 100))
    sheet.wires.append(Wire(380,220,500,220,start_component_id=sheet.components[0].id,start_pin_index=1,
                            end_component_id=sheet.components[1].id,end_pin_index=0))
    project.sheets[1].components.append(project.new_component(by_name["Arduino Mega 2560"].id, 580, 360))
    window.project = project
    window._rebuild_tabs()
    window.show()
    app.processEvents()
    window._current_view().fit_page()
    app.processEvents()
    window.grab().save(str(output / "main-en.png"))
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    window.grab().save(str(output / "controller.png"))
    dialog = SettingsDialog(settings, window, first_run=True)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / "setup.png"))
    dialog.close()
    props = ComponentPropertiesDialog(sheet.components[0], by_name["Rezystor"], "pl", window)
    props.show()
    app.processEvents()
    props.grab().save(str(output / "properties.png"))
    props.close()
    # Duży atlas pozwala obejrzeć specjalistyczne symbole bez 109 okienek.
    names = ["Rezystor", "Kondensator Elektrolityczny", "Tranzystor NPN BC547",
             "Tranzystor N-MOSFET IRF540N", "Dioda RGB", "Optoizolator PC817",
             "Przekaźnik Elektromechaniczny 5V", "Silnik Krokowy NEMA 17", "Serwomechanizm SG90"]
    image = QImage(1200, 840, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, name in enumerate(names):
        painter.save()
        col, row = i % 3, i // 3
        painter.translate(col*400, row*280)
        painter.setFont(QFont("Arial", 10))
        painter.setPen(QColor("#526779"))
        painter.drawText(QRectF(15,5,370,40), Qt.AlignmentFlag.AlignCenter, name)
        painter.translate(200,145)
        item = ComponentItem(ComponentInstance(by_name[name].id, 0, 0), language="pl")
        factor = min(1.6, 340/item.boundingRect().width(), 210/item.boundingRect().height())
        painter.scale(factor, factor)
        item.paint(painter, None)
        painter.restore()
    painter.end()
    image.save(str(output / "symbols.png"))
    # Ten sam podpis przy czterech obrotach i osobne symbole bramek.
    image = QImage(1440, 1080, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for row, name in enumerate(("Rezystor", "Bramka AND", "Bramka OR", "Bramka NOT")):
        for col, angle in enumerate((0, 90, 180, 270)):
            painter.save()
            painter.translate(180+col*360, 130+row*270)
            painter.scale(2, 2)
            painter.setPen(QColor("#e7edf1"))
            for offset in range(-80, 81, 20):
                painter.drawLine(offset, -60, offset, 60)
                painter.drawLine(-80, offset, 80, offset)
            component = ComponentInstance(by_name[name].id, 0, 0, rotation=angle,
                                          display_name="Długa nazwa rezystora" if row == 0 else "")
            if row == 0:
                component.value, component.unit = "4.7", "kΩ"
            item = ComponentItem(component, language="pl")
            item.setSelected(True)
            painter.rotate(angle)
            item.paint(painter, None)
            painter.restore()
    painter.end()
    image.save(str(output / "rc3-rotations.png"))
    # Nie zamykamy przez ścieżkę zapisania dokumentu: to wyłącznie fixture QA.
    window.hide()
    window.deleteLater()
    print(str(output.resolve()))


if __name__ == "__main__":
    preview()
