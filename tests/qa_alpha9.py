"""Render ordinary UI and static local effects; no sound or full-window flash."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont,QFontDatabase
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.effects import ExplosionVisual
from app.simulation.examples import example
from app.libraries.built_in import get_definition
from test_simulation import component

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
out=Path("output/alfa9"); out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl",theme="dark",window_mode="windowed",fault_effect="mini"),start_setup=False)
window.resize(1200,820); window.project.sheets=[example("dc")]; window._rebuild_tabs(); window.show()
for _ in range(8): app.processEvents()
window.grab().save(str(out/"dark-editor.png"))
settings=SettingsDialog(window.settings,window); settings.show(); app.processEvents()
settings.grab().save(str(out/"dark-settings.png")); settings.close()
c=component("Matryca RGB WS2812B 16x16",100,100)
properties=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl",window); properties.resize(700,600); properties.show()
for _ in range(8): app.processEvents()
properties.grab().save(str(out/"dark-properties.png")); properties.close()
window.show_simulation(); sim=window.simulation_window; sim.resize(1200,800); sim.showNormal()
for _ in range(8): app.processEvents()
sim.grab().save(str(out/"simulator-pl.png"))
menu=QMenu(window); window._populate_library_menu(menu,1,QPoint(100,100))
sub=next(action.menu() for action in menu.actions() if action.text()=="Światło i podczerwień")
sub.popup(QPoint(100,100)); app.processEvents(); sub.grab().save(str(out/"secondary-entries.png")); sub.hide()
for level in ("medium","mega"):
    visual=ExplosionVisual(level); visual.setPos(500,250); sim.scene.addItem(visual); visual.set_progress(.4)
    sim.view.fitInView(sim.scene.itemsBoundingRect(),__import__('PySide6.QtCore',fromlist=['Qt']).Qt.AspectRatioMode.KeepAspectRatio)
    app.processEvents(); sim.view.grab().save(str(out/(level+"-local-effect.png"))); sim.scene.removeItem(visual)
window.settings.language="en"; sim.refresh_language(); app.processEvents()
sim.grab().save(str(out/"simulator-en.png"))
window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
print(out.resolve())
