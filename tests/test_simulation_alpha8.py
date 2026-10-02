"""Alfa8 numerical models, localization, window states and opt-in effects."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch,MagicMock
from PySide6.QtCore import Qt,QSettings,QPoint
from PySide6.QtWidgets import QApplication,QPushButton,QMenu,QWidget
from PySide6.QtTest import QTest
from app.core.models import Sheet
from app.core.settings import AppSettings,save_settings,load_settings
from app.core.messages import localize
from app.libraries.built_in import AVAILABLE_ITEMS,get_definition
from app.libraries.simulation_catalog import behavior_for
from app.libraries.peripheral_models import ENVELOPE_NAMES
from app.simulation.engine import Circuit,SimulationError
from app.simulation.peripherals import i2c_write,lcd_byte
from app.ui.main_window import MainWindow
from app.ui.effects import ClickFeedback,FLASH_SECONDS,RING_TAIL_SECONDS
from app.ui.window_mode import show_window
from test_simulation_alpha2 import Bench
from test_rc5 import placement_actions

APP=QApplication.instance() or QApplication([])


class Alpha8Models(unittest.TestCase):
    def test_catalog_models_and_excluded_inventory_items(self):
        self.assertTrue(all(behavior_for(d) for d in AVAILABLE_ITEMS))
        self.assertFalse(any("DSI" in d.name or "Camera Module" in d.name for d in AVAILABLE_ITEMS))
        for name in ENVELOPE_NAMES:
            d=next(d for d in AVAILABLE_ITEMS if d.name==name)
            self.assertIn("ONLY",behavior_for(d).note_en)

    def test_all_envelopes_draw_power_without_mutating_document(self):
        for name in ENVELOPE_NAMES:
            with self.subTest(name=name):
                b=Bench(); supply,g=b.power(); item=b.add(name,sim_nominal_voltage="5 V",sim_load_current="10 mA")
                pins=[p.name for p in get_definition(item.library_id).pins]
                hi=next(k for k in ("VCC","VDD","5V","3V3","VCC_IN","IN+") if k in pins)
                lo=next(k for k in ("GND","VSS","GND_IN","IN−") if k in pins)
                b.connect(supply,0,item,hi); b.connect(g,0,item,lo)
                original=deepcopy(item); circuit=b.circuit(); r=circuit.step()
                self.assertFalse(r.faults); self.assertAlmostEqual(-r.currents[supply.id],.01,places=6)
                self.assertIn("Supply-only",r.readings[item.id]); self.assertEqual(item,original)
                device=next(d for d in circuit.devices if d.component.id==item.id)
                device.parameters["sim_nominal_voltage"]=2
                self.assertIn(item.id,circuit.step().faults)

    def test_joystick_and_receiver_click_states(self):
        for name,pin in (("Joystick Iduino ST1079","SW"),("Odbiornik IR Grove 38 kHz","SIG")):
            b=Bench(); supply,g=b.power(); item=b.add(name,sim_x="0.25",sim_y="0.75")
            b.connect(supply,0,item,"VCC"); b.connect(g,0,item,"GND")
            pull=b.add("Rezystor","10","kΩ"); b.connect(pull,0,supply,0); b.connect(pull,1,item,pin)
            circuit=b.circuit(); r=circuit.step(); definition=get_definition(item.library_id)
            def node(label): return circuit.netlist.pins[item.id,next(i for i,p in enumerate(definition.pins) if p.name==label)]
            self.assertGreater(r.voltages[node(pin)],4.9)
            if "Joystick" in name:
                self.assertAlmostEqual(r.voltages[node("VRx")],1.25,places=5)
                self.assertAlmostEqual(r.voltages[node("VRy")],3.75,places=5)
            next(d for d in circuit.devices if d.component.id==item.id).closed=True
            self.assertLess(circuit.step().voltages[node(pin)],.02)

    def test_rgb_common_anode(self):
        b=Bench(); supply,g=b.power(); led=b.add("Dioda RGB wspólna anoda")
        b.connect(supply,0,led,"A"); b.connect(supply,0,led,"G"); b.connect(supply,0,led,"B")
        load=b.add("Rezystor","330"); b.connect(load,0,led,"R"); b.connect(load,1,g,0)
        r=b.circuit().step(); self.assertGreater(r.rgb[led.id][0],.4); self.assertEqual(r.rgb[led.id][1:],(0,0))

    def test_gpio_manual_outputs_have_real_supply_load(self):
        b=Bench(); supply,g=b.power(); item=b.add("Ekspander Portów MCP23008",sim_output_mask="1",sim_gpio_mask="1")
        b.connect(supply,0,item,"VDD"); b.connect(g,0,item,"VSS")
        load=b.add("Rezystor","1","kΩ"); b.connect(item,"GP0",load,0); b.connect(load,1,g,0)
        c=b.circuit(); r=c.step(); self.assertAlmostEqual(r.currents[load.id],5/1025,places=6)
        next(d for d in c.devices if d.component.id==item.id).parameters["sim_gpio_mask"]=0
        self.assertLess(c.step().currents[load.id],1e-8)

    def test_4n35_base_shunt_reduces_optical_gain(self):
        currents=[]
        for shunt in (False,True):
            b=Bench(); supply,g=b.power(); opto=b.add("Transoptor 4N35")
            led_r=b.add("Rezystor","1","kΩ"); load=b.add("Rezystor","1","kΩ")
            for a,ap,z,zp in ((supply,0,led_r,0),(led_r,1,opto,"A"),(opto,"K",g,0),(supply,0,load,0),(load,1,opto,"C"),(opto,"E",g,0)): b.connect(a,ap,z,zp)
            if shunt: b.connect(opto,"B",g,0)
            currents.append(b.circuit().step().currents[load.id])
        self.assertGreater(currents[0],.002); self.assertLess(currents[1],currents[0]/10)

    def test_i2c_write_ack_address_and_lcd_text(self):
        bus={}; received=[]
        def clock(scl,sda):
            nonlocal bus
            bus,value=i2c_write(bus,bool(scl),bool(sda),0x27)
            if value is not None: received.append(value)
        def send(value):
            for bit in range(7,-1,-1):
                state=(value>>bit)&1; clock(0,state); clock(1,state); clock(0,state)
            ack=bus.get("ack",False); clock(1,not ack); clock(0,not ack)
            return ack
        clock(1,1); clock(1,0)
        self.assertTrue(send(0x4e)); self.assertTrue(send(0x38)); self.assertEqual(received,[0x38])
        clock(0,0); clock(1,0); clock(1,1); clock(1,0)
        self.assertFalse(send(0x50)); self.assertFalse(send(0xff)); self.assertEqual(received,[0x38])
        lcd={}
        def nibble(value,rs=0):
            nonlocal lcd
            lcd=lcd_byte(lcd,(value<<4)|rs|12); lcd=lcd_byte(lcd,(value<<4)|rs|8)
        def byte(value,rs=0): nibble(value>>4,rs); nibble(value&15,rs)
        nibble(3); nibble(3); nibble(2); byte(0x28); byte(0x0c); byte(1); byte(0x80)
        for character in "ElectroSchem": byte(ord(character),1)
        byte(0xc0); byte(ord("2"),1)
        self.assertTrue(lcd["display"]); self.assertEqual(lcd["cells"][:12],"ElectroSchem")
        self.assertEqual(lcd["cells"][16],"2")

    def test_supply_defaults_and_overload(self):
        b=Bench(); supply=b.add("Zasilacz Raspberry Pi USB-C 27 W"); resistor=b.add("Rezystor","0.5",sim_max_power="100 W")
        b.connect(supply,0,resistor,0); b.connect(supply,1,resistor,1)
        c=b.circuit(); r=c.step(); self.assertIn(supply.id,r.faults)
        self.assertAlmostEqual(abs(r.currents[supply.id]),10.2,places=5)

    def test_lcd_receives_text_over_actual_circuit_nodes(self):
        b=Bench(); supply,g=b.power(); lcd=b.add("Wyświetlacz LCD 16x2 I2C LCM1602")
        clock=b.add("Bateria 9V","5"); data=b.add("Bateria 9V","5"); pull=b.add("Rezystor","1","kΩ")
        for a,ap,z,zp in ((supply,0,lcd,"VCC"),(g,0,lcd,"GND"),(clock,0,lcd,"SCL"),(clock,1,g,0),(data,0,pull,0),(pull,1,lcd,"SDA"),(data,1,g,0)): b.connect(a,ap,z,zp)
        circuit=b.circuit(); sources={d.component.id:d for d in circuit.sources}
        def drive(scl,sda):
            sources[clock.id].parameters["value"]=5*bool(scl); sources[data.id].parameters["value"]=5*bool(sda)
            result=circuit.step(); self.assertFalse(result.faults)
            return result
        def send(value):
            for bit in range(7,-1,-1):
                state=(value>>bit)&1; drive(0,state); drive(1,state); drive(0,state)
            result=drive(0,1); drive(1,1); drive(0,1)
            pin=next(i for i,p in enumerate(get_definition(lcd.library_id).pins) if p.name=="SDA")
            self.assertLess(result.voltages[circuit.netlist.pins[lcd.id,pin]],.1)
        def port(value):
            drive(1,1); drive(1,0); send(0x4e); send(value)
            drive(0,0); drive(1,0); drive(1,1)
        def nibble(value,rs=0): port((value<<4)|rs|12); port((value<<4)|rs|8)
        def byte(value,rs=0): nibble(value>>4,rs); nibble(value&15,rs)
        nibble(3); nibble(3); nibble(2); byte(0x28); byte(0x0c); byte(1)
        byte(ord("O"),1); byte(ord("K"),1)
        self.assertTrue(circuit.result.readings[lcd.id].startswith("OK"))

    def test_single_language_errors(self):
        for lang,expected,absent in (("pl","Arkusz jest pusty","The sheet"),("en","The sheet is empty","Arkusz")):
            with self.assertRaises(SimulationError) as error: Circuit(Sheet(),language=lang)
            self.assertIn(expected,str(error.exception)); self.assertNotIn(absent,str(error.exception))
        message="Component does not fit this sheet; choose a larger paper size. / Element nie mieści się na arkuszu; wybierz większy format."
        self.assertEqual(localize(message,"pl"),message.split(" / ")[1]); self.assertEqual(localize(message,"en"),message.split(" / ")[0])


class Alpha8Ui(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language="pl",window_mode="windowed"),start_setup=False)
        self.window.show(); APP.processEvents()
    def tearDown(self):
        self.window._saved_state=deepcopy(self.window.project.to_dict())
        self.window.close(); self.window.deleteLater(); APP.processEvents()

    def test_live_language_roundtrip_and_manual(self):
        self.window.show_simulation(); sim=self.window.simulation_window
        self.assertIn("Arkusz jest pusty",sim.log.toPlainText()); self.assertNotIn("The sheet",sim.log.toPlainText())
        for language in ("en","pl","en"):
            self.window.settings.language=language; sim.refresh_language(); self.window._translate_ui()
            text=sim.log.toPlainText()
            self.assertIn("Arkusz jest pusty" if language=="pl" else "The sheet is empty",text)
            self.assertNotIn("Start blocked" if language=="pl" else "Start zablokowany",text)
        self.assertEqual(self.window.help_action.text(),"Usage Instructions")

    def test_disabled_click_flashes_without_invoking_action(self):
        button=QPushButton("Disabled",self.window); button.setGeometry(130,130,120,40); button.show(); button.setEnabled(False)
        callback=MagicMock(); button.clicked.connect(callback); APP.processEvents()
        QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        self.assertTrue(button.findChildren(ClickFeedback)); callback.assert_not_called(); self.assertFalse(button.isEnabled())

    def test_secondary_entries_are_enabled_and_marked(self):
        actions=[]
        for index in range(5):
            menu=QMenu(self.window); self.window._populate_library_menu(menu,index,QPoint(200,200))
            actions.extend(placement_actions(menu))
        led=next(d for d in AVAILABLE_ITEMS if d.name=="Dioda LED 3mm")
        copies=[a for a in actions if a.data()==led.id]
        self.assertEqual(len(copies),2); self.assertEqual(sum(bool(a.property("secondaryEntry")) for a in copies),1)
        self.assertTrue(all(a.isEnabled() for a in copies))

    def test_window_modes_and_preference_roundtrip(self):
        self.assertEqual(AppSettings().window_mode,"maximized")
        with tempfile.TemporaryDirectory() as folder:
            store=QSettings(str(Path(folder)/"prefs.ini"),QSettings.Format.IniFormat)
            for mode in ("windowed","maximized","fullscreen"):
                settings=AppSettings(window_mode=mode); save_settings(settings,store)
                self.assertEqual(load_settings(store).window_mode,mode)
                show_window(self.window,settings); APP.processEvents()
                self.assertEqual(self.window.isFullScreen(),mode=="fullscreen")
                if mode!="fullscreen": self.assertEqual(self.window.isMaximized(),mode=="maximized")

    def test_flash_bounds_and_ring_duration_without_playback(self):
        self.window.show_simulation(); sim=self.window.simulation_window
        sim.flash_overlay.set_opacity(.8)
        self.assertEqual(sim.flash_overlay.geometry(),sim.rect())
        self.assertTrue(sim.flash_overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        with patch("app.ui.fault_sound.QAudioSink") as sink:
            from app.ui.fault_sound import FaultSound
            sound=FaultSound(sim)
            self.assertEqual(sound.buffer.size(),int(22050*(FLASH_SECONDS+RING_TAIL_SECONDS))*2)
            sink.return_value.start.assert_not_called()
            sim.fault_sound=sound
            QTest.keyClick(sim,Qt.Key.Key_Escape)
            self.assertEqual(sim.flash_overlay.opacity,0); sink.return_value.stop.assert_called()


if __name__=="__main__": unittest.main()
