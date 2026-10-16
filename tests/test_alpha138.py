"""Alpha8 regressions: fixtures and UI checks, without provider API calls."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPointF,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.core.models import Sheet,Wire,Project
from app.core.settings import AppSettings
from app.core.wire_topology import merge_overlaps
from app.canvas.routing import overlap_allowed
from app.canvas.component_item import ComponentItem
from app.libraries.built_in import get_definition,AVAILABLE_ITEMS
from app.libraries.component_info import explanation
from app.libraries.pin_info import pin_explanation
from app.services.assistant_curriculum import tasks,validate_response
from app.simulation.examples import example
from app.simulation.engine import Circuit
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])

class TopologyTests(unittest.TestCase):
    def test_partial_overlap_becomes_one_stretch_and_real_branch(self):
        a=Wire(100,100,300,100,points=[[100,100],[300,100]],start_component_id='a',start_pin_index=0)
        b=Wire(200,100,400,200,points=[[200,100],[400,100],[400,200]],end_component_id='b',end_pin_index=1)
        sheet=Sheet(wires=[a,b]); self.assertTrue(merge_overlaps(sheet,{b.id}))
        for wire in sheet.wires:
            self.assertTrue(overlap_allowed(sheet,[QPointF(*p) for p in wire.points],{wire.id}))
        self.assertTrue(any(w.start_component_id=='a' or w.end_component_id=='a' for w in sheet.wires))
        self.assertTrue(any(w.start_component_id=='b' or w.end_component_id=='b' for w in sheet.wires))
        self.assertFalse(merge_overlaps(sheet,{w.id for w in sheet.wires}))
    def test_t_branch_keeps_shared_junction(self):
        a=Wire(100,100,400,100,points=[[100,100],[400,100]])
        b=Wire(200,200,400,100,points=[[200,200],[200,100],[400,100]])
        sheet=Sheet(wires=[a,b]); self.assertTrue(merge_overlaps(sheet,{b.id}))
        ends=[getattr(w,side+'_junction_id') for w in sheet.wires for side in ('start','end') if (getattr(w,side+'_x'),getattr(w,side+'_y'))==(200,100)]
        self.assertEqual(len(ends),3); self.assertEqual(len(set(ends)),1); self.assertIsNotNone(ends[0])
    def test_threshold_crossing_and_unedited_overlap(self):
        for second in (Wire(180,100,300,100),Wire(150,50,150,150)):
            a=Wire(100,100,200,100); sheet=Sheet(wires=[a,second])
            self.assertFalse(merge_overlaps(sheet,{second.id}))
        a=Wire(100,100,300,100); b=Wire(200,100,400,100); untouched=Wire(500,500,600,500)
        self.assertFalse(merge_overlaps(Sheet(wires=[a,b,untouched]),{untouched.id}))
    def test_reversed_diagonal_preserves_asset_group(self):
        a=Wire(100,100,300,300,group_id='asset'); b=Wire(400,400,200,200,group_id='asset')
        sheet=Sheet(wires=[a,b]); self.assertTrue(merge_overlaps(sheet,{b.id}))
        self.assertEqual(len(sheet.wires),1); self.assertEqual(sheet.wires[0].group_id,'asset')

class ElectricalTests(unittest.TestCase):
    def test_external_usb_supply_does_not_conflict_with_pi_rail(self):
        for voltage in ('5','5.1'):
            b=Bench(); board=b.add('Raspberry Pi 5',sim_mode='gpio',sim_builtin_example='blink')
            brick=b.add('Kostka zasilająca USB',voltage,'V')
            b.add('Kabel USB',sim_usb_a_type='A',sim_usb_b_type='C',usb_a_target=brick.id,usb_b_target=board.id)
            result=b.circuit().step(); self.assertFalse(result.faults)
    def test_every_demo_has_separate_routes(self):
        for key in ('led','ac','capacitor','rails','transistor','meter_ac','meter_ohm','pi_blink','usb_c_led','fault_led','fault_resistor','fault_gpio'):
            with self.subTest(key=key):
                sheet=example(key)
                for w in sheet.wires: self.assertTrue(overlap_allowed(sheet,[QPointF(*p) for p in w.points],{w.id}))
                result=Circuit(sheet).step()
                if key.startswith('fault_'): self.assertTrue(result.faults)
                else: self.assertFalse(result.faults)
    def test_all_twenty_exercises_validate_offline(self):
        for task in tasks():
            self.assertTrue(validate_response(task,{'commands':task['commands'],'summary':'Fixture'})['verified'])
    def test_exercise18_applies_stimulus_but_rejects_wrong_gate(self):
        task=tasks()[17]
        commands='\n'.join(line for line in task['commands'].splitlines() if 'property=sim_closed' not in line)
        result=validate_response(task,{'commands':commands,'summary':'Fixture'})
        self.assertIn('property=sim_closed value=true',result['commands'])
        not_id=next(d.id for d in AVAILABLE_ITEMS if d.name=='Bramka NOT')
        wrong_id=next(d.id for d in AVAILABLE_ITEMS if d.name=='Bramka AND')
        with self.assertRaises(ValueError): validate_response(task,{'commands':commands.replace(not_id,wrong_id),'summary':'Wrong'})
    def test_usb_help_describes_power_and_all_pin_roles(self):
        for d in AVAILABLE_ITEMS:
            if d.name.startswith('Port USB'):
                self.assertIn('VBUS',explanation(d,'pl')); self.assertIn('GPIO',explanation(d,'pl'))
                for pin in d.pins: self.assertGreater(len(pin_explanation(d,pin,'pl')),15)

class UITests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language='pl',window_mode='windowed',fault_effect='mini'),start_setup=False)
        self.window.show(); APP.processEvents()
    def tearDown(self):
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()
    def load(self,b):
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        self.window._rebuild_tabs(); APP.processEvents(); return self.window._current_view()
    def test_switch_reloads_geometry_and_keeps_selection(self):
        b=Bench(); c=b.add('Przełącznik wielostopniowy',sim_outputs='2'); view=self.load(b)
        old=view._component_items[c.id]; old.setSelected(True)
        c.properties['sim_outputs']='10'; view.refresh_component(c.id)
        new=view._component_items[c.id]
        self.assertEqual(len(new.definition.pins),11); self.assertGreater(new.boundingRect().height(),old.boundingRect().height())
        self.assertTrue(new.isSelected()); self.assertIsNone(old.scene())
        wire=Wire(200,200,360,360,end_component_id=c.id,end_pin_index=10,end_pin_number='11')
        view._sheet.wires.append(wire); view._add_wire_item(wire)
        c.properties['sim_outputs']='2'; view.refresh_component(c.id)
        self.assertIsNone(wire.end_component_id); self.assertIsNone(wire.end_pin_index)
        self.assertIn(wire,view._sheet.wires)
    def test_f_opens_properties_without_changing_favorites(self):
        b=Bench(); c=b.add('Rezystor'); view=self.load(b); view._component_items[c.id].setSelected(True)
        view.setFocus(); APP.processEvents()
        with patch.object(self.window,'show_component_properties') as opened,patch.object(self.window,'toggle_favorite') as favorite:
            QTest.keyClick(view,Qt.Key.Key_E); opened.assert_called_once_with(c); favorite.assert_not_called()
    def test_manual_wire_overlap_is_merged_by_the_view(self):
        b=Bench(); view=self.load(b)
        old=Wire(200,300,500,300,points=[[200,300],[500,300]])
        view._sheet.wires.append(old); view._add_wire_item(old)
        view.set_tool('wire')
        for point in (QPointF(300,300),QPointF(600,300)):
            QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=view.mapFromScene(point))
        APP.processEvents()
        self.assertGreater(len(view._sheet.wires),0)
        self.assertTrue(any(w.end_x==600 or w.start_x==600 for w in view._sheet.wires))
        for w in view._sheet.wires: self.assertTrue(overlap_allowed(view._sheet,[QPointF(*p) for p in w.points],{w.id}))
    def test_keyboard_mouse_host_keys_polish_and_console_f(self):
        b=Bench(); board=b.add('Raspberry Pi 5',sim_source=str(Path(__file__).parent/'fixtures'/'console_input.py'))
        keyboard=b.add('Klawiatura USB'); brick=b.add('Kostka zasilająca USB','5.1','V')
        b.add('Kabel USB',sim_usb_a_type='A',sim_usb_b_type='C',usb_a_target=brick.id,usb_b_target=board.id)
        b.add('Kabel USB',sim_usb_a_type='A',sim_usb_b_type='C',usb_a_target=board.id,usb_b_target=keyboard.id)
        self.load(b); self.window.show_simulation(); sim=self.window.simulation_window; APP.processEvents(); sim.single_step()
        self.assertEqual(ComponentItem(keyboard).pin_positions(),[])
        panel=sim.controls[keyboard.id]
        QTest.mouseClick(panel.buttons['a'],Qt.MouseButton.LeftButton)
        QTest.keyClicks(panel.entry,'la'); self.assertEqual(panel.entry.text(),'ala')
        QTest.keyClick(panel.entry,Qt.Key.Key_Return)
        for _ in range(200): sim.single_step()
        self.assertIn('Cześć ala',sim.console_script(board.id).serial)
        QTest.mouseClick(panel.buttons['AltGr'],Qt.MouseButton.LeftButton); QTest.mouseClick(panel.buttons['z'],Qt.MouseButton.LeftButton)
        self.assertEqual(panel.entry.text(),'ż')
        symbol=sim.symbols[board.id]; symbol.setSelected(True); sim.view.setFocus(); APP.processEvents()
        QTest.keyClick(sim.view,Qt.Key.Key_E); self.assertTrue(sim.pi_consoles[board.id].isVisible())
        sim.view.setFocus(); QTest.keyClick(sim.view,Qt.Key.Key_E); self.assertFalse(sim.pi_consoles[board.id].isVisible())
    def test_custom_toolbar_icons_are_loaded(self):
        b=Bench(); b.add('Raspberry Pi 5'); self.load(b); self.window.show_simulation(); sim=self.window.simulation_window
        self.assertFalse(sim.camera_button.icon().isNull()); self.assertFalse(sim.buzzer_sound_button.icon().isNull())

if __name__=='__main__': unittest.main()
