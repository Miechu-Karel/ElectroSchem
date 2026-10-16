"""Alpha11: stable scope, CV/CC supply, cables and bounded AI. Offline only."""
import os,math,json,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch,MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings,QPointF,Qt
from PySide6.QtTest import QTest
from app.core.settings import AppSettings,load_settings,save_settings,remember_request_consent
from app.core.models import Project,Sheet
from app.libraries.built_in import get_definition,AVAILABLE_ITEMS
from app.libraries.menu_groups import secondary_locations
from app.ui.scope_trace import acquire,automatic_duration
from app.ui.main_window import MainWindow
from app.simulation.netlist import build_netlist
from test_simulation_alpha2 import Bench
from test_alpha1310 import PLAN
APP=QApplication.instance() or QApplication([])

class ScopeTests(unittest.TestCase):
    def test_trigger_keeps_phase_and_time_axis_stationary(self):
        frames=[]
        for end in (1.,1.013,1.038):
            samples=[(i/10000,math.sin(2*math.pi*50*i/10000)) for i in range(int(end*10000))]
            data,bounds=acquire(samples,.08,(-2,2))
            self.assertEqual(bounds,(-2,2)); self.assertAlmostEqual(data[0][0],0); self.assertAlmostEqual(data[0][1],0,places=5)
            peak=min(data,key=lambda p:abs(p[0]-.005)); frames.append(peak[1])
            self.assertLessEqual(data[-1][0],.080000001)
        self.assertLess(max(frames)-min(frames),.001)
    def test_auto_voltage_scale_and_manual_range(self):
        samples=[(i*.001,4+2*math.sin(i*.1)) for i in range(600)]
        _,bounds=acquire(samples,.1,(-10,10),True); self.assertGreater(bounds[0],1); self.assertLess(bounds[1],7)
        _,manual=acquire(samples,.1,(-10,10),False); self.assertEqual(manual,(-10,10))
        sine=[(i*.0001,math.sin(2*math.pi*50*i*.0001)) for i in range(10000)]
        self.assertAlmostEqual(automatic_duration(sine,1),.08,places=5)
    def test_settings_and_consent_roundtrip(self):
        with TemporaryDirectory() as directory:
            store=QSettings(str(Path(directory)/'test.ini'),QSettings.Format.IniFormat)
            settings=AppSettings(scope_time_div=.025,scope_volts_div=.5,scope_autoscale=True,ai_provider='local')
            save_settings(settings,store); remember_request_consent(settings,store); loaded=load_settings(store)
            self.assertEqual((loaded.scope_time_div,loaded.scope_volts_div,loaded.scope_autoscale),(.025,.5,True))
            self.assertEqual(loaded.ai_request_consents,{'local':True})
            store.setValue('scope_time_div','nan'); self.assertEqual(load_settings(store).scope_time_div,.01)

class SupplyTests(unittest.TestCase):
    def circuit(self,limit='1 A',voltage='10'):
        b=Bench(); supply=b.add('Zasilacz laboratoryjny',voltage,'V',sim_max_current=limit); r=b.add('Rezystor','100','Ω',sim_max_power='100 W')
        b.connect(supply,0,r,0); b.connect(supply,1,r,1); return b.circuit(),supply,r
    def test_cv_cc_and_zero_output(self):
        for limit,current,voltage in (('1 A',.1,10),('50 mA',.05,5)):
            circuit,supply,r=self.circuit(limit); result=circuit.step(); self.assertFalse(result.faults)
            self.assertAlmostEqual(result.currents[r.id],current,places=7)
            self.assertAlmostEqual(result.voltages[circuit.netlist.pins[r.id,0]]-result.voltages[circuit.netlist.pins[r.id,1]],voltage)
        circuit,supply,r=self.circuit(voltage='0'); self.assertAlmostEqual(circuit.step().currents[r.id],0)
    def test_live_supply_parameters_and_waveform(self):
        circuit,supply,r=self.circuit(); device=next(d for d in circuit.devices if d.component.id==supply.id)
        device.parameters['value']=3; self.assertAlmostEqual(circuit.step().currents[r.id],.03)
        device.parameters['sim_waveform']='square'; device.parameters['sim_frequency']=50
        self.assertAlmostEqual(circuit.step(.0001).currents[r.id],.03)
        self.assertLess(circuit.maximum_time_step(),.001)

