"""Render Polish LCD text without modifying the user's project or playing audio."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
for name in ('arial.ttf', 'segoeui.ttf', 'cour.ttf'):
    QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts') / name))
app.setFont(QFont('Segoe UI', 9))
root = Path(__file__).resolve().parents[1]
out = root / 'output/rc8'
out.mkdir(parents=True, exist_ok=True)
window = MainWindow(AppSettings(language='pl', theme='dark', fault_effect='mini'), start_setup=False)
window.project = load_project('C:/Users/miesz/Documents/EtectroSchem Projeky/Przykładowy LCD.els')
for component in window.project.sheets[0].components:
    if 'raspberry' in component.library_id:
        component.properties.update(sim_source=str(root / 'examples/lcd_polish.py'), sim_mode='gpio')
window._rebuild_tabs()
window.show_simulation()
sim = window.simulation_window
sim.resize(1200, 850)
sim.single_step()
lcd = next(item for item in sim.symbols.values() if item.is_lcd)
sim.view.fitInView(lcd.sceneBoundingRect().adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)
app.processEvents()
sim.view.grab().save(str(out / 'lcd-polish.png'))
print(sim.circuit.result.displays)
window._sync_positions()
window._saved_state = deepcopy(window.project.to_dict())
window.close()
app.processEvents()
