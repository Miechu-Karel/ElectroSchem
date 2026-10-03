"""Theme consistency, drawing conventions and non-destructive code workspaces."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from pathlib import Path
from uuid import UUID
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QSettings,QPointF
from PySide6.QtGui import QColor,QImage,QPainter,QPalette
from PySide6.QtWidgets import QApplication
from app.core.settings import AppSettings,load_settings,save_settings
from app.core.models import Project,Sheet
from app.core.board_code import ensure_source,ensure_code_folder,project_code_id
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.libraries.built_in import get_definition
from app.ui.theme import canvas_colors
from app.canvas.component_item import ComponentItem
from app.simulation.engine import Circuit
from app.simulation.examples import example
from test_simulation import component

APP=QApplication.instance() or QApplication([])


class Alpha10Tests(unittest.TestCase):
    def test_strong_default_and_saved_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            store=QSettings(str(Path(directory)/"settings.ini"),QSettings.Format.IniFormat)
            self.assertEqual(AppSettings().fault_effect,"mega")
            self.assertEqual(load_settings(store).fault_effect,"mega")
            for level in ("mini","medium","mega"):
                save_settings(AppSettings(fault_effect=level,standard="IEEE/ANSI"),store)
                loaded=load_settings(store)
                self.assertEqual(loaded.fault_effect,level); self.assertEqual(loaded.standard,"IEEE/ANSI")
            dialog=SettingsDialog(AppSettings(language="pl"))
            self.assertEqual([dialog.fault_effect.itemText(i) for i in range(3)],["Delikatny","Średni","Mocny"])
            self.assertEqual(dialog.fault_effect.currentData(),"mega")
            self.assertIn("epilepsją",dialog.fault_note.text()); self.assertNotIn("pisk",dialog.fault_note.text())
            dialog.deleteLater()

    def test_project_uuid_and_rename_preserve_old_sources(self):
        with tempfile.TemporaryDirectory() as directory,patch("app.core.board_code.appdata_directory",return_value=Path(directory)):
            project=Project(name="Migający LED na Raspberry")
            board=component("Raspberry Pi 5",100,100); board.reference="Raspberry.Pi.001"
            self.assertEqual(project_code_id(project),UUID(project.id).hex)
            source=ensure_source(board,project)
            self.assertEqual(source.name,f"{board.reference}_{project_code_id(project)}_code.py")
            source.write_text("# Custom code\nfrom electroschem import Pin\np = Pin('GPIO12', Pin.OUT)\np.on()\n",encoding="utf-8")
            contents=source.read_bytes()
            project.name="A different project"
            new=ensure_source(board,project)
            self.assertEqual(source,new); self.assertEqual(source.read_bytes(),contents); self.assertEqual(new.read_bytes(),contents)
            other=deepcopy(board); other.id="other-instance"; other.properties={}
            self.assertNotEqual(ensure_source(other,project),new)

    def test_folder_creation_repeat_preservation_and_gpio_execution(self):
        with tempfile.TemporaryDirectory() as directory,patch("app.core.board_code.appdata_directory",return_value=Path(directory)):
            board=component("Raspberry Pi 5",100,100); board.reference="Pi001"; project=Project(name="Blink")
            old=ensure_source(board,project)
            folder=ensure_code_folder(board,project); entry=Path(board.properties["sim_source"])
            self.assertEqual(entry.parent,folder); self.assertTrue(old.is_file())
            self.assertEqual(ensure_code_folder(board,project),folder)
            self.assertEqual(ensure_source(board,project),entry)
            note=folder/"README.md"; note.write_text("My notes",encoding="utf-8")
            ensure_code_folder(board,project); self.assertEqual(note.read_text(),"My notes")
            self.assertTrue((folder/"requirements.txt").is_file())
            entry.write_text("from gpiozero import LED\nfrom time import sleep\nled=LED(12)\nwhile True:\n    led.on()\n    sleep(.5)\n    led.off()\n    sleep(.5)\n",encoding="utf-8")
            circuit=Circuit(Sheet(components=[board]))
            self.assertFalse(circuit.step(.001).faults)
            self.assertEqual(circuit.gpio_states[board.id]["GPIO12"],1)
            for _ in range(60): circuit.step(.01)
            self.assertEqual(circuit.gpio_states[board.id]["GPIO12"],0)

    def test_folder_conflict_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory,patch("app.core.board_code.appdata_directory",return_value=Path(directory)):
            board=component("Raspberry Pi 5",100,100); project=Project(name="Blink")
            source=ensure_source(board,project); folder=source.parent/source.stem; folder.mkdir()
            target=folder/source.name; target.write_text("keep",encoding="utf-8")
            with self.assertRaises(ValueError): ensure_code_folder(board,project)
            self.assertEqual(target.read_text(),"keep"); self.assertEqual(board.properties["sim_source"],str(source))

    def test_property_dialog_retains_new_code_link_when_saved(self):
        window=MainWindow(AppSettings(language="pl",window_mode="windowed",fault_effect="mini"),start_setup=False)
        try:
            board=component("Raspberry Pi 5",100,100)
            dialog=ComponentPropertiesDialog(board,get_definition(board.library_id),"pl",window)
            def create(component):
                component.properties.update(sim_source="C:/code/Pi_project_code.py",sim_mode="gpio")
            with patch.object(window,"edit_component_code_folder",side_effect=create) as callback:
                dialog.code_folder_button.click(); callback.assert_called_once_with(board)
            dialog.accept()
            board.properties.update(dialog.values["simulation_properties"])
            self.assertEqual(board.properties["sim_source"],"C:/code/Pi_project_code.py")
            self.assertEqual(board.properties["sim_mode"],"gpio")
            dialog.deleteLater()
        finally:
            window._saved_state=deepcopy(window.project.to_dict()); window.close(); window.deleteLater(); APP.processEvents()

    def test_external_folder_editor_receives_argument_not_shell_command(self):
        window=MainWindow(AppSettings(window_mode="windowed",fault_effect="mini"),start_setup=False)
        try:
            with tempfile.TemporaryDirectory() as directory,patch("app.core.board_code.appdata_directory",return_value=Path(directory)):
                editor=Path(directory)/"Code.exe"; editor.touch(); window.settings.editor_path=str(editor)
                window.settings.default_code_directory=directory
                board=component("Raspberry Pi 5",100,100)
                with patch("app.ui.main_window.subprocess.Popen") as launch:
                    window.edit_component_code_folder(board)
                    launch.assert_called_once_with([str(editor),board.properties["sim_code_folder"]],shell=False)
        finally:
            window._saved_state=deepcopy(window.project.to_dict()); window.close(); window.deleteLater(); APP.processEvents()

    def test_drawing_profiles_change_symbols_not_pins(self):
        def render(item):
            image=QImage(260,260,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.white)
            painter=QPainter(image); painter.translate(100,100); item.paint(painter,None,None); painter.end()
            return image
        for name in ("Rezystor","Potencjometr Obrotowy","Bramka AND","Bramka NOT","Bramka XOR"):
            with self.subTest(component=name):
                model=component(name,0,0)
                iec=ComponentItem(model,language="en",standard="EN"); ansi=ComponentItem(model,language="en",standard="IEEE/ANSI")
                pn=ComponentItem(model,language="en",standard="PN")
                self.assertEqual(render(iec),render(pn)); self.assertNotEqual(render(iec),render(ansi))
                self.assertEqual([(p.x,p.y) for p in iec.definition.pins],[(p.x,p.y) for p in ansi.definition.pins])
        project=Project(); project.sheets[0].standard="IEEE/ANSI"
        self.assertEqual(Project.from_dict(project.to_dict()).sheets[0].standard,"IEEE/ANSI")

    def test_simulator_theme_switch_and_light_editor_paper(self):
        window=MainWindow(AppSettings(language="pl",window_mode="windowed",fault_effect="mini"),start_setup=False)
        try:
            window.project.sheets=[example("dc")]; window._rebuild_tabs(); window.show_simulation(); sim=window.simulation_window
            before=deepcopy(window.project.to_dict())
            self.assertIn("1.2.0",sim.windowTitle())
            self.assertEqual(sim.windowIcon().cacheKey(),window.windowIcon().cacheKey())
            for theme in ("light","dark","light"):
                window.settings.theme=theme; sim.refresh_theme(); window._current_view().apply_settings(window.settings)
                expected=QColor("#f6f9fc" if theme=="light" else "#17212d")
                self.assertEqual(sim.palette().color(QPalette.ColorRole.Window),expected)
                self.assertEqual(sim.view.backgroundBrush().color(),QColor("#10151c"))
                lightness=QColor(canvas_colors(window.settings)["paper"]).lightness()
                self.assertGreater(lightness,140)
                if theme=="dark":
                    self.assertEqual(lightness,218)
                    channel=lightness/255
                    luminance=((channel+0.055)/1.055)**2.4
                    self.assertAlmostEqual(luminance,0.70,delta=0.01)
                else: self.assertGreater(lightness,240)
                self.assertLess(QColor(canvas_colors(window.settings)["ink"]).lightness(),100)
                self.assertNotIn("#151c26",sim.styleSheet())
            self.assertEqual(window.project.to_dict(),before)
        finally:
            window._saved_state=deepcopy(window.project.to_dict()); window.close(); window.deleteLater(); APP.processEvents()


if __name__=="__main__": unittest.main()