class CableTests(unittest.TestCase):
    def test_matching_jumper_and_gender_mismatch(self):
        b=Bench(); male=b.add('Goldpin'); female=b.add('Goldpin żeński'); cable=b.add('Kabel Męsko-Żeński',jumper_a_target=female.id,jumper_b_target=male.id)
        net=build_netlist(Sheet(components=b.components)); self.assertEqual(net.pins[male.id,1],net.pins[female.id,1])
        from app.services.clipboard import encode_selection,decode_selection,prepare_paste
        sheet=Sheet(components=b.components); project=Project(sheets=[sheet]); fragment=decode_selection(encode_selection(project,sheet,{c.id for c in b.components}))
        _,copied=prepare_paste(project,fragment,20,20); replacement=next(c for c in copied.components if c.library_id==cable.library_id)
        self.assertNotEqual(replacement.properties['jumper_a_target'],female.id); self.assertIn(replacement.properties['jumper_a_target'],{c.id for c in copied.components})
        cable.properties['jumper_a_target']=male.id; cable.properties['jumper_b_target']=female.id
        net=build_netlist(Sheet(components=b.components)); self.assertNotEqual(net.pins[male.id,1],net.pins[female.id,1])
    def test_buzzer_secondary_sound_location(self):
        buzzer=next(d for d in AVAILABLE_ITEMS if d.symbol=='buzzer'); self.assertIn(('Dźwięk',('Sound','Dźwięk')),secondary_locations(buzzer))

