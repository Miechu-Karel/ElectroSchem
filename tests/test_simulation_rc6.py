"""Live controls, real wiring and buzzer synthesis without playing host audio."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.settings import AppSettings
from app.core.project_file import load_project
from app.libraries.built_in import get_definition
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from app.ui.buzzer_audio import BuzzerAudio,ToneStream
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])
USER_PROJECT=Path("C:/Users/miesz/Documents/EtectroSchem Projeky/Testy Przełączników.els")


class Rc6Tests(unittest.TestCase):
    def buzzer(self,name):
        b=Bench(); supply,g=b.power(); buzzer=b.add(name)
        b.connect(supply,0,buzzer,0); b.connect(g,0,buzzer,1)
        return b.circuit(),buzzer

    def test_active_buzzer_emits_tone_not_brightness_and_passive_dc_is_silent(self):
        c,b=self.buzzer("Buzzer Piezoelektryczny Aktywny")
        result=c.step()
        self.assertEqual(result.sounds[b.id]["frequency"],2000)
        self.assertGreater(result.sounds[b.id]["level"],0)
        self.assertNotIn(b.id,result.brightness)
        c,b=self.buzzer("Buzzer Pasywny")
        for _ in range(100): result=c.step(.001)
        self.assertEqual(result.sounds[b.id]["level"],0)

    def test_passive_buzzer_tracks_drive_frequency_and_stops_after_edges_stop(self):
        c,b=self.buzzer("Buzzer Pasywny")
        for i in range(100):
            c.sources[0].parameters["value"]=5 if i%10<5 else 0
            result=c.step(.0001)
        self.assertAlmostEqual(result.sounds[b.id]["frequency"],1000,places=5)
        self.assertGreater(result.sounds[b.id]["level"],0)
        c.sources[0].parameters["value"]=5
        for _ in range(50): result=c.step(.001)
        self.assertEqual(result.sounds[b.id]["level"],0)

    def test_audio_generates_pcm_and_mute_stops_backend(self):
        with patch("app.ui.buzzer_audio.QMediaDevices.defaultAudioOutput") as output, patch("app.ui.buzzer_audio.QAudioSink") as sink:
            output.return_value.isNull.return_value=False
            audio=BuzzerAudio(None)
            audio.update({"test":{"frequency":1000,"level":1}})
            sink.return_value.start.assert_called_once()
            samples=struct.unpack("<128h",audio.stream.readData(256))
            self.assertGreater(max(samples),1000)
            self.assertLessEqual(max(abs(x) for x in samples),32767)
            audio.stop(); self.assertEqual(audio.stream.voices,())
            sink.return_value.stop.assert_called()

    def test_potentiometer_dial_changes_led_current_not_source_document(self):
        b=Bench(); supply,g=b.power(); pot=b.add("Potencjometr Obrotowy","10","kΩ")
        resistor=b.add("Rezystor","330","Ω"); led=b.add("Dioda LED 5mm",color="red")
        for part,(x,y) in zip((supply,g,pot,resistor,led),((100,160),(480,320),(240,160),(360,160),(480,160))):
            part.x,part.y=x,y
        b.connect(supply,0,pot,"1"); b.connect(g,0,pot,"3"); b.connect(pot,"W",resistor,0)
        b.connect(resistor,1,led,0); b.connect(led,1,g,0)
        window=MainWindow(AppSettings(fault_effect="mini"),start_setup=False)
        try:
            from app.core.models import Sheet
            window.project.sheets=[Sheet(components=b.components,wires=b.wires)]
            window._rebuild_tabs(); before=deepcopy(window.project.to_dict())
            window.show_simulation(); sim=window.simulation_window
            dial=sim.controls[pot.id].dial
            self.assertFalse(hasattr(sim.controls[pot.id],"wiper_warning"))
            dial.setValue(200)
            self.assertIn(led.id,sim.circuit.result.brightness,sim.log.toPlainText())
            bright=sim.circuit.result.brightness[led.id]
            dial.setValue(800); dim=sim.circuit.result.brightness[led.id]
            self.assertGreater(bright,dim*2)
            self.assertFalse(sim.circuit.result.faults)
            self.assertEqual(window.project.to_dict(),before)
        finally:
            window._saved_state=deepcopy(window.project.to_dict()); window.close(); window.deleteLater(); APP.processEvents()

    @unittest.skipUnless(USER_PROJECT.is_file(),"User fixture unavailable")
    def test_user_keypad_buttons_switch_leds_and_release_contacts(self):
        window=MainWindow(AppSettings(fault_effect="mini"),start_setup=False)
        try:
            window.project=load_project(USER_PROJECT); window._rebuild_tabs()
            before=deepcopy(window.project.to_dict()); window.show_simulation()
            sim=window.simulation_window
            key=next(d for d in sim.circuit.devices if d.kind=="keypad")
            pot=next(d for d in sim.circuit.devices if d.kind=="potentiometer")
            if hasattr(sim.controls[pot.component.id],"wiper_warning"):
                self.assertIn("W is disconnected",sim.controls[pot.component.id].wiper_warning.text())
            leds={c.reference:c.id for c in window.project.sheets[0].components}
            for index,button in enumerate(sim.controls[key.component.id].keys):
                QTest.mousePress(button,Qt.MouseButton.LeftButton)
                self.assertGreater(sim.circuit.result.brightness[leds[f"LED00{6+index%4}"]],.1)
                QTest.mouseRelease(button,Qt.MouseButton.LeftButton)
                self.assertEqual(key.parameters["sim_key"],"none")
                self.assertLess(sim.circuit.result.brightness[leds[f"LED00{6+index%4}"]],.001)
            self.assertEqual(window.project.to_dict(),before)
        finally:
            window._saved_state=deepcopy(window.project.to_dict()); window.close(); window.deleteLater(); APP.processEvents()

    def test_default_checkboxes_have_distinct_scopes(self):
        b=Bench(); c=b.add("Rezystor","330","Ω")
        dialog=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl")
        self.assertIn("nazwę",dialog.save_default_name.text())
        self.assertIn("wartości",dialog.save_default_values.text())
        dialog.save_default_name.setChecked(True)
        self.assertFalse(dialog.save_default_values.isChecked())
        dialog.close()
