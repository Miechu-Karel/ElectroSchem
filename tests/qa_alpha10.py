"""Static theme/profile screenshots, without playing fault effects or audio."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.simulation.examples import example
from test_simulation import component
app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path("C:/Windows/Fonts")/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
out=Path("output/alfa10"); out.mkdir(parents=True,exist_ok=True)
for theme in ("light","dark"):
    window=MainWindow(AppSettings(language="pl",theme=theme,window_mode="windowed",fault_effect="mini"),start_setup=False)
    window.resize(1200,820); window.project.sheets=[example("dc")]; window._rebuild_tabs(); window.show()
    for _ in range(8): app.processEvents()
    window.grab().save(str(out/(theme+"-editor.png")))
    settings=SettingsDialog(window.settings,window); settings.show(); app.processEvents()
    settings.grab().save(str(out/(theme+"-settings.png"))); settings.close()
    window.show_simulation(); sim=window.simulation_window; sim.resize(1200,800)
    for tab in range(3):
        sim.tabs.setCurrentIndex(tab)
        for _ in range(8): app.processEvents()
        sim.grab().save(str(out/(theme+f"-simulator-{tab}.png")))
    window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
window=MainWindow(AppSettings(language="pl",window_mode="windowed",fault_effect="mini"),start_setup=False)
sheet=window.project.sheets[0]
for i,name in enumerate(("Rezystor","Potencjometr Obrotowy","Bramka AND","Bramka OR","Bramka NOT","Bramka XOR")):
    sheet.components.append(component(name,160+i*160,200))
window.resize(1200,820); window._rebuild_tabs(); window.show()
for standard in ("EN","IEEE/ANSI"):
    window.set_sheet_standard(standard)
    for _ in range(8): app.processEvents()
    window.grab().save(str(out/(standard.replace("/","-")+"-symbols.png")))
window._sync_positions(); window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
print(out.resolve())
