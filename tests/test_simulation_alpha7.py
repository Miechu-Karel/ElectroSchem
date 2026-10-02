"""Alfa7 layout, help, filename and opt-in effect regressions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtGui import QFont, QImage, QPainter, QColor
from app.core.settings import AppSettings
from app.core.file_names import project_filename
from app.libraries.built_in import get_definition
from app.libraries.component_info import explanation
from app.libraries.pin_info import pin_explanation
from app.libraries.menu_groups import subgroup
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.component_info_dialog import ComponentInfoDialog
from app.ui.manual_dialog import ManualDialog
from app.ui.wrapping_label import WrappingLabel
from app.simulation.examples import example
from test_simulation import component

APP=QApplication.instance() or QApplication([])


class Alpha7Tests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language="pl"),start_setup=False)
        self.window.show(); APP.processEvents()

    def tearDown(self):
        self.window._saved_state=deepcopy(self.window.project.to_dict())
        self.window.close(); self.window.deleteLater(); APP.processEvents()

    def test_wrapped_properties_keep_full_height_at_large_fonts(self):
        for name in ("Szyna Zasilania +12V","Bramka Logiczna 74HC04","Bramka NAND"):
            for points in (9,12,16):
                c=component(name,100,100)
                dialog=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl",self.window)
                dialog.setStyleSheet(f"QWidget {{font-family: Arial; font-size: {points}pt;}}")
                dialog.resize(600,420); dialog.show()
                for _ in range(8): APP.processEvents()
                labels=dialog.findChildren(WrappingLabel)
                for label in labels:
                    self.assertGreaterEqual(label.height(),label.heightForWidth(label.width()),(name,points,label.text(),label.size()))
                    self.assertGreaterEqual(label.y(),0)
                    self.assertLessEqual(label.y()+label.height(),label.parentWidget().height())
                scroll=dialog.findChild(QScrollArea)
                self.assertGreaterEqual(scroll.widget().height(),scroll.widget().minimumSizeHint().height())
                dialog.close(); dialog.deleteLater()

    def test_filenames_use_project_title_for_save_and_each_export(self):
        self.window.project.name="Migające LEDy 2.0"
        self.window.current_file=Path("old-name.els")
        with patch("app.ui.main_window.QFileDialog.getSaveFileName",return_value=("","")) as dialog:
            self.window.save_project_as()
            self.assertEqual(Path(dialog.call_args.args[2]).name,"Migające LEDy 2.0.els")
            for kind in ("pdf","png","svg"):
                self.window._export(kind)
                self.assertEqual(Path(dialog.call_args.args[2]).name,"Migające LEDy 2.0."+kind)
        self.assertEqual(project_filename('A:/B?*\n',"els"),'A__B__.els')
        self.assertEqual(project_filename("CON", "els"),"_CON.els")
        self.assertEqual(project_filename("..", "pdf"),"project.pdf")
        self.assertEqual(project_filename("Test.els", "els"),"Test.els")

    def test_manual_has_sections_table_and_no_long_dashes(self):
        for language in ("pl","en"):
            dialog=ManualDialog(language,self.window)
            html=dialog.browser.toHtml(); text=dialog.browser.toPlainText()
            self.assertIn("<table",html)
            self.assertIn("Ctrl+Shift+S",text)
            self.assertNotIn("—",text); self.assertNotIn("–",text)
            self.assertIn("Symulacja" if language=="pl" else "Simulation",text)
            dialog.deleteLater()
        self.assertEqual(self.window.help_action.text(),"Instrukcja Obsługi")
        actions=self.window.toolbar.actions()
        self.assertIs(actions[actions.index(self.window.search_action)+1],self.window.component_help_action)
        self.assertFalse(self.window.component_help_action.icon().isNull())
        c=self.window.add_component_from_id(component("Rezystor",0,0).library_id)
        with patch("app.ui.main_window.ComponentInfoDialog") as info:
            self.window.component_help_action.trigger()
            self.assertIs(info.call_args.args[0],c)

    def test_logic_help_has_actual_function_all_pins_and_active_link(self):
        c=component("Bramka Logiczna 74HC04",0,0); d=get_definition(c.library_id)
        for language in ("en","pl"):
            dialog=ComponentInfoDialog(c,d,language,parent=self.window)
            text=dialog.browser.toPlainText()
            self.assertIn("NOT",explanation(d,language))
            self.assertIn("6",text)
            for pin in d.pins:
                self.assertIn(pin.name,text)
                self.assertNotIn("Device-specific",pin_explanation(d,pin,language))
            self.assertTrue(dialog.browser.openExternalLinks())
            self.assertIn('href="https://www.ti.com/lit/ds/symlink/sn74hc04.pdf"',dialog.browser.toHtml())
            dialog.deleteLater()
        self.assertEqual(subgroup(d),("Logic ICs","Układy logiczne"))

    def test_custom_text_is_not_html_and_unsafe_url_is_not_clickable(self):
        c=component("Rezystor",0,0); d=replace(get_definition(c.library_id),source_url="javascript:alert(1)")
        dialog=ComponentInfoDialog(c,d,"en",{"description":"<b>literal</b><img src='file:///secret'>"},self.window)
        self.assertIn("<b>literal</b>",dialog.browser.toPlainText())
        self.assertNotIn("<img",dialog.browser.toHtml())
        self.assertNotIn('href="javascript:',dialog.browser.toHtml())
        dialog.deleteLater()

    def test_nc_relay_is_not_described_as_unconnected(self):
        d=get_definition(component("Przekaźnik Elektromechaniczny 5V",0,0).library_id)
        pin=next(p for p in d.pins if p.name=="NC")
        self.assertIn("COM",pin_explanation(d,pin))

    def test_flash_is_opt_in_single_fade_resettable_and_audio_mocked(self):
        self.window.project.sheets=[example("capacitor")]; self.window._rebuild_tabs()
        self.window.show_simulation(); sim=self.window.simulation_window
        with patch("app.ui.fault_sound.FaultSound") as audio:
            for dramatic in (False,True):
                self.window.settings.dramatic_faults=dramatic
                self.window.settings.fault_effect="legacy"; sim.reset()
                for _ in range(100):
                    sim.advance()
                    if sim.circuit.result.faults: break
                self.assertTrue(sim.circuit.result.faults)
                sim.fault_animation.stop(); sim.animate_faults(0)
                self.assertEqual(sim.flash_overlay.opacity,1 if dramatic else 0)
                sim.animate_faults(.5)
                self.assertGreaterEqual(sim.flash_overlay.opacity,0)
                self.assertLess(sim.flash_overlay.opacity,1)
                sim.animate_faults(1); self.assertEqual(sim.flash_overlay.opacity,0)
                sim.reset(); self.assertEqual(sim.flash_overlay.opacity,0)
            audio.return_value.play.assert_called_once()
