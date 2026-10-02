"""Electrical and interaction regressions for alfa4."""
from copy import deepcopy
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from app.core.models import Project, Sheet
from app.libraries.built_in import get_definition, AVAILABLE_ITEMS
from app.libraries.emulator_catalog import profile_for
from app.core.board_code import ensure_source
from app.core.settings import AppSettings, save_settings, load_settings
from PySide6.QtCore import QSettings
from app.simulation.engine import Circuit
from app.simulation.gpio_script import GpioScript
from test_simulation import component,wire,led_circuit,loop
from test_simulation_alpha2 import Bench

SOURCE=Path(__file__).parent/"fixtures"/"gpio_blink.py"


class Alpha4Tests(unittest.TestCase):
    def test_author_and_effect_preferences_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            store=QSettings(str(Path(folder)/"settings.ini"),QSettings.Format.IniFormat)
            self.assertFalse(load_settings(store).dramatic_faults)
            settings=AppSettings(default_author="Miechu",dramatic_faults=True)
            save_settings(settings,store)
            loaded=load_settings(store)
            self.assertEqual(loaded.default_author,"Miechu")
            self.assertTrue(loaded.dramatic_faults)

    def test_code_creation_all_board_templates_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder, patch("app.core.board_code.appdata_directory",return_value=Path(folder)):
            for d in AVAILABLE_ITEMS:
                if not profile_for(d): continue
                with self.subTest(board=d.name):
                    board=component(d.name,500,500)
                    source=ensure_source(board)
                    self.assertTrue(source.is_file())
                    content=source.read_text(encoding="utf-8")
                    self.assertEqual(ensure_source(board),source)
                    self.assertEqual(source.read_text(encoding="utf-8"),content)
                    circuit=Circuit(Sheet(components=[board]))
                    result=circuit.step(.001)
                    self.assertFalse(result.faults)
                    self.assertTrue(any(state==1 for state in circuit.gpio_states[board.id].values()))

    def test_pi5_gpio12_blinks_with_series_resistor(self):
        b=Bench()
        board=b.add("Raspberry Pi 5",sim_source=str(SOURCE),sim_mode="gpio")
        led=b.add("Dioda LED 5mm",color="red")
        r=b.add("Rezystor","330","Ω")
        b.connect(board,"GPIO12",r,0); b.connect(r,1,led,0); b.connect(led,1,board,"GND")
        c=b.circuit()
        on=c.step(.001)
        self.assertFalse(on.faults)
        self.assertGreater(on.brightness[led.id],.1)
        for _ in range(60): off=c.step(.01)
        self.assertLess(off.brightness[led.id],1e-6)
        for _ in range(50): on=c.step(.01)
        self.assertGreater(on.brightness[led.id],.1)

    def test_pi5_direct_led_reports_overcurrent(self):
        b=Bench(); board=b.add("Raspberry Pi 5",sim_source=str(SOURCE)); led=b.add("Dioda LED 5mm",color="red")
        b.connect(board,"GPIO12",led,0); b.connect(led,1,board,"GND")
        self.assertIn(led.id,b.circuit().step(.001).faults)

    def test_rpi_board_numbering_and_gpio_reads(self):
        d=get_definition(component("Raspberry Pi 5",0,0).library_id)
        s=GpioScript("import RPi.GPIO as GPIO\nfrom time import sleep\nGPIO.setmode(GPIO.BOARD)\nGPIO.setup(32, GPIO.OUT)\nGPIO.output(32, GPIO.HIGH)\nsleep(1)\nGPIO.output(32, GPIO.LOW)",d)
        self.assertEqual(s.advance(.1)["GPIO12"],1)
        self.assertEqual(s.advance(1)["GPIO12"],0)
        with self.assertRaises(ValueError): GpioScript("import os\nos.remove('x')",d)
        s=GpioScript("while True:\n    pass",d)
        with self.assertRaises(ValueError): s.advance(.1)

    def test_logic_inputs_and_output_without_explicit_supply_or_ground(self):
        b=Bench(); a=b.add("Input"); z=b.add("Input"); gate=b.add("Bramka AND"); output=b.add("Output")
        b.connect(a,0,gate,0); b.connect(z,0,gate,1); b.connect(gate,2,output,0)
        c=b.circuit()
        self.assertEqual(c.step().readings[output.id],"LOW (0)")
        for d in c.devices:
            if d.parameters.get("logic_input"): d.parameters["value"]=5
        self.assertEqual(c.step().readings[output.id],"HIGH (1)")

    def test_faulted_island_does_not_prevent_healthy_island_resuming(self):
        healthy,_,_,led=led_circuit()
        source=component("Bateria 9V",1000,1000,"9")
        cap=component("Kondensator Ceramiczny",1400,1000,"10","µF",voltage="6.3 V")
        broken=loop(source,cap)
        combined=Sheet(components=healthy.components+broken.components,wires=healthy.wires+broken.wires)
        c=Circuit(combined)
        self.assertEqual(len(c.parts),2)
        self.assertIn(cap.id,c.step().faults)
        self.assertTrue(c.can_resume)
        c.acknowledge_faults()
        r=c.step()
        self.assertFalse(r.faults)
        self.assertGreater(r.brightness[led.id],.4)

    def test_reference_spaces_migrate_without_rewiring(self):
        board=component("Raspberry Pi 5",500,500)
        board.reference="mc_Raspberry Pi 5___999"
        p=Project(sheets=[Sheet(components=[board])],reference_counters={"mc_Raspberry Pi 5___":1000})
        loaded=Project.from_dict(deepcopy(p.to_dict()))
        self.assertEqual(loaded.sheets[0].components[0].reference,"mc_Raspberry.Pi.5___999")
        self.assertEqual(loaded.sheets[0].components[0].id,board.id)
        self.assertEqual(loaded.allocate_reference(board.library_id),"mc_Raspberry.Pi.5___1001")
