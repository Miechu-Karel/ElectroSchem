"""Offline checks of command proposals, both providers and alpha models."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from copy import deepcopy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.models import Project, Sheet
from app.core.settings import AppSettings
from app.core.editor_commands import CommandSession, execute_batch, parse_commands
from app.libraries.built_in import BUILT_IN_ITEMS, AVAILABLE_ITEMS, get_definition
from app.services.assistant_client import AssistantClient, decode_answer
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from test_simulation_alpha2 import Bench
from test_ai_settings import FakeReply

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)
RES = next(d for d in BUILT_IN_ITEMS if d.name == "Rezystor")
def add_command(key="R1", x=200, y=200):
    return f'ADD_COMPONENT type={RES.id} id={key} x={x} y={y} value=330 unit=Ω'


class CommandTests(unittest.TestCase):
    def test_proposal_edit_reject_accept_and_conflict(self):
        project=Project(sheets=[Sheet()]); before=deepcopy(project.to_dict())
        session=CommandSession(project,0); session.execute(add_command())
        session.execute('SET_PROPERTY id=R1 property=value value=220\nMOVE_COMPONENT id=R1 x=300 y=300')
        self.assertEqual(project.to_dict(),before)
        self.assertEqual(session.accept(project).sheets[0].components[0].value,"220")
        project.name="Changed"
        with self.assertRaises(ValueError): session.accept(project)
        session.reject(); self.assertEqual(session.working.to_dict(),before)

    def test_partial_execution_failure_is_atomic(self):
        project=Project(sheets=[Sheet()]); session=CommandSession(project,0)
        before=deepcopy(session.working.to_dict())
        for tail in ('MOVE_COMPONENT id=missing x=100 y=100',
                     'CONNECT from=R1 to=R1 from_pin=900 to_pin=0',
                     'SET_PROPERTY id=R1 property=sim_source value=malicious.py',
                     'MOVE_COMPONENT id=R1 x=nan y=0', 'ROTATE_COMPONENT id=R1 angle=20'):
            with self.subTest(tail=tail), self.assertRaises(ValueError): session.execute(add_command()+"\n"+tail)
            self.assertEqual(session.working.to_dict(),before)

    def test_shell_unknown_arguments_and_duplicate_keys_rejected(self):
        for text in ('cmd /c del C:\\file','ADD_COMPONENT id=R id=X type=a x=1 y=2','MOVE_COMPONENT id=a x=20 y=20 foo=bar'):
            with self.assertRaises(ValueError): parse_commands(text)
        with self.assertRaises(ValueError): decode_answer('{"summary":"x","commands":"rm anything"}')
        self.assertEqual(parse_commands('help'),[("HELP",{})])

    def test_connect_move_rotate_and_delete(self):
        project=execute_batch(Project(sheets=[Sheet()]),0,add_command()+"\n"+add_command("R2",400,200)+"\nCONNECT from=R1 to=R2 from_pin=1 to_pin=0")
        project=execute_batch(project,0,'MOVE_COMPONENT id=R2 x=500 y=300\nROTATE_COMPONENT id=R2 angle=90')
        wire=project.sheets[0].wires[0]
        self.assertEqual((wire.end_x,wire.end_y),(500,260))
        self.assertEqual(len(project.sheets[0].wires),1)
        project=execute_batch(project,0,'DELETE_COMPONENT id=R2')
        self.assertEqual(len(project.sheets[0].components),1)
        self.assertIsNone(project.sheets[0].wires[0].end_component_id)
        project=execute_batch(project,0,'DISCONNECT id='+project.sheets[0].wires[0].id)
        self.assertFalse(project.sheets[0].wires)


class AssistantUiTests(unittest.TestCase):
    def setUp(self): self.window=MainWindow(AppSettings(),start_setup=False)
    def tearDown(self):
        self.window._saved_state=self.window.project.to_dict()
        if hasattr(self.window,"command_panel"): self.window.command_panel.client.cancel()
        self.window.close(); self.window.deleteLater(); APP.processEvents()

    def test_terminal_accept_undo_and_mocked_ai_revision(self):
        self.window.show_command_panel(terminal=True); panel=self.window.command_panel
        before=deepcopy(self.window.project.to_dict())
        panel.commands.setPlainText(add_command()); panel.execute_commands()
        self.assertEqual(self.window.project.to_dict(),before); self.assertFalse(panel.preview.image.isNull())
        panel.completed({"summary":"Revised","commands":"SET_PROPERTY id=R1 property=value value=220"})
        panel.accept(); self.assertEqual(self.window.project.sheets[0].components[0].value,"220")
        self.window.undo(); self.assertEqual(self.window.project.to_dict(),before)
        self.window.redo(); self.assertEqual(len(self.window.project.sheets[0].components),1)

    def test_no_key_assistant_shortcut_does_not_expose_hidden_terminal(self):
        self.assertTrue(self.window.ai_action.isEnabled())
        self.window.show(); self.window.activateWindow(); self.window._current_view().setFocus(); APP.processEvents()
        view=self.window._current_view()
        QTest.keyClick(view,Qt.Key.Key_T,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
        QTest.keyClick(view,Qt.Key.Key_Return)
        self.assertFalse(hasattr(self.window, "command_panel"))
        self.window.show_command_panel()
        panel=self.window.command_panel
        self.assertFalse(panel.tabs.isTabVisible(1))
        self.assertEqual(panel.tabs.currentIndex(),0)
        self.assertFalse(panel.provider_key())

    def test_provider_routing_and_secure_keys(self):
        settings=self.window.settings
        settings.ai_provider="openai"; settings.openai_api_key="fake-openai"
        self.window._translate_ui(); self.assertTrue(self.window.ai_action.isEnabled())
        self.assertNotIn("fake-openai",repr(settings))
        client=AssistantClient()
        with patch.object(client.gemini,"start") as gemini:
            settings.ai_provider="gemini"; settings.api_key="fake-gemini"
            client.start(settings,"Build",{},[])
            args=gemini.call_args.args; self.assertEqual(args[0],"fake-gemini")
            self.assertNotIn("fake-gemini",args[2].decode())
        client.deleteLater()

    def test_frequency_number_and_unit_roundtrip(self):
        b=Bench(); c=b.add("Źródło napięcia przemiennego","5","V",sim_frequency="2 kHz")
        dialog=ComponentPropertiesDialog(c,get_definition(c.library_id),"pl")
        self.assertEqual(dialog.simulation_fields["sim_frequency"].text(),"2")
        self.assertEqual(dialog.simulation_units["sim_frequency"].text(),"kHz")
        dialog.accept(); self.assertEqual(dialog.values["simulation_properties"]["sim_frequency"],"2 kHz")
        dialog.deleteLater()


class AddedModelTests(unittest.TestCase):
    def test_catalog_hidden_entries_survive_and_additions_have_models(self):
        from app.libraries.simulation_catalog import behavior_for
        for name in ("Gniazdo Raspberry Pi 2x20","Zasilacz Raspberry Pi USB-C 27 W"):
            self.assertTrue(any(d.name==name for d in BUILT_IN_ITEMS)); self.assertFalse(any(d.name==name for d in AVAILABLE_ITEMS))
        for name in ("Port USB A","Port USB C","Port Lightning","Karta RFID","Panel słoneczny","Przetwornica DC/AC","Grove LSM6DS3 105020012","Komparator LM393","Przetwornik DAC 8-bit"):
            self.assertIsNotNone(behavior_for(next(d for d in AVAILABLE_ITEMS if d.name==name)))

    def test_solar_scales_output(self):
        b=Bench(); solar=b.add("Panel słoneczny",sim_light="0.5"); r=b.add("Rezystor","1","kΩ")
        b.connect(solar,0,r,0); b.connect(solar,1,r,1)
        result=b.circuit().step(); self.assertAlmostEqual(result.currents[r.id],.003); self.assertFalse(result.faults)

    def test_parallel_dac_binary_conversion(self):
        b=Bench(); s,g=b.power(); dac=b.add("Przetwornik DAC 8-bit"); r=b.add("Rezystor","10","kΩ")
        for pin in ("VCC","VREF","D7"): b.connect(s,0,dac,pin)
        for pin in ("GND",*(f"D{i}" for i in range(7))): b.connect(g,0,dac,pin)
        b.connect(dac,"OUT",r,0); b.connect(r,1,g,0)
        result=b.circuit().step(); self.assertAlmostEqual(result.currents[r.id],5*128/255/10025,places=7); self.assertFalse(result.faults)

    def test_buck_boost_output_and_input_power(self):
        b=Bench(); s,g=b.power(); conv=b.add("Przetwornica DC-DC Step-Up/Step-Down",sim_output_voltage="8 V"); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,conv,"IN+"); b.connect(g,0,conv,"IN−"); b.connect(conv,"OUT+",r,0); b.connect(conv,"OUT−",r,1)
        result=b.circuit().step(); self.assertAlmostEqual(result.currents[r.id],8/1000.1,places=6); self.assertFalse(result.faults)

    def test_rectifier_and_analog_switch(self):
        b=Bench(); source=b.add("Źródło napięcia przemiennego","5","V"); bridge=b.add("Prostownik AC/DC"); r=b.add("Rezystor","1","kΩ")
        b.connect(source,0,bridge,"AC+"); b.connect(source,1,bridge,"AC-"); b.connect(bridge,"DC+",r,0); b.connect(bridge,"DC-",r,1)
        c=b.circuit()
        for _ in range(50): result=c.step(.0001)
        self.assertGreater(result.currents[r.id],.005); self.assertFalse(result.faults)
        b=Bench(); s,g=b.power(); switch=b.add("Przełącznik analogowy CD4066"); r=b.add("Rezystor","1","kΩ")
        for pin in ("VDD","A1","EN.A"): b.connect(s,0,switch,pin)
        for pin in ("VSS","EN.B","EN.C","EN.D"): b.connect(g,0,switch,pin)
        b.connect(switch,"A2",r,0); b.connect(r,1,g,0)
        result=b.circuit().step(); self.assertAlmostEqual(result.currents[r.id],5/1100,places=7)


class NewLiveInputTests(unittest.TestCase):
    def setUp(self): self.window=MainWindow(AppSettings(fault_effect="mini"),start_setup=False)
    def tearDown(self):
        self.window._sync_positions()
        self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()
    def sandbox(self,b):
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        self.window._rebuild_tabs()
        if getattr(self.window,"simulation_window",None) is not None: self.window.simulation_window.reload()
        self.window.show_simulation()
        return self.window.simulation_window

    def test_tact_pir_and_joystick_are_momentary(self):
        b=Bench(); s,g=b.power(); tact=b.add("Przycisk Tact Switch")
        b.connect(s,0,tact,0); b.connect(g,0,tact,1)
        # Avoid shorting a source when the switch closes: use a pull-down load.
        b.wires.pop(); r=b.add("Rezystor","1","kΩ"); b.connect(tact,1,r,0); b.connect(r,1,g,0)
        sim=self.sandbox(b); before=deepcopy(self.window.project.to_dict())
        d=next(d for d in sim.circuit.devices if d.kind=="tactile")
        sim.toggle(tact.id); self.assertTrue(d.closed)
        QTest.qWait(300); self.assertFalse(d.closed)
        self.assertEqual(before,self.window.project.to_dict())

    def test_solar_control_and_joystick_drag(self):
        b=Bench(); solar=b.add("Panel słoneczny"); r=b.add("Rezystor","1","kΩ")
        b.connect(solar,0,r,0); b.connect(solar,1,r,1)
        sim=self.sandbox(b); before=deepcopy(self.window.project.to_dict())
        sim.controls[solar.id].slider.setValue(25)
        self.assertAlmostEqual(sim.circuit.result.currents[r.id],.0015)
        self.assertEqual(before,self.window.project.to_dict())
        b=Bench(); s,g=b.power(); joystick=b.add("Joystick Iduino ST1079")
        b.connect(s,0,joystick,"VCC"); b.connect(g,0,joystick,"GND")
        sim=self.sandbox(b)
        self.assertTrue(hasattr(sim.controls[joystick.id],"joystick"))
        sim.set_simulation_input(joystick.id,"sim_x",.8)
        d=next(d for d in sim.circuit.devices if d.kind=="joystick")
        self.assertEqual(d.parameters["sim_x"],.8)
        sim.toggle(joystick.id); self.assertTrue(d.closed)
        QTest.qWait(300); self.assertFalse(d.closed)

    def test_pi_console_toggle_and_print(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"console.py"; source.write_text('print("Hello Pi", end="!")\n',encoding="utf-8")
            b=Bench(); board=b.add("Raspberry Pi 5",sim_source=str(source),sim_mode="gpio",sim_console="true")
            r=b.add("Rezystor","1","kΩ"); b.connect(board,"5V",r,0); b.connect(board,"GND",r,1)
            sim=self.sandbox(b); sim.single_step(); sim.toggle_console(board.id)
            self.assertTrue(sim.pi_consoles[board.id].isVisible())
            self.assertIn("Hello Pi!",sim.pi_consoles[board.id].toPlainText())
            sim.toggle_console(board.id); self.assertFalse(sim.pi_consoles[board.id].isVisible())


class OpenAITransportTests(unittest.TestCase):
    def test_request_and_response_without_network(self):
        class Reply(FakeReply):
            def readAll(self): return self.read(len(self.body))
            def bytesAvailable(self): return len(self.body)
        answer={"summary":"Preview", "commands":add_command()}
        result={"status":"completed","output":[{"type":"reasoning","content":[{"type":"output_text","text":"not displayed"}]},
            {"type":"message","content":[{"type":"output_text","text":json.dumps(answer)}]}]}
        reply=Reply(body=json.dumps(result).encode()); client=AssistantClient(); received=[]
        client.completed.connect(received.append)
        settings=AppSettings(ai_provider="openai",openai_api_key="fake-openai")
        with patch.object(client.network,"post",return_value=reply) as post:
            client.start(settings,"Build",{},[])
            request,body=post.call_args.args
            self.assertEqual(bytes(request.rawHeader("Authorization")),b"Bearer fake-openai")
            self.assertFalse(json.loads(body)["store"])
            self.assertNotIn("fake-openai",body.decode())
        reply.finished.emit(); self.assertEqual(received,[decode_answer(json.dumps(answer))])
        client.deleteLater(); APP.processEvents()
