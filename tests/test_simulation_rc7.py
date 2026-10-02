"""Loose items are excluded, not silently converted into valid wired models."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from app.core.models import ComponentInstance
from app.core.project_file import load_project
from app.core.settings import AppSettings
from app.simulation.engine import Circuit,SimulationError
from app.ui.main_window import MainWindow
from app.ui.buzzer_audio import BuzzerAudio
from test_simulation import led_circuit,component,wire

APP=QApplication.instance() or QApplication([])
USER_PROJECT=Path("C:/Users/miesz/Documents/EtectroSchem Projeky/Test Buzzera.els")


class Rc7Tests(unittest.TestCase):
    def test_loose_invalid_resistor_board_and_unknown_do_not_block_led_circuit(self):
        sheet,_,_,led=led_circuit()
        expected=Circuit(sheet).step().brightness[led.id]
        extras=[component("Rezystor",800,500),component("Arduino Uno R3",1000,500),
                ComponentInstance("missing-library-entry",1200,500,reference="loose-unknown")]
        sheet.components.extend(extras); before=deepcopy(sheet)
        circuit=Circuit(sheet,language="pl"); result=circuit.step()
        self.assertEqual(circuit.ignored_components,{c.id for c in extras})
        self.assertEqual(result.brightness[led.id],expected)
        self.assertEqual(set(result.warnings),{c.id for c in extras})
        self.assertEqual(sheet,before)

    def test_wired_invalid_component_is_not_silently_ignored(self):
        sheet,battery,_,_=led_circuit()
        resistor=component("Rezystor",900,500)
        sheet.components.append(resistor); sheet.wires.append(wire(battery,0,resistor,0))
        with self.assertRaises(SimulationError): Circuit(sheet)

    def test_loose_sketch_is_not_compiled_and_stays_visible(self):
        sheet,_,_,led=led_circuit()
        board=component("Arduino Uno R3",840,580,sim_source="missing-unconnected.ino")
        sheet.components.append(board)
        sheet.paper_size="A3"
        window=MainWindow(AppSettings(fault_effect="mini"),start_setup=False)
        try:
            window.project.sheets=[sheet]; window._rebuild_tabs()
            with patch("app.simulation.arduino_compile.ArduinoCompiler.start") as compile_sketch:
                window.show_simulation(); sim=window.simulation_window
                compile_sketch.assert_not_called()
            self.assertIsNotNone(sim.circuit,sim.log.toPlainText())
            self.assertIn(board.id,sim.symbols)
            self.assertIn(board.id,sim.circuit.ignored_components)
            self.assertEqual(sim.symbols[board.id].ink_color,"#74818c")
            sim.single_step(); self.assertGreater(sim.circuit.result.brightness[led.id],.1)
        finally:
            window._saved_state=deepcopy(window.project.to_dict())
            with patch.object(window,"_confirm_discard",return_value=True): window.close()
            window.deleteLater(); APP.processEvents()

    def test_buzzer_volume_is_twice_rc6_level(self):
        with patch("app.ui.buzzer_audio.QMediaDevices.defaultAudioOutput") as output,patch("app.ui.buzzer_audio.QAudioSink") as sink:
            output.return_value.isNull.return_value=False
            audio=BuzzerAudio(None)
            sink.return_value.setVolume.assert_called_once_with(.30)
            audio.stop()

    @unittest.skipUnless(USER_PROJECT.is_file(),"User fixture unavailable")
    def test_supplied_dc_buzzer_test_reports_missing_periodic_drive(self):
        project=load_project(USER_PROJECT); before=deepcopy(project.to_dict())
        circuit=Circuit(project.sheets[0],language="pl")
        if any(source.kind=="ac" for source in circuit.sources):
            self.skipTest("User fixture now contains AC, not the original DC-only circuit")
        switch=next(d for d in circuit.devices if d.kind=="switch")
        buzzer=next(d for d in circuit.devices if d.kind=="buzzer")
        self.assertFalse(switch.closed)
        switch.closed=True
        for _ in range(50): result=circuit.step(.001)
        self.assertEqual(result.sounds[buzzer.component.id]["level"],0)
        self.assertIn("napięcie stałe",result.warnings[buzzer.component.id])
        self.assertEqual(project.to_dict(),before)

    @unittest.skipUnless(USER_PROJECT.is_file(),"User fixture unavailable")
    def test_supplied_buzzer_responds_to_ac_drive_in_memory(self):
        project=load_project(USER_PROJECT); circuit=Circuit(project.sheets[0])
        switch=next(d for d in circuit.devices if d.kind=="switch"); switch.closed=True
        source=circuit.sources[0]; source.kind="ac"
        source.parameters.update(value=3.5,sim_frequency=2000)
        buzzer=next(d for d in circuit.devices if d.kind=="buzzer")
        for _ in range(1000): result=circuit.step(.000005)
        self.assertFalse(result.faults)
        self.assertAlmostEqual(result.sounds[buzzer.component.id]["frequency"],2000,places=4)
        self.assertGreater(result.sounds[buzzer.component.id]["level"],.1)
