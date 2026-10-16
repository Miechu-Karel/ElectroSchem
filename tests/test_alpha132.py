"""Offline alpha2 regressions: settings, inspection, probes and live switches."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
from copy import deepcopy
from unittest.mock import patch
import unittest
from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.models import Project, Sheet
from app.core.settings import AppSettings
from app.core.editor_commands import execute_batch
from app.ui.settings_dialog import SettingsDialog
from app.ui.main_window import MainWindow
from app.services.assistant_examples import examples
from app.services.proposal_simulation import simulate_proposal
from app.libraries.built_in import AVAILABLE_ITEMS
from app.libraries.menu_groups import subgroup
from test_simulation_alpha2 import Bench

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)

def wait_release(predicate):
    deadline = time.monotonic()+1
    while predicate() and time.monotonic() < deadline:
        APP.processEvents(); time.sleep(.01)


class SettingsTests(unittest.TestCase):
    def test_single_key_switch_preserves_separate_keys_and_none(self):
        dialog=SettingsDialog(AppSettings(api_key="gem-key",openai_api_key="oa-key"))
        try:
            dialog.show(); APP.processEvents()
            self.assertEqual(dialog.key.text(),"gem-key")
            self.assertTrue(dialog.model.isHidden()); self.assertTrue(dialog.openai_model.isHidden())
            self.assertEqual(dialog._rows[6].text(),"Gemini key")
            dialog.key.setText("changed-gem-key")
            dialog.provider.setCurrentIndex(dialog.provider.findData("openai"))
            self.assertEqual(dialog.key.text(),"oa-key")
            self.assertEqual(dialog._rows[6].text(),"OpenAI key")
            dialog.key.setText("changed-oa-key")
            dialog.provider.setCurrentIndex(dialog.provider.findData("none"))
            self.assertTrue(dialog.key.isHidden())
            dialog._accept(); result=dialog.result_settings()
            self.assertEqual(result.ai_provider,"none")
            self.assertEqual(result.api_key,"changed-gem-key")
            self.assertEqual(result.openai_api_key,"changed-oa-key")
        finally: dialog.close(); dialog.deleteLater(); APP.processEvents()

    def test_power_menu_has_small_subgroups_without_id_changes(self):
        groups={}
        for item in AVAILABLE_ITEMS:
            if item.category=="Zasilanie i połączenia": groups.setdefault(subgroup(item),[]).append(item.id)
        self.assertGreaterEqual(len(groups),5)
        self.assertLessEqual(max(map(len,groups.values())),20)


class ProbeTests(unittest.TestCase):
    def test_bundled_examples_execute_and_probe_is_immutable(self):
        project=execute_batch(Project(sheets=[Sheet()]),0,examples()[0]["response"]["commands"])
        before=deepcopy(project.to_dict())
        report=simulate_proposal(project,0)
        self.assertEqual(report["status"],"sampled",report)
        self.assertLessEqual(report["steps"],250)
        self.assertFalse(report["faults"])
        resistor=next(c for c in project.sheets[0].components if c.reference=="R1")
        self.assertAlmostEqual(report["peak_current_A"][resistor.id],.009,places=5)
        self.assertEqual(project.to_dict(),before)
        revised=execute_batch(project,0,examples()[1]["response"]["commands"])
        self.assertEqual(revised.sheets[0].components[1].value,"2.2")

    def test_empty_and_firmware_are_reported_without_reading_files(self):
        self.assertEqual(simulate_proposal(Project(sheets=[Sheet()]),0)["status"],"blocked")
        b=Bench(); board=b.add("Raspberry Pi 5",sim_mode="gpio",sim_source="C:/private.py")
        project=Project(sheets=[Sheet(components=b.components)])
        with patch("pathlib.Path.read_text",side_effect=AssertionError("File access forbidden")):
            report=simulate_proposal(project,0)
        self.assertEqual(report["status"],"not_tested"); self.assertIn("Firmware",report["reason"])


class PanelTests(unittest.TestCase):
    def setUp(self): self.window=MainWindow(AppSettings(language="pl",fault_effect="mini"),start_setup=False)
    def tearDown(self):
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()

    def test_no_key_has_visible_feedback_and_none_disables_only_ai(self):
        self.window.show_ai(); panel=self.window.command_panel
        self.assertIn("Brak klucza",panel.status.text()); self.assertTrue(panel.send.isEnabled())
        panel.prompt.setPlainText("Dodaj rezystor")
        with patch.object(panel.client,"start") as start:
            panel.send_request(); start.assert_not_called()
        self.assertIn("klucz API",panel.status.text())
        self.window.settings.ai_provider="none"; self.window._translate_ui(); panel.translate()
        self.assertFalse(self.window.ai_action.isEnabled()); self.assertFalse(panel.send.isEnabled())
        self.assertTrue(panel.execute.isEnabled())

    def test_proposal_is_zoomable_and_report_reaches_model_context(self):
        self.window.show_command_panel(terminal=True); panel=self.window.command_panel
        panel.commands.setPlainText(examples()[0]["response"]["commands"]); panel.execute_commands()
        self.assertEqual(panel.preview.image.width(),2400)
        self.assertTrue(panel.inspect_button.isEnabled())
        self.assertEqual(panel.working_context()["simulation_report"]["status"],"sampled")
        self.assertEqual(len(self.window.project.sheets[0].components),0)

    def sandbox(self,b):
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        self.window._rebuild_tabs(); self.window.show_simulation()
        return self.window.simulation_window

    def test_joystick_actual_right_click_drives_sw_and_releases(self):
        b=Bench(); s,g=b.power(); joy=b.add("Joystick Iduino ST1079",sim_switch_mode="contact"); pull=b.add("Rezystor","10","kΩ")
        b.connect(s,0,joy,"VCC"); b.connect(g,0,joy,"GND")
        b.connect(s,0,pull,0); b.connect(pull,1,joy,"SW")
        sim=self.sandbox(b); sim.single_step()
        d=next(d for d in sim.circuit.devices if d.component.id==joy.id)
        pin=sim.circuit.netlist.pins[joy.id,4]
        self.assertGreater(sim.circuit.result.voltages[pin],4.9)
        control=sim.controls[joy.id].joystick
        QTest.mousePress(control,Qt.MouseButton.RightButton,pos=QPoint(75,75))
        self.assertTrue(d.closed); self.assertTrue(control.pressed)
        self.assertLess(sim.circuit.result.voltages[pin],.1)
        QTest.qWait(300); self.assertTrue(d.closed)
        QTest.mouseRelease(control,Qt.MouseButton.RightButton,pos=QPoint(75,75))
        self.assertFalse(d.closed)
        self.assertGreater(sim.circuit.result.voltages[pin],4.9)
        QTest.mousePress(sim.controls[joy.id].switch_button,Qt.MouseButton.LeftButton)
        self.assertTrue(d.closed)
        QTest.mouseRelease(sim.controls[joy.id].switch_button,Qt.MouseButton.LeftButton)
        self.assertFalse(d.closed)

    def test_tact_visual_changes_during_pulse(self):
        b=Bench(); s,g=b.power(); tact=b.add("Przycisk Tact Switch"); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,tact,0); b.connect(tact,1,r,0); b.connect(r,1,g,0)
        sim=self.sandbox(b); item=sim.symbols[tact.id]
        def snapshot():
            image=QImage(300,200,QImage.Format.Format_ARGB32_Premultiplied); image.fill(Qt.GlobalColor.black)
            painter=QPainter(image); sim.scene.render(painter,QRectF(0,0,300,200),item.sceneBoundingRect()); painter.end()
            return image
        before=snapshot(); sim.toggle(tact.id)
        self.assertEqual(item.component.properties["sim_closed"],"true")
        self.assertNotEqual(before,snapshot())
        wait_release(lambda:item.component.properties["sim_closed"]=="true")
        self.assertEqual(item.component.properties["sim_closed"],"false")
