"""Held inputs, powered connectors, DAC resolutions, knowledge and live pacing."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
from time import perf_counter, perf_counter_ns
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QPoint, QEventLoop, QTimer
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.models import Project, Sheet
from app.core.settings import AppSettings
from app.core.project_file import load_project
from app.ui.main_window import MainWindow
from app.ui.ai_preview import AiPreview
from app.services.design_knowledge import knowledge, RULE_GROUPS, RECIPES
from app.libraries.built_in import get_definition
from app.libraries.menu_groups import subgroup
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


class ElectricalTests(unittest.TestCase):
    def test_gpio_pullup_and_pad_reaches_real_python_input(self):
        b=Bench(); board=b.add("Raspberry Pi 5", sim_mode="gpio", sim_source=str(Path(__file__).parent/"fixtures"/"pad_gpio_read.py"))
        pad=b.add("Joystick Iduino ST1079",sim_switch_mode="contact")
        b.connect(board,"3V3",pad,"VCC"); b.connect(board,"GND",pad,"GND"); b.connect(board,"GPIO17",pad,"SW")
        circuit=b.circuit()
        for _ in range(10): result=circuit.step(.001)
        self.assertFalse(result.faults)
        script=next(part.scripts[board.id] for part in circuit.parts if board.id in part.scripts)
        self.assertEqual(script.states["GPIO17"],3)
        self.assertEqual(script.serial.strip().splitlines()[-1],"1")
        device=next(d for d in circuit.devices if d.component.id==pad.id); device.closed=True
        for _ in range(10): result=circuit.step(.001)
        self.assertEqual(script.serial.strip().splitlines()[-1],"0")
        device.closed=False
        for _ in range(10): result=circuit.step(.001)
        self.assertEqual(script.serial.strip().splitlines()[-1],"1")

    def test_all_ports_deliver_external_power_and_usb_c_contacts_are_joined(self):
        for name in ("Port USB A","Port USB B","Port USB Mini-B","Port USB Micro-B","Port USB C","Port Lightning"):
            with self.subTest(port=name):
                b=Bench(); port=b.add(name,sim_power="true",sim_voltage="5 V"); r=b.add("Rezystor","1","kΩ")
                positive="POWER" if name=="Port Lightning" else "VBUS.A4" if name=="Port USB C" else "VBUS"
                ground="GND.B12" if name=="Port USB C" else "GND"
                source=b.add("Kostka zasilająca USB","5","V")
                b.connect(source,0,port,positive); b.connect(source,1,port,ground)
                b.connect(port,positive,r,0); b.connect(port,ground,r,1)
                c=b.circuit(); result=c.step(); self.assertFalse(result.faults)
                self.assertAlmostEqual(result.currents[r.id],.005,places=7)
                if name=="Port USB C":
                    d=get_definition(port.library_id)
                    nodes={p.name:c.netlist.pins[port.id,i] for i,p in enumerate(d.pins)}
                    self.assertEqual(len({v for k,v in nodes.items() if k.startswith("VBUS")}),1)
                    self.assertEqual(len({v for k,v in nodes.items() if k.startswith("GND")}),1)

    def test_power_brick_current_limit_fault(self):
        b=Bench(); port=b.add("Port USB A",sim_power="true",sim_max_current="1 mA"); r=b.add("Rezystor","1","kΩ")
        b.connect(port,"VBUS",r,0); b.connect(port,"GND",r,1)
        source=b.add("Kostka zasilająca USB","5","V",sim_max_current="1 mA")
        b.connect(source,0,port,"VBUS"); b.connect(source,1,port,"GND")
        self.assertIn(source.id,b.circuit().step().faults)

    def test_dac_resolutions_half_scale(self):
        for bits in (8,10,12):
            b=Bench(); s,g=b.power(); dac=b.add(f"Przetwornik DAC {bits}-bit"); r=b.add("Rezystor","10","kΩ")
            for pin in ("VCC","VREF",f"D{bits-1}"): b.connect(s,0,dac,pin)
            for pin in ("GND",*(f"D{i}" for i in range(bits-1))): b.connect(g,0,dac,pin)
            b.connect(dac,"OUT",r,0); b.connect(r,1,g,0)
            result=b.circuit().step(); self.assertFalse(result.faults)
            self.assertAlmostEqual(result.currents[r.id],5*(1<<(bits-1))/((1<<bits)-1)/10025,places=7)
            self.assertEqual(subgroup(get_definition(dac.library_id))[1],"Przetworniki cyfrowo-analogowe")

    def test_bundled_knowledge_has_conditions_and_relevant_recipes(self):
        self.assertGreaterEqual(sum(map(len,RULE_GROUPS.values())),60)
        self.assertGreaterEqual(len(RECIPES),20)
        selected=knowledge("pad joystick i DAC")
        self.assertIn("Joystick button",[r["name"] for r in selected["selected_recipes"]])
        self.assertIn("Parallel DAC",[r["name"] for r in selected["selected_recipes"]])

    def test_preview_click_opens_inspection_not_edits(self):
        preview=AiPreview(); preview.image=QImage(30,30,QImage.Format.Format_ARGB32); preview.language="pl"
        with patch.object(preview,"inspect") as inspect:
            QTest.mouseClick(preview,Qt.MouseButton.LeftButton); inspect.assert_called_once_with("pl")
        preview.deleteLater()


class LiveTests(unittest.TestCase):
    def setUp(self): self.window=MainWindow(AppSettings(fault_effect="mini",window_mode="windowed"),start_setup=False)
    def tearDown(self):
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()
    def sandbox(self,b):
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        self.window._rebuild_tabs(); self.window.show_simulation()
        sim=self.window.simulation_window; sim.buzzer_sound_button.setChecked(False)
        return sim

    def test_pad_holds_low_until_actual_mouse_release_without_external_pullup(self):
        b=Bench(); s,g=b.power(); pad=b.add("Joystick Iduino ST1079",sim_switch_mode="contact")
        b.connect(s,0,pad,"VCC"); b.connect(g,0,pad,"GND")
        sim=self.sandbox(b); sim.single_step(); before=deepcopy(self.window.project.to_dict())
        sw=sim.circuit.netlist.pins[pad.id,4]; control=sim.controls[pad.id].joystick
        self.assertGreater(sim.circuit.result.voltages[sw],4.9)
        QTest.mousePress(control,Qt.MouseButton.RightButton,pos=QPoint(75,75)); QTest.qWait(350)
        self.assertTrue(control.pressed); self.assertLess(sim.circuit.result.voltages[sw],.1)
        QTest.mouseRelease(control,Qt.MouseButton.RightButton,pos=QPoint(75,75))
        self.assertFalse(control.pressed); self.assertGreater(sim.circuit.result.voltages[sw],4.9)
        self.assertEqual(self.window.project.to_dict(),before)

    def test_tact_scene_press_holds_until_release(self):
        b=Bench(); s,g=b.power(); tact=b.add("Przycisk Tact Switch"); r=b.add("Rezystor","1","kΩ")
        for c,pos in zip((s,g,tact,r),((100,200),(500,400),(300,200),(500,200))): c.x,c.y=pos
        b.connect(s,0,tact,0); b.connect(tact,1,r,0); b.connect(r,1,g,0)
        sim=self.sandbox(b); APP.processEvents()
        d=next(d for d in sim.circuit.devices if d.component.id==tact.id)
        point=sim.view.mapFromScene(sim.symbols[tact.id].scenePos())
        QTest.mousePress(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=point); QTest.qWait(350)
        self.assertTrue(d.closed)
        QTest.mouseRelease(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        self.assertFalse(d.closed)

    def test_live_100_percent_with_tiny_initial_step(self):
        b=Bench(); s,g=b.power(); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,r,0); b.connect(g,0,r,1)
        sim=self.sandbox(b); sim.dt.setValue(.001); sim.time_scale.setValue(100)
        loop=QEventLoop(); QTimer.singleShot(2000,loop.quit)
        started=perf_counter(); sim.run(); loop.exec(); elapsed=(perf_counter_ns()-sim.wall_start_ns)/1e9; sim.pause()
        ratio=sim.circuit.time/elapsed
        print(f"Pacing small circuit: real={elapsed:.3f}s, simulated={sim.circuit.time:.3f}s, actual={ratio*100:.2f}%, step={sim.dt.value():.4g}ms")
        self.assertGreater(ratio,.94,(ratio,sim.dt.value()))
        self.assertLess(ratio,1.03)

    @unittest.skipUnless(Path("C:/Users/miesz/Documents/EtectroSchem Projeky/Migające LEDy.els").is_file(),"User oscillator fixture unavailable")
    def test_user_blinking_leds_real_time(self):
        self.window.project=load_project("C:/Users/miesz/Documents/EtectroSchem Projeky/Migające LEDy.els")
        self.window._rebuild_tabs(); self.window.show_simulation(); sim=self.window.simulation_window
        sim.buzzer_sound_button.setChecked(False); sim.dt.setValue(.1); sim.time_scale.setValue(100)
        loop=QEventLoop(); QTimer.singleShot(6000,loop.quit)
        started=perf_counter(); sim.run(); loop.exec(); elapsed=(perf_counter_ns()-sim.wall_start_ns)/1e9; sim.pause()
        print(f"Pacing user LED circuit: real={elapsed:.3f}s, simulated={sim.circuit.time:.3f}s, actual={sim.circuit.time/elapsed*100:.2f}%, step={sim.dt.value():.4g}ms")
        self.assertGreater(sim.circuit.time/elapsed,.98,(sim.circuit.time,elapsed,sim.dt.value(),sim.log.toPlainText()))