class UITests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False); self.window.show(); APP.processEvents()
    def tearDown(self):
        if getattr(self.window,'command_panel',None): self.window.command_panel.cancel_request()
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict(); self.window.close(); self.window.deleteLater(); APP.processEvents()
    def test_editor_usb_and_jumper_connections_are_project_changes(self):
        b=Bench(); brick=b.add('Kostka zasilająca USB','5','V'); port=b.add('Port USB C'); cable=b.add('Kabel USB')
        male=b.add('Goldpin'); jumper=b.add('Kabel Żeńsko-Żeński')
        self.window.project=Project(sheets=[Sheet(components=b.components)]); self.window._rebuild_tabs()
        view=self.window._current_view(); layer=view.cable_layer; self.assertEqual(len(layer.usb_cables),2)
        usb=next(c for c in layer.usb_cables if c.component.id==cable.id)
        for plug,target in zip(usb.plugs,(brick,port)):
            point=next(p for cid,p in usb.targets(plug) if cid==target.id); plug.setPos(point); usb.attach(plug)
        self.assertEqual(cable.properties['usb_a_target'],brick.id); self.assertEqual(cable.properties['usb_b_target'],port.id)
        lead=next(c for c in layer.usb_cables if c.component.id==jumper.id); plug=lead.plugs[0]
        plug.setPos(layer.symbols[male.id].pin_positions()[0]); lead.attach(plug); self.assertEqual(jumper.properties['jumper_a_target'],male.id)
        layer.symbols[male.id].setPos(male.x+20,male.y); view._refresh_attached_wires(); self.assertEqual(plug.pos(),layer.symbols[male.id].pin_positions()[0])
        view._delete_item(lead.path); self.assertEqual(len(layer.usb_cables),1)
        usb.path.setSelected(True); before=usb.component.rotation; view.rotate_selected_components(); self.assertEqual(usb.component.rotation,(before+90)%360)
    def test_scope_axes_are_live(self):
        b=Bench(); s,g=b.power(); scope=b.add('Oscyloskop'); b.connect(s,0,scope,0); b.connect(g,0,scope,1)
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); self.window._rebuild_tabs(); self.window.show_simulation(); sim=self.window.simulation_window
        sim.open_measurements(); panel=sim.measurement_panel; panel.time_div.setValue(.02); panel.volts_div.setValue(2)
        item=sim.scopes[scope.id]; self.assertEqual(item.scope_duration,.16); self.assertEqual(item.scope_bounds,(-4,4))
        panel.auto_scale.setChecked(True); self.assertTrue(item.scope_autoscale); sim.close(); APP.processEvents()
    def test_jumper_can_be_dragged_with_mouse_in_editor(self):
        b=Bench(); male=b.add('Goldpin'); cable=b.add('Kabel Żeńsko-Żeński'); male.x,male.y=300,250; cable.x,cable.y=500,500
        self.window.project=Project(sheets=[Sheet(components=b.components)]); self.window._rebuild_tabs(); view=self.window._current_view(); view.fit_page(); APP.processEvents()
        lead=view.cable_layer.usb_cables[0]; plug=lead.plugs[0]
        start=view.mapFromScene(plug.pos()+QPointF(0,20)); end=view.mapFromScene(view._component_items[male.id].pin_positions()[0]+QPointF(0,20))
        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=start); QTest.mouseMove(view.viewport(),end,50); QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=end); APP.processEvents()
        self.assertEqual(cable.properties.get('jumper_a_target'),male.id)
    def test_lab_controls_are_live_and_sandbox_only(self):
        b=Bench(); source=b.add('Zasilacz laboratoryjny','5','V'); r=b.add('Rezystor','100','Ω',sim_max_power='100 W'); b.connect(source,0,r,0); b.connect(source,1,r,1)
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); self.window._rebuild_tabs(); original=deepcopy(self.window.project.to_dict()); self.window.show_simulation(); sim=self.window.simulation_window
        panel=sim.controls[source.id]; panel.fields['value'].setValue(10); panel.fields['sim_max_current'].setValue(.02)
        self.assertAlmostEqual(sim.circuit.result.currents[r.id],.02); self.assertIn('CC',panel.reading.text()); self.assertEqual(self.window.project.to_dict(),original)
        panel.fields['sim_waveform'].setCurrentIndex(1); self.assertEqual(next(d for d in sim.circuit.devices if d.component.id==source.id).parameters['sim_waveform'],'sine')
        sim.close(); APP.processEvents()
    def test_ai_remembers_consent_and_can_edit_or_stop(self):
        self.window.settings.ai_provider='local'; self.window.settings.local_ai_model='fixture'; self.window.settings.ai_chat_consent=True; self.window.settings.ai_request_consents={'local':True}
        self.window.show_command_panel(); panel=self.window.command_panel; panel.prompt.setPlainText('LED')
        with patch('app.services.assistant_curriculum.read_profile',return_value={'exercises':[{}]*20}),patch('app.ui.ai_cost_dialog.confirm_requests') as confirm,patch.object(panel.planner,'start'):
            panel.send_request(); self.assertFalse(confirm.called); self.assertTrue(panel.stop_response.isEnabled()); panel.stop_response.click()
            self.assertFalse(panel.busy); panel.edit_last_prompt(); self.assertEqual(panel.prompt.toPlainText(),'LED')
    def test_planner_cannot_keep_interviewing(self):
        self.window.settings.ai_provider='local'; self.window.settings.local_ai_model='fixture'; self.window.settings.ai_chat_consent=True; self.window.settings.ai_request_consents={'local':True}
        self.window.show_command_panel(); panel=self.window.command_panel; panel.prompt.setPlainText('LED')
        with patch('app.services.assistant_curriculum.read_profile',return_value={'exercises':[{}]*20}),patch.object(panel.planner,'start'),patch.object(panel.client,'start') as draw:
            panel.send_request(); panel.plan_completed({**PLAN,'questions':['Voltage?']}); self.assertFalse(draw.called)
            panel.prompt.setPlainText('5V'); panel.send_request(); panel.plan_completed({**PLAN,'questions':[]}); self.assertTrue(draw.called)
            self.assertIn('LED',draw.call_args.args[1]); self.assertIn('5V',draw.call_args.args[1])
        panel.cancel_request()

if __name__=='__main__': unittest.main()
