"""Offline alfa7 UI snapshots; no audio, flashing animation or user-data writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtWidgets import QApplication
from app.core.settings import AppSettings
from app.libraries.built_in import get_definition
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.component_info_dialog import ComponentInfoDialog
from app.ui.manual_dialog import ManualDialog
from app.ui.settings_dialog import SettingsDialog
from test_simulation import component

app=QApplication.instance() or QApplication([])
for name in ("arial.ttf","arialbd.ttf","segoeui.ttf","segoeuib.ttf"):
    path=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/name
    if path.is_file(): QFontDatabase.addApplicationFont(str(path))
app.setFont(QFont("Segoe UI",9))
out=Path("output/alfa7"); out.mkdir(parents=True,exist_ok=True)
window=MainWindow(AppSettings(language="pl"),start_setup=False)
window.show(); app.processEvents()
window.grab().save(str(out/"toolbar.png"))
for name,key in (("Szyna Zasilania +12V","rail"),("Bramka Logiczna 74HC04","74hc04")):
    c=component(name,100,100); c.reference="Example001"; d=get_definition(c.library_id)
    dialog=ComponentPropertiesDialog(c,d,"pl",window)
    dialog.setStyleSheet("QWidget {font-family: 'Segoe UI'; font-size: 12pt;}")
    dialog.resize(640,530); dialog.show()
    for _ in range(8): app.processEvents()
    dialog.grab().save(str(out/(key+"-properties.png"))); dialog.close()
    if key=="74hc04":
        info=ComponentInfoDialog(c,d,"pl",parent=window); info.show(); app.processEvents()
        info.grab().save(str(out/"component-help.png")); info.close()
manual=ManualDialog("pl",window); manual.show(); app.processEvents()
manual.grab().save(str(out/"manual.png")); manual.close()
settings=SettingsDialog(window.settings,window); settings.show(); app.processEvents()
settings.grab().save(str(out/"settings.png")); settings.close()
window._saved_state=deepcopy(window.project.to_dict()); window.close(); app.processEvents()
print(out.resolve())
