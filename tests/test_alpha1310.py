"""Alpha10: measurements, stable scope, AC limits and two-stage AI, offline."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json,math,unittest
from unittest.mock import patch,MagicMock
from PySide6.QtCore import QSettings,Qt,QRectF
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from app.core.models import Project,Sheet
from app.core.settings import AppSettings,save_settings,load_settings
from app.libraries.built_in import AVAILABLE_ITEMS,get_definition,item_name
from app.libraries.menu_groups import subgroup
from app.libraries.component_info import explanation
from app.services.assistant_plan import decode_plan
from app.services.ai_errors import explanation as error_explanation
from app.simulation.engine import ac_voltage,SimulationError
from app.simulation.measurements import resistance,live_network
from app.ui.instrument_graphics import draw_waveform,scope_dimensions
from app.ui.main_window import MainWindow
from app.ui.properties_dialog import ComponentPropertiesDialog
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])
PLAN={'goal':'LED circuit','tasks':[{'id':1,'task':'Add source and current-limited LED','check':'Closed return, rated current','depends_on':[]}],'questions':[]}

class ModelTests(unittest.TestCase):
    def test_names_groups_pinout_and_stable_ids(self):
        families=set()
        for d in AVAILABLE_ITEMS:
            if d.name.startswith('Układ Scalony ') and d.name.split()[-1] in {'NE567','TL072','CD4017','CH340G','W25Q128','DS1307','LM7809','IR2101'}:
                families.add(subgroup(d)[0]); self.assertIn(' — ',item_name(d,'pl')); self.assertIn('Ograniczenia',explanation(d,'pl'))
        self.assertGreaterEqual(len(families),7)
        d=next(d for d in AVAILABLE_ITEMS if d.name=='Układ Scalony NE567')
        self.assertEqual([p.name for p in d.pins],['OUT_FILTER','LOOP_FILTER','IN','VCC','TIMING_R','TIMING_RC','GND','OUT'])
        self.assertEqual(next(d for d in AVAILABLE_ITEMS if d.name=='Układ Scalony TL072').id,'układy-i-sterowniki-układ-scalony-tl072')
    def test_ac_limits_all_waveforms_and_rms(self):
        for shape in ('sine','square','triangle','sawtooth'):
            values=[ac_voltage(123,50,i/50000,shape,-2,6) for i in range(1000)]
            self.assertAlmostEqual(min(values),-2,places=5); self.assertAlmostEqual(max(values),6,delta=.01)
            self.assertAlmostEqual(sum(values)/len(values),2,delta=.01)
            values=[ac_voltage(5,50,i/50000,shape) for i in range(1000)]
            self.assertAlmostEqual(math.sqrt(sum(v*v for v in values)/len(values)),5,delta=.001)
    def test_circuit_uses_limits_and_rejects_reversed_bounds(self):
        b=Bench(); source=b.add('Źródło napięcia przemiennego','5','V',sim_voltage_mode='limits',sim_voltage_min='-2 V',sim_voltage_max='6 V',sim_waveform='square'); r=b.add('Rezystor','10','kΩ')
        b.connect(source,0,r,0); b.connect(source,1,r,1)
        c=b.circuit(); result=c.step(.0001)
        self.assertAlmostEqual(result.currents[r.id],.0006,places=7)
        source.properties['sim_voltage_max']='-3 V'
        with self.assertRaises(SimulationError): b.circuit()
    def test_open_switch_does_not_bridge_back_to_source_and_can_measure(self):
        b=Bench(); battery=b.add('Bateria','5','V'); sw=b.add('Łącznik'); r=b.add('Rezystor','5','Ω')
        b.connect(battery,0,sw,0); b.connect(sw,1,r,0); b.connect(r,1,battery,1)
        circuit=b.circuit(); result=circuit.step(); net=circuit.netlist; a,z=net.pins[r.id,0],net.pins[r.id,1]
        self.assertFalse(live_network(circuit.sheet,net,a,z,circuit.devices,result))
        self.assertAlmostEqual(resistance(circuit.sheet,[],net,a,z,circuit.devices),5)
        device=next(d for d in circuit.devices if d.component.id==sw.id); device.closed=True
        result=circuit.step(); self.assertTrue(live_network(circuit.sheet,net,a,z,circuit.devices,result))
    def test_ac_zero_crossing_still_blocks_ohms(self):
        b=Bench(); source=b.add('Źródło napięcia przemiennego','5','V'); r=b.add('Rezystor','10','kΩ')
        b.connect(source,0,r,0); b.connect(source,1,r,1); c=b.circuit()
        result=c.result; result.voltages={n:0 for n in c.netlist.pins.values()}
        self.assertTrue(live_network(c.sheet,c.netlist,c.netlist.pins[r.id,0],c.netlist.pins[r.id,1],c.devices,result))
    def test_settings_roundtrip(self):
        with TemporaryDirectory() as directory:
            store=QSettings(str(Path(directory)/'prefs.ini'),QSettings.Format.IniFormat)
            save_settings(AppSettings(scope_size='huge',stop_on_fault=False),store)
            settings=load_settings(store); self.assertEqual(scope_dimensions(settings),(800,440)); self.assertFalse(settings.stop_on_fault)
            store.setValue('scope_size','bad'); self.assertEqual(load_settings(store).scope_size,'normal')
    def test_trace_vertical_position_does_not_change_with_samples(self):
        def image(samples):
            im=QImage(500,260,QImage.Format.Format_ARGB32); p=QPainter(im)
            draw_waveform(p,QRectF(0,0,500,260),samples,(-10,10)); p.end(); return im
        first=image([(0,0),(1,5)]); second=image([(0,0),(1,5),(2,-5)])
        # At the start both traces keep 0 V at the exact same vertical pixel.
        def green_rows(im): return [y for y in range(25,235) if im.pixelColor(57,y).green()>180 and im.pixelColor(57,y).red()<140]
        self.assertEqual(green_rows(first),green_rows(second))

class PlannerTests(unittest.TestCase):
    def test_local_plan_transport_and_busy_purpose_guard(self):
        from app.services.assistant_client import AssistantClient
        from test_ai_settings import FakeReply
        class Reply(FakeReply):
            def readAll(self): return self.read(len(self.body))
        client=AssistantClient(); completed=[]; client.completed.connect(completed.append)
        reply=Reply(status=200,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(PLAN)}}]}).encode())
        settings=AppSettings(ai_provider='local',local_ai_model='test-model')
        with patch.object(client.network,'post',return_value=reply) as post,patch('app.services.assistant_curriculum.remembered_knowledge',return_value=[]):
            client.start(settings,'LED circuit',{},[],purpose='plan')
            with self.assertRaises(ValueError): client.start(settings,'again',{},[],purpose='draw')
        self.assertEqual(client._purpose,'plan')
        payload=json.loads(bytes(post.call_args.args[1])); self.assertIn('tasks',payload['messages'][0]['content'])
        reply.finished.emit(); self.assertEqual(completed,[PLAN])
    def test_schema_and_dependencies_reject_commands_and_cycles(self):
        self.assertEqual(decode_plan(json.dumps(PLAN)),PLAN)
        for changed in ({**PLAN,'commands':'DELETE_COMPONENT id=x'}, {**PLAN,'tasks':[{**PLAN['tasks'][0],'depends_on':[1]}]}, {**PLAN,'tasks':[],'questions':[]}):
            with self.assertRaises(ValueError): decode_plan(json.dumps(changed))
    def test_http503_explains_outage_not_bad_key(self):
        text=error_explanation('Practice stopped: http_503','gemini','pl')
        self.assertIn('przeciążona',text); self.assertIn('Spróbuj ponownie',text)
        self.assertNotIn('schemat',text.lower()); self.assertIn('kosztami',text)

class UITests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language='pl',window_mode='windowed',fault_effect='mini'),start_setup=False)
        self.window.show(); APP.processEvents()
    def tearDown(self):
        if getattr(self.window,'command_panel',None): self.window.command_panel.cancel_request()
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()
    def sandbox(self,b):
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); self.window._rebuild_tabs()
        self.window.show_simulation(); APP.processEvents(); return self.window.simulation_window
    def test_multimeter_beeps_on_continuity_and_stops_when_open_or_muted(self):
        b=Bench(); r=b.add('Rezystor','5','Ω'); sim=self.sandbox(b); sim.open_measurements(); panel=sim.measurement_panel
        panel.positive.setCurrentIndex(0); panel.negative.setCurrentIndex(1)
        panel.beep=MagicMock(); panel.mode.setCurrentIndex(panel.mode.findData('continuity')); panel.refresh()
        self.assertIn('Zwarte',panel.reading.text()); self.assertIn('continuity',panel.beep.update.call_args.args[0])
        panel.probes[1].node=None; panel.refresh(); self.assertTrue(panel.beep.stop.called)
        sim.buzzer_sound_button.setChecked(True); panel.continuity_beep(True); self.assertEqual(panel.beep.update.call_args.args[0],{})
        sim.close()
    def test_stale_voltage_history_does_not_block_continuity(self):
        b=Bench(); r=b.add('Rezystor','5','Ω'); sim=self.sandbox(b); sim.open_measurements(); panel=sim.measurement_panel
        panel.positive.setCurrentIndex(0); panel.negative.setCurrentIndex(1)
        panel.history.extend((i*.001,5) for i in range(20)); panel.beep=MagicMock()
        panel.mode.setCurrentIndex(panel.mode.findData('continuity')); panel.refresh(); self.assertIn('Zwarte',panel.reading.text()); sim.close()
    def test_ac_property_fields_follow_selected_mode(self):
        b=Bench(); source=b.add('Źródło napięcia przemiennego','5','V'); dialog=ComponentPropertiesDialog(source,get_definition(source.library_id),'pl',parent=self.window)
        dialog.show(); APP.processEvents(); self.assertFalse(dialog.simulation_fields['sim_voltage_min'].isVisible())
        dialog.simulation_fields['sim_voltage_mode'].setCurrentIndex(1); APP.processEvents()
        self.assertFalse(dialog.value.isVisible()); self.assertTrue(dialog.simulation_fields['sim_voltage_min'].isVisible())
        dialog.reject(); dialog.deleteLater()
    def test_ac_limits_caption_and_hidden_rms_value(self):
        from app.canvas.component_item import ComponentItem
        b=Bench(); source=b.add('Źródło napięcia przemiennego','invalid','V',sim_voltage_mode='limits',sim_voltage_min='-2 V',sim_voltage_max='6 V')
        item=ComponentItem(source); self.assertEqual(item._visible_values(),'-2 V … 6 V')
        dialog=ComponentPropertiesDialog(source,get_definition(source.library_id),'pl',parent=self.window)
        dialog.accept(); self.assertIsNotNone(dialog.values)
    def test_symbol_continuity_tone_is_muted_globally(self):
        b=Bench(); r=b.add('Rezystor','5','Ω'); meter=b.add('Tester ciągłości'); b.connect(r,0,meter,0); b.connect(r,1,meter,1)
        sim=self.sandbox(b)
        with patch('app.ui.buzzer_audio.BuzzerAudio') as audio:
            sim.calculate(single=True)
            self.assertTrue(any(k.startswith('continuity_') for k in audio.return_value.update.call_args.args[0]))
            sim.buzzer_sound_button.setChecked(True); sim.calculate(single=True)
            self.assertEqual(audio.return_value.update.call_args.args[0],{})
        sim.close()
    def test_planner_then_draw_and_clarification_does_not_draw(self):
        settings=self.window.settings; settings.ai_provider='local'; settings.local_ai_model='fixture'; settings.ai_chat_consent=True
        self.window.show_command_panel(); panel=self.window.command_panel; panel.prompt.setPlainText('LED circuit')
        before=deepcopy(self.window.project.to_dict())
        with patch('app.services.assistant_curriculum.read_profile',return_value={'exercises':[{}]*20}),patch('app.ui.ai_cost_dialog.confirm_requests',return_value=True),patch.object(panel.planner,'start') as planner,patch.object(panel.client,'start') as drawer:
            panel.send_request(); self.assertEqual(planner.call_args.kwargs['purpose'],'plan'); self.assertFalse(drawer.called)
            panel.plan_completed(PLAN); self.assertEqual(drawer.call_args.args[2]['task_plan'],PLAN)
            drawer.reset_mock(); panel._phase='plan'; panel.plan_completed({**PLAN,'questions':['What source voltage?']}); self.assertFalse(drawer.called)
        self.assertEqual(before,self.window.project.to_dict()); panel.cancel_request()
    def test_clickable_error_informator(self):
        self.window.show_command_panel(); panel=self.window.command_panel; panel.failed('http_503')
        self.assertIn('href="error"',panel.status.text())
        messages=[]
        with patch('app.ui.command_panel.QMessageBox.exec',lambda box:messages.append(box.informativeText())):
            panel.status.linkActivated.emit('error'); self.assertIn('przeciążona',messages[0])
    def test_scope_display_setting_and_fixed_bounds(self):
        b=Bench(); s,g=b.power(); scope=b.add('Oscyloskop'); b.connect(s,0,scope,0); b.connect(g,0,scope,1)
        self.window.settings.scope_size='huge'; sim=self.sandbox(b); item=sim.scopes[scope.id]
        self.assertEqual(item.scope_rect().width(),800); self.assertEqual(item.scope_rect().height(),440)
        sim.open_measurements(); panel=sim.measurement_panel; panel.mode.setCurrentIndex(panel.mode.findData('wave'))
        panel.volts_div.setValue(2); panel.offset.setValue(1); self.assertEqual(item.scope_bounds,(-3,5)); sim.close()

    def test_failure_setting_can_continue_healthy_islands(self):
        for stop in (True,False):
            b=Bench(); bad=b.add('Bateria','5','V'); limiter=b.add('Rezystor','47','Ω'); led=b.add('Dioda LED 3mm',color='red')
            b.connect(bad,0,limiter,0); b.connect(limiter,1,led,0); b.connect(led,1,bad,1)
            good=b.add('Bateria','12','V'); load=b.add('Rezystor','1','kΩ'); good.y=load.y=900
            b.connect(good,0,load,0); b.connect(load,1,good,1)
            self.window.settings.stop_on_fault=stop; sim=self.sandbox(b); sim.buzzer_sound_button.setChecked(True)
            sim.reload(); self.assertIsNotNone(sim.circuit,sim.log.toPlainText())
            sim.run(); sim.calculate(single=True)
            self.assertEqual(sim.timer.isActive(),not stop,sim.log.toPlainText())
            if not stop: self.assertTrue(sim.circuit.disabled)
            sim.pause(); sim.close(); APP.processEvents()

if __name__=='__main__': unittest.main()
