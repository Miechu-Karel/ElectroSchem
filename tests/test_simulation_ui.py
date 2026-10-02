"""Integracja okna, kopii arkusza, właściwości oraz emulatora z obwodem."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.settings import AppSettings
from app.core.models import Sheet,Project
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.canvas.page import draw_page
from app.simulation.engine import Circuit
from app.simulation.examples import example
from app.libraries.built_in import get_definition
from test_simulation import component,wire,led_circuit,loop
from test_emulators import AVAILABLE,hex_firmware

APP=QApplication.instance() or QApplication([])


class SimulationUiTests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language="pl"),start_setup=False)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window._saved_state=deepcopy(self.window.project.to_dict())
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def open_sheet(self,sheet):
        self.window.project.sheets=[sheet]
        self.window._rebuild_tabs()
        self.window.show_simulation()
        APP.processEvents()
        return self.window.simulation_window

    def test_blank_sheet_blocks_start_but_demo_runs_without_modifying_project(self):
        self.window.show_simulation()
        sim=self.window.simulation_window
        self.assertFalse(sim.run_button.isEnabled())
        before=deepcopy(self.window.project.to_dict())
        sim.load_example(1)
        self.assertTrue(sim.run_button.isEnabled(),sim.log.toPlainText())
        sim.single_step()
        self.assertTrue(any(g.isVisible() for g in sim.glows.values()))
        self.assertEqual(before,self.window.project.to_dict())
        sim.reset()
        self.assertEqual(sim.circuit.time,0)

    def test_snapshot_switch_and_reset_are_isolated(self):
        sim=self.open_sheet(example("led"))
        before=deepcopy(self.window.project.to_dict())
        d=next(d for d in sim.circuit.devices if d.kind=="switch")
        sim.toggle(d.component.id)
        self.assertFalse(d.closed)
        sim.reset()
        self.assertTrue(next(d for d in sim.circuit.devices if d.kind=="switch").closed)
        self.assertEqual(before,self.window.project.to_dict())

    def test_time_scale_is_wall_clock_based(self):
        sim=self.open_sheet(example("led"))
        sim.dt.setValue(1)
        sim.time_scale.setValue(50)
        sim.wall_start_ns=100_000_000_000; sim.sim_start=0
        with patch("app.ui.simulation_window.perf_counter_ns",return_value=102_000_000_000):
            self.assertEqual(sim._steps_due(),1000)
        sim.time_scale.setValue(100)
        with patch("app.ui.simulation_window.perf_counter_ns",return_value=102_000_000_000):
            self.assertEqual(sim._steps_due(),2000)
        with patch("app.ui.simulation_window.perf_counter_ns",return_value=101_000_000_000):
            self.assertEqual(sim._steps_due(),1000)
        self.assertIn("9 192 631 770",sim.time_scale.toolTip())
        sim.circuit.time=10
        with patch("app.ui.simulation_window.perf_counter_ns",return_value=200_000_000_000):
            sim.run()
        with patch("app.ui.simulation_window.perf_counter_ns",return_value=201_000_000_000):
            self.assertEqual(sim._steps_due(),1000)
        sim.pause()

    def test_gentle_fault_is_silent_and_strong_has_sound(self):
        self.window.settings.fault_effect="mini"
        sim=self.open_sheet(example("capacitor"))
        self.assertFalse(self.window.settings.dramatic_faults)
        for _ in range(100):
            sim.advance()
            if sim.circuit.result.faults: break
        self.assertIsNone(sim.fault_sound)
        self.window.settings.fault_effect="mega"
        sim.reset()
        with patch("app.ui.fault_sound.FaultSound") as sound:
            for _ in range(100):
                sim.advance()
                if sim.circuit.result.faults: break
            sound.return_value.play.assert_called_once()

    def test_board_code_button_and_new_icons(self):
        board=component("Raspberry Pi 5",100,100)
        dialog=ComponentPropertiesDialog(board,get_definition(board.library_id),"pl",self.window)
        with patch.object(self.window,"edit_component_code") as edit:
            dialog.edit_code_button.click()
            edit.assert_called_once_with(board)
        dialog.deleteLater()
        for action in (self.window.code_action,self.window.properties_action,self.window.add_component_action,self.window.search_action):
            self.assertFalse(action.icon().isNull())
        menus=[a.text() for a in self.window.menuBar().actions()]
        self.assertNotIn("Symulacja",menus)

    def test_properties_store_simulation_parameters(self):
        c=component("Dioda LED 3mm",100,100,color="red")
        dialog=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl",self.window)
        dialog.simulation_fields["sim_max_current"].setText("10 mA")
        dialog.accept()
        self.assertEqual(dialog.values["simulation_properties"]["sim_max_current"],"10 mA")
        self.assertNotIn("sim_max_current",c.properties)
        dialog.deleteLater()

    def test_polarity_warning_logs_once_and_does_not_disable_run(self):
        source=component("Bateria 9V",100,100,"5")
        cap=component("Kondensator Elektrolityczny",400,200,"10","µF",voltage="25 V")
        sim=self.open_sheet(loop(source,cap))
        for _ in range(4): sim.single_step()
        self.assertEqual(sim.log.toPlainText().count("Ostrzeżenie:"),1)
        self.assertTrue(sim.run_button.isEnabled())
        self.assertFalse(sim.circuit.result.faults)
        sim.reset()
        sim.single_step()
        self.assertEqual(sim.log.toPlainText().count("Ostrzeżenie:"),1)

    def test_capacitor_auto_start_survives_properties_roundtrip(self):
        cap=component("Kondensator Elektrolityczny",100,100,"10","µF",voltage="25 V")
        dialog=ComponentPropertiesDialog(cap,get_definition(cap.library_id),"pl",self.window)
        dialog.accept()
        self.assertEqual(dialog.values["simulation_properties"]["sim_initial_voltage"],"auto")
        dialog.deleteLater()

    def test_alpha2_rail_and_transistor_examples_and_reset(self):
        self.window.show_simulation()
        sim=self.window.simulation_window
        for key in ("rails","transistor"):
            index=sim.examples.findData(key)
            self.assertGreater(index,0)
            sim.load_example(index)
            self.assertTrue(sim.run_button.isEnabled(),sim.log.toPlainText())
            sim.single_step()
            self.assertTrue(any(g.isVisible() for g in sim.glows.values()))
            self.assertFalse(sim.circuit.result.faults)
        switch=next(d for d in sim.circuit.devices if d.kind=="switch")
        sim.toggle(switch.component.id)
        sim.single_step()
        led=next(d for d in sim.circuit.devices if d.kind=="led")
        self.assertLess(sim.circuit.result.brightness[led.component.id],1e-6)
        sim.reset()
        sim.single_step()
        self.assertGreater(sim.circuit.result.brightness[led.component.id],.1)

    def test_alpha2_vcc_and_potentiometer_properties(self):
        for name,key,value in (("Szyna Zasilania VCC","sim_voltage","9 V"),("Potencjometr Obrotowy","sim_position","0")):
            c=component(name,100,100,"1000" if "Potencjometr" in name else "")
            dialog=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl",self.window)
            dialog.simulation_fields[key].setText(value)
            dialog.accept()
            self.assertEqual(dialog.values["simulation_properties"][key],value)
            dialog.deleteLater()

    def test_faint_grid_is_dots_not_lines(self):
        image=QImage(1200,900,QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        painter=QPainter(image)
        draw_page(painter,Sheet(),settings=AppSettings(grid_visible=False))
        painter.end()
        self.assertNotEqual(image.pixelColor(200,200),image.pixelColor(201,201))
        self.assertEqual(image.pixelColor(200,201),image.pixelColor(201,201))

    def test_ac_example_does_not_false_trip_at_rms_peak(self):
        c=Circuit(example("ac"))
        for _ in range(2500):result=c.step(.0001)
        self.assertFalse(result.faults)
        self.assertGreater(max(result.brightness.values()),.8)

    def test_capacitor_example_fault_and_visual_marker(self):
        sim=self.open_sheet(example("capacitor"))
        for _ in range(100):
            sim.advance()
            if sim.circuit.result.faults:break
        self.assertTrue(sim.circuit.result.faults)
        self.assertTrue(sim.run_button.isEnabled())
        self.assertTrue(sim.fault_marks)

    @unittest.skipUnless(AVAILABLE,"Optional emulator dependencies not installed")
    def test_firmware_drives_led_through_schematic_wires(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"gpio.hex"
            path.write_text(hex_firmware([0x9a25,0x9a2d,0xcfff]),encoding="ascii")
            board=component("Arduino Uno R3",720,320,sim_firmware=str(path))
            battery=component("Bateria 9V",150,150,"5")
            resistor=component("Rezystor",200,500,"330")
            led=component("Dioda LED 3mm",450,600,color="red")
            pins={p.name:i for i,p in enumerate(get_definition(board.library_id).pins)}
            sheet=Sheet(components=[battery,board,resistor,led],wires=[
                wire(battery,0,board,pins["5V"]),wire(battery,1,board,pins["GND"]),
                wire(board,pins["D13/SCK"],resistor,0),wire(resistor,1,led,0),wire(led,1,battery,1)])
            sim=self.open_sheet(sheet)
            self.assertIsNotNone(sim.circuit,sim.log.toPlainText())
            sim.single_step()
            for _ in range(150):
                QTest.qWait(20)
                if sim.circuit.time>0 or not sim.step_button.isEnabled():break
            self.assertGreater(sim.circuit.time,0,sim.log.toPlainText())
            self.assertFalse(sim.circuit.result.faults,sim.log.toPlainText())
            self.assertGreater(sim.circuit.result.brightness[led.id],.3)
            self.assertTrue(sim.glows[led.id].isVisible())
            sim.close()
            APP.processEvents()


if __name__=="__main__":unittest.main()
