"""Offline visual QA; no network requests, audio or user settings writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtCore import QTimer
from app.core.settings import AppSettings
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.libraries.built_in import BUILT_IN_ITEMS, get_definition

app=QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
for name in ("arial.ttf", "segoeui.ttf", "cour.ttf"):
    QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts")/name))
app.setFont(QFont("Segoe UI",9))
out=Path(__file__).resolve().parents[1]/"output"/"alpha130"
out.mkdir(parents=True,exist_ok=True)
settings=AppSettings(language="pl", theme="dark",fault_effect="mini",window_mode="windowed")
window=MainWindow(settings,start_setup=False)
window.resize(1350,900); window.show(); window.show_command_panel(terminal=True)
window.command_panel.commands.setPlainText("help")
window.command_panel.execute_commands()
app.processEvents(); window.grab().save(str(out/"terminal.png"))
from app.services.assistant_examples import examples
window.command_panel.commands.setPlainText(examples()[0]["response"]["commands"])
window.command_panel.execute_commands()
app.processEvents(); window.grab().save(str(out/"proposal.png"))
def capture_preview():
    dialog=window.command_panel.preview.inspection_dialog
    dialog.grab().save(str(out/"inspection.png")); dialog.accept()
QTimer.singleShot(100,capture_preview)
window.command_panel.preview.inspect("pl")
dialog=SettingsDialog(settings,window); dialog.show(); app.processEvents()
dialog.grab().save(str(out/"settings.png")); dialog.close()
dialog.provider.setCurrentIndex(dialog.provider.findData("openai")); dialog.show(); app.processEvents()
dialog.grab().save(str(out/"settings-openai.png")); dialog.close()
dialog.provider.setCurrentIndex(dialog.provider.findData("none")); dialog.show(); app.processEvents()
dialog.grab().save(str(out/"settings-none.png")); dialog.close()
definition=next(d for d in BUILT_IN_ITEMS if d.name=="Źródło napięcia przemiennego")
component=window.project.new_component(definition.id,200,200)
dialog=ComponentPropertiesDialog(component,definition,"pl",parent=window)
dialog.show(); app.processEvents(); dialog.grab().save(str(out/"properties.png")); dialog.close()
window._saved_state=window.project.to_dict(); window.close(); app.processEvents()
print(out)
