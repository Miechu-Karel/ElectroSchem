"""Real sketch compilation, wired Python LCD and privacy-safe camera tests."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QEventLoop,QTimer,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QApplication,QMessageBox
from app.core.models import Sheet
from app.core.project_file import load_project
from app.libraries.built_in import get_definition
from app.simulation.python_board import PythonBoard
from app.simulation.engine import Circuit
from app.simulation.arduino_compile import ArduinoCompiler,compiler_path
from app.simulation.emulator_process import ENGINE_DIR
from app.ui.camera_preview import CameraPreview
from app.ui.simulation_window import LiveSymbol
from app.ui.main_window import MainWindow
from app.core.settings import AppSettings
from copy import deepcopy
from time import monotonic
from test_simulation import component
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])
ROOT=Path(__file__).resolve().parents[1]
USER_PROJECT=Path('C:/Users/miesz/Documents/EtectroSchem Projeky/Przykładowy LCD.els')


def compile_example(board_name,source):
    board=component(board_name,0,0,sim_source=str(source),sim_mode="arduino")
    compiler=ArduinoCompiler(); loop=QEventLoop(); answer={}
    compiler.finished.connect(lambda path:(answer.update(path=path),loop.quit()))
    compiler.failed.connect(lambda message:(answer.update(error=message),loop.quit()))
    QTimer.singleShot(180000,loop.quit)
    compiler.start(board,get_definition(board.library_id))
    if not answer: loop.exec()
    compiler.stop()
    if "path" not in answer: raise AssertionError(answer.get("error","Compilation timed out"))
    return answer["path"]


class PythonApiTests(unittest.TestCase):
    def test_functions_keywords_loops_and_simulated_time(self):
        definition=get_definition(component("Raspberry Pi 5",0,0).library_id)
        script=PythonBoard("import RPi.GPIO as GPIO\nimport time\nGPIO.setmode(GPIO.BCM)\nGPIO.setup(12, GPIO.OUT, initial=GPIO.LOW)\ndef blink(pin, delay=0.5):\n    for state in [1, 0]:\n        GPIO.output(pin, state)\n        time.sleep(delay)\nwhile True:\n    blink(12, delay=0.5)\n",definition)
        self.assertEqual(script.advance(.1)["GPIO12"],1)
        self.assertEqual(script.advance(.5)["GPIO12"],0)
        self.assertEqual(script.advance(.5)["GPIO12"],1)

    def test_local_helper_modules_without_host_imports(self):
        definition=get_definition(component("Raspberry Pi 5",0,0).library_id)
        with tempfile.TemporaryDirectory() as directory:
            helper=Path(directory)/"helper.py"; helper.write_text("def twice(value):\n    return value * 2\n",encoding="utf-8")
            script=PythonBoard("from helper import twice\nprint(twice(21))\n",definition,Path(directory)/"main.py")
            script.advance(.1); self.assertEqual(script.serial,"42\n")
        for source in ("import os", "import subprocess", "while True:\n    pass", "x = bytes(999999999)"):
            with self.subTest(source=source),self.assertRaises(ValueError): PythonBoard(source,definition).advance(.1)

    def lcd_circuit(self,source,swapped=False,address="39"):
        bench=Bench(); pi=bench.add("Raspberry Pi 5",sim_source=str(source),sim_mode="gpio")
        lcd=bench.add("Wyświetlacz LCD 16x2 I2C LCM1602",sim_address=address)
        for a,z in (("5V","VCC"),("GND","GND"),("GPIO2/SDA1","SCL" if swapped else "SDA"),("GPIO3/SCL1","SDA" if swapped else "SCL")):
            bench.connect(pi,a,lcd,z)
        return bench.circuit(),lcd

    def test_real_rplcd_api_reaches_wired_lcd(self):
        circuit,lcd=self.lcd_circuit(ROOT/"examples/lcd_raspberry.py")
        result=circuit.step(.001)
        self.assertTrue(result.readings[lcd.id].startswith("ElectroSchem")); self.assertIn("LCD dziala!",result.readings[lcd.id])
        self.assertTrue(result.displays[lcd.id]["backlight"]); self.assertFalse(result.faults)

    def test_bad_wiring_and_wrong_address_do_not_fake_lcd_success(self):
        for swapped,address in ((True,"39"),(False,"38")):
            circuit,lcd=self.lcd_circuit(ROOT/"examples/lcd_raspberry.py",swapped,address)
            with self.assertRaises(ValueError): circuit.step(.001)

    @unittest.skipUnless(USER_PROJECT.is_file(),"User's optional LCD project is unavailable")
    def test_users_project_wires_and_new_lcd_code(self):
        project=load_project(USER_PROJECT)
        for c in project.sheets[0].components:
            if "raspberry" in c.library_id: c.properties.update(sim_source=str(ROOT/"examples/lcd_raspberry.py"),sim_mode="gpio")
        result=Circuit(project.sheets[0]).step(.001)
        self.assertTrue(any("LCD dziala!" in text for text in result.readings.values())); self.assertFalse(result.faults)

    def test_lcd_draws_a_real_visible_display(self):
        c=component("Wyświetlacz LCD 16x2 I2C LCM1602",0,0)
        item=LiveSymbol(c)
        def render():
            image=QImage(300,300,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.black)
            painter=QPainter(image); painter.translate(150,150); item.paint(painter,None); painter.end(); return image
        original=render(); item.display_state={"cells":"ElectroSchem    LCD dziala!     ","backlight":True,"powered":True}
        self.assertNotEqual(original,render())

    def test_lcd_has_large_blue_panel_and_last_column_is_visible(self):
        from dataclasses import asdict
        from PySide6.QtGui import QColor
        c=component("Wyświetlacz LCD 16x2 I2C LCM1602",0,0)
        item=LiveSymbol(c)
        before=asdict(c)
        def render(cells):
            item.display_state={"cells":cells,"backlight":True,"powered":True}
            image=QImage(600,500,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.black)
            painter=QPainter(image); painter.translate(300,300); item.paint(painter,None); painter.end()
            return image
        blank=render(" "*32); last=render(" "*15+"W"+" "*15+"W")
        self.assertNotEqual(blank,last)
        panel=item.lcd_rect()
        self.assertEqual(blank.pixelColor(int(panel.left()+315),int(panel.top()+315)),QColor("#164fc9"))
        self.assertGreaterEqual(item.boundingRect().width(),320)
        self.assertTrue(item.boundingRect().contains(panel))
        self.assertEqual(asdict(c),before)

    def test_disconnected_pi_pins_do_not_expand_solver_matrix(self):
        circuit,lcd=self.lcd_circuit(ROOT/"examples/lcd_raspberry.py")
        self.assertLessEqual(max(len(part.index) for part in circuit.parts),8)
        result=circuit.step(.0001)
        self.assertFalse(result.faults)
        self.assertEqual(len(result.displays[lcd.id]["cells"]),32)


@unittest.skipUnless(compiler_path() and shutil.which("node"),"Arduino CLI and Node are required")
class ArduinoIntegrationTests(unittest.TestCase):
    def test_simulation_automatically_compiles_ino_and_powers_board(self):
        bench=Bench(); board=bench.add("Arduino Uno R3",sim_source=str(ROOT/"examples/arduino_blink/arduino_blink.ino"),sim_mode="arduino")
        resistor=bench.add("Rezystor","330","Ω"); led=bench.add("Dioda LED 5mm",color="red")
        bench.connect(board,"D13/SCK",resistor,0); bench.connect(resistor,1,led,0); bench.connect(led,1,board,"GND")
        window=MainWindow(AppSettings(window_mode="windowed",fault_effect="mini"),start_setup=False)
        try:
            window.project.sheets=[Sheet(components=bench.components,wires=bench.wires)]
            window._rebuild_tabs(); window.show_simulation(); sim=window.simulation_window
            limit=monotonic()+30
            while sim.circuit is None and sim.compile_queue and monotonic()<limit: APP.processEvents()
            self.assertIsNotNone(sim.circuit,sim.log.toPlainText())
            self.assertEqual(board.properties["sim_usb_power"],"true")
            for _ in range(20):
                before=sim.circuit.time; sim.single_step(); limit=monotonic()+5
                while sim.circuit.time==before and monotonic()<limit: APP.processEvents()
                if sim.circuit.result.brightness.get(led.id,0)>.1: break
            self.assertGreater(sim.circuit.result.brightness.get(led.id,0),.1,sim.log.toPlainText())
            self.assertFalse(sim.circuit.result.faults)
        finally:
            window._sync_positions(); window._saved_state=deepcopy(window.project.to_dict()); window.close(); window.deleteLater(); APP.processEvents()

    def run_firmware(self,firmware,steps,addresses=()):
        commands=[{"op":"init","engine":"avr8js","firmware":firmware}]
        commands.extend({"op":"step","seconds":.01,"inputs":{},"i2c_addresses":list(addresses)} for _ in range(steps))
        result=subprocess.run([shutil.which("node"),str(ENGINE_DIR/"bridge.cjs")],input="\n".join(map(json.dumps,commands))+"\n",text=True,capture_output=True,timeout=30,check=True)
        replies=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(all(reply["ok"] for reply in replies),replies)
        return replies

    def test_real_ino_compiles_and_blinks_on_uno_and_nano(self):
        for board in ("Arduino Uno R3","Arduino Nano"):
            firmware=compile_example(board,ROOT/"examples/arduino_blink/arduino_blink.ino")
            replies=self.run_firmware(firmware,110)
            self.assertEqual(replies[2]["gpio"]["D13"],1)
            self.assertEqual(replies[61]["gpio"]["D13"],0)
            self.assertEqual(replies[-1]["gpio"]["D13"],1)

    def test_real_wire_firmware_writes_into_wired_circuit(self):
        firmware=compile_example("Arduino Uno R3",ROOT/"examples/arduino_lcd/arduino_lcd.ino")
        bench=Bench(); supply,ground=bench.power(); board=bench.add("Arduino Uno R3",sim_firmware=firmware,sim_mode="firmware")
        lcd=bench.add("Wyświetlacz LCD 16x2 I2C LCM1602")
        for a,ap,z,zp in ((supply,0,board,"5V"),(ground,0,board,"GND"),(supply,0,lcd,"VCC"),(ground,0,lcd,"GND"),(board,"A4/SDA",lcd,"SDA"),(board,"A5/SCL",lcd,"SCL")): bench.connect(a,ap,z,zp)
        circuit=bench.circuit(); device=next(d for d in circuit.devices if d.component.id==board.id)
        self.assertEqual(circuit.i2c_addresses(device),[0x27])
        for reply in self.run_firmware(firmware,25,[0x27])[1:]:
            circuit.gpio_states[board.id]=reply["gpio"]
            circuit.receive_i2c(device,reply.get("i2c",[])); result=circuit.step(.01)
            self.assertFalse(result.faults)
        self.assertTrue(result.readings[lcd.id].startswith("Arduino LCD"))


class CameraPrivacyTests(unittest.TestCase):
    def test_denied_consent_never_starts_camera(self):
        dialog=CameraPreview(language="pl")
        with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.No),patch.object(dialog,"start_authorized") as start:
            dialog.request_start(); start.assert_not_called(); self.assertFalse(dialog.consent)
        dialog.close(); dialog.deleteLater()

    def test_consent_is_session_scoped_and_stop_revokes_it(self):
        dialog=CameraPreview()
        with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.Yes),patch.object(dialog,"start_authorized") as start:
            dialog.request_start(); start.assert_called_once(); self.assertTrue(dialog.consent)
        dialog.stop_button.click(); self.assertFalse(dialog.consent); self.assertIsNone(dialog.camera)
        dialog.close(); dialog.deleteLater()


if __name__=="__main__": unittest.main()
