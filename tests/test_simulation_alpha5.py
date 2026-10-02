"""Alfa5 preferences, readable source names and UI regressions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QLabel, QGraphicsItem, QDialog
from app.core.models import Project, Sheet, Annotation
from app.core.settings import AppSettings, load_settings, save_settings
from app.core.component_defaults import value_defaults, apply_defaults, validate_defaults
from app.core.board_code import ensure_source
from app.libraries.built_in import get_definition, AVAILABLE_ITEMS
from app.libraries.menu_groups import library_sort_key
from app.simulation.engine import Circuit
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.settings_dialog import SettingsDialog
from test_simulation import component, loop
from test_simulation_alpha2 import Bench

APP = QApplication.instance() or QApplication([])


class Alpha5Tests(unittest.TestCase):
    def test_defaults_roundtrip_and_isolation(self):
        c=component("Kondensator Elektrolityczny",100,100,"47","µF",voltage="25 V",sim_initial_voltage="auto")
        c.properties.update(sim_source="private.py",description="do not clone")
        settings=AppSettings(default_component_values={c.library_id:value_defaults(c)})
        with tempfile.TemporaryDirectory() as folder:
            store=QSettings(str(Path(folder)/"settings.ini"),QSettings.Format.IniFormat)
            save_settings(settings,store)
            loaded=load_settings(store)
        fresh=Project().new_component(c.library_id,200,200)
        apply_defaults(fresh,loaded)
        self.assertEqual((fresh.value,fresh.unit),("47","µF"))
        self.assertEqual(fresh.properties["voltage"],"25 V")
        self.assertEqual(fresh.properties["sim_initial_voltage"],"auto")
        self.assertNotIn("sim_source",fresh.properties)
        self.assertNotIn("description",fresh.properties)
        fresh.properties["voltage"]="50 V"
        self.assertEqual(loaded.default_component_values[c.library_id]["properties"]["voltage"],"25 V")

    def test_invalid_defaults_do_not_break_loading(self):
        self.assertEqual(validate_defaults([]),{})
        self.assertEqual(validate_defaults({"a":None}),{})
        result=validate_defaults({"a":{"value":[],"show_value":"no","properties":{"sim_source":"x", "sim_position":".5"}}})
        self.assertNotIn("value",result["a"])
        self.assertEqual(result["a"]["properties"],{"sim_position":".5"})

    def test_battery_nominal_and_explicit_override(self):
        old=component("Bateria 9V",100,100)
        new=Project().new_component(old.library_id,100,100)
        self.assertEqual((new.value,new.unit),("9","V"))
        resistor=component("Rezystor",400,100,"1","kΩ")
        for value,voltage in (("",9),("5",5)):
            old.value=value
            result=Circuit(loop(old,resistor)).step()
            self.assertAlmostEqual(abs(result.currents[resistor.id]),voltage/1000)
            self.assertEqual(old.value,value)

    def test_source_migration_readable_name_preserves_code(self):
        with tempfile.TemporaryDirectory() as folder, patch("app.core.board_code.appdata_directory",return_value=Path(folder)):
            board=component("Raspberry Pi 5",100,100); board.reference="mc_Raspberry.Pi.5___001"
            legacy=Path(folder)/"code"/(sha256(board.id.encode()).hexdigest()[:24]+".py")
            legacy.parent.mkdir(); legacy.write_text("# my custom code\n",encoding="utf-8")
            source=ensure_source(board)
            self.assertEqual(source.name,board.reference+"_code.py")
            self.assertEqual(source.read_bytes(),legacy.read_bytes())
            self.assertEqual(ensure_source(board),source)
            other=component("Raspberry Pi 5",100,100); other.reference=board.reference
            self.assertNotEqual(ensure_source(other),source)

    def test_external_firmware_source_keeps_extension_and_mode(self):
        with tempfile.TemporaryDirectory() as folder, patch("app.core.board_code.appdata_directory",return_value=Path(folder)):
            old=Path(folder)/"blink.ino"; old.write_text("void loop() {}",encoding="utf-8")
            board=component("Arduino Uno R3",100,100,sim_source=str(old),sim_mode="firmware")
            board.reference="mc_Arduino.Uno.R3___001"
            source=ensure_source(board)
            self.assertEqual(source.name,board.reference+"_code.ino")
            self.assertEqual(source.read_bytes(),old.read_bytes())
            self.assertEqual(board.properties["sim_mode"],"firmware")

    def test_catalog_groups_related_transistors_and_capacitors(self):
        entries=sorted(AVAILABLE_ITEMS,key=library_sort_key)
        for prefix in ("Tranzystor NPN", "Kondensator", "Szyna"):
            positions=[i for i,d in enumerate(entries) if d.name.startswith(prefix)]
            self.assertEqual(positions,list(range(min(positions),max(positions)+1)))


class Alpha5UiTests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language="pl"),start_setup=False)
        self.window.show(); APP.processEvents()

    def tearDown(self):
        self.window._saved_state=deepcopy(self.window.project.to_dict())
        self.window.close(); self.window.deleteLater(); APP.processEvents()

    def test_tools_one_add_menu_and_toolbar_cleanup(self):
        w=self.window
        tools=next(a.menu() for a in w.menuBar().actions() if a.text()=="Narzędzia")
        add=[a for a in tools.actions() if a.text().startswith("Dodaj element")]
        self.assertEqual(len(add),1); self.assertIsNotNone(add[0].menu())
        for action in (w.add_component_action,w.properties_action,w.code_action):
            self.assertNotIn(action,w.toolbar.actions())
        self.assertIn(w.properties_action,tools.actions())
        self.assertIn(w.code_action,tools.actions())
        self.assertIn(w.simulation_action,w.toolbar.actions())
        self.assertFalse(w.simulation_action.icon().isNull())
        self.assertEqual(w.fit_page_action.text(),"Dopasuj arkusz")

    def test_properties_rows_stay_compact_when_resized(self):
        c=component("Bramka NAND",100,100); c.reference="NANGat004"
        dialog=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl",self.window)
        dialog.resize(770,900); dialog.show(); APP.processEvents()
        labels={label.text():label for label in dialog.findChildren(QLabel)}
        for text in ("ID:","Typ:","NANGat004"):
            self.assertLess(labels[text].height(),40)
        self.assertLess(abs(labels["ID:"].mapTo(dialog,labels["ID:"].rect().topLeft()).y()-labels["NANGat004"].mapTo(dialog,labels["NANGat004"].rect().topLeft()).y()),5)
        self.assertTrue(dialog.save_default_values.isVisible())
        dialog.close(); dialog.deleteLater()

    def test_new_instances_use_saved_defaults_after_restart(self):
        c=component("Rezystor",100,100,"22","kΩ")
        defaults={c.library_id:value_defaults(c)}
        self.window.settings.default_component_values=defaults
        fresh=self.window._current_view().add_component(c.library_id)
        self.assertEqual((fresh.value,fresh.unit),("22","kΩ"))
        settings=SettingsDialog(self.window.settings,self.window)
        settings._accept()
        self.assertEqual(settings.result_settings().default_component_values,defaults)
        settings.deleteLater()

    def test_save_default_checkbox_persists_through_real_properties_handler(self):
        c=component("Rezystor",100,100,"10","kΩ")
        self.window.project.sheets[0].components.append(c); self.window._rebuild_tabs()
        def accept_defaults(dialog):
            dialog.value.setText("22")
            dialog.save_default_values.setChecked(True)
            dialog.accept()
            return QDialog.DialogCode.Accepted
        with tempfile.TemporaryDirectory() as folder:
            store=QSettings(str(Path(folder)/"settings.ini"),QSettings.Format.IniFormat)
            with patch.object(ComponentPropertiesDialog,"exec",accept_defaults), patch("app.ui.main_window.save_settings",side_effect=lambda settings:save_settings(settings,store)):
                self.window.show_component_properties(c)
            settings=load_settings(store)
            self.assertEqual(settings.default_component_values[c.library_id]["value"],"22")
            self.window.settings=settings
            self.window._current_view().apply_settings(settings)
            new=self.window._current_view().add_component(c.library_id)
            self.assertEqual((new.value,new.unit),("22","kΩ"))

    def test_comments_output_and_emulator_button_state(self):
        b=Bench(); source=b.add("Input"); output=b.add("Output")
        b.connect(source,0,output,0)
        annotation=Annotation("Logic test",200,100)
        sheet=Sheet(components=b.components,wires=b.wires,comments=[annotation])
        self.window.project.sheets=[sheet]; self.window._rebuild_tabs()
        before=deepcopy(self.window.project.to_dict())
        self.window.show_simulation(); sim=self.window.simulation_window
        comment=sim.comments[annotation.id]
        self.assertEqual(comment.toPlainText(),"Logic test")
        self.assertFalse(comment.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        sim.single_step(); self.assertEqual(sim.symbols[output.id].logic_label,"0")
        sim.toggle(source.id); sim.single_step()
        self.assertEqual(sim.symbols[output.id].logic_label,"1")
        halo=sim.glows[output.id]
        self.assertTrue(halo.isVisible()); self.assertLess(halo.zValue(),sim.symbols[output.id].zValue())
        self.assertLess(halo.brush().gradient().stops()[0][1].alphaF(),.4)
        self.assertEqual(before,self.window.project.to_dict())
        panel=sim.emulators
        self.assertEqual(panel.buttons[-2].text(),"Restart")
        panel.loaded=True; panel.toggle(); self.assertEqual(panel.buttons[-1].text(),"Pauza")
        panel.toggle(); self.assertEqual(panel.buttons[-1].text(),"Start")
        panel.shutdown(); self.assertEqual(panel.buttons[-1].text(),"Start")


if __name__=="__main__": unittest.main()
