"""Alpha9 tests: local transport is mocked; no model/API calls."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import Qt,QRectF
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtTest import QTest
from app.core.settings import AppSettings
from app.core.models import Project,Sheet
from app.libraries.alpha139_parts import SPECS
from app.libraries.built_in import get_definition,AVAILABLE_ITEMS
from app.libraries.simulation_catalog import behavior_for
from app.simulation.alpha139_ic import linearize
from app.canvas.component_item import ComponentItem
from app.canvas.connector_art import socket_regions
from app.services.local_ai import endpoint,body,answer
from app.services.assistant_client import AssistantClient
from app.ui.settings_dialog import SettingsDialog
from app.ui.main_window import MainWindow
from test_ai_settings import FakeReply
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])

class CatalogTests(unittest.TestCase):
    def test_packages_and_protocol_limits(self):
        self.assertEqual(len(SPECS),30)
        for chip,(pins,_,_,function) in SPECS.items():
            d=next(d for d in AVAILABLE_ITEMS if d.name=='Układ Scalony '+chip)
            self.assertEqual([p.name for p in d.pins],pins.split('|'))
            model=behavior_for(d); self.assertEqual(model.kind,'catalog_ic')
            if function=='protocol': self.assertIn('NIE',model.note_pl)
        self.assertFalse(any(d.name=='Układ Scalony NE56' for d in AVAILABLE_ITEMS))

    def test_every_package_steps_without_missing_model(self):
        for chip in SPECS:
            with self.subTest(chip=chip):
                b=Bench(); s,g=b.power(); ic=b.add('Układ Scalony '+chip)
                names=SPECS[chip][0].split('|')
                low=next((x for x in ('GND','VSS','COM','PGND','V−') if x in names),None)
                high=next((x for x in ('VCC','VDD','VIN','VBAT','V+') if x in names),None)
                if not high: high='IN' if 'IN' in names else 'COM'
                b.connect(ic,high,s,0); b.connect(ic,low,g,0)
                result=b.circuit().step(); self.assertFalse(result.faults)
                self.assertIn(ic.id,result.readings)

    def fake(self,chip,levels=None,state=None):
        labels=SPECS[chip][0].split('|'); n={p:i+1 for i,p in enumerate(labels)}
        values={node:0 for node in n.values()}
        for label in ('VCC','VDD','V+'):
            if label in n: values[n[label]]=5
        for label,value in (levels or {}).items(): values[n[label]]=value
        d=SimpleNamespace(parameters={'name':'Układ Scalony '+chip,'pins':n,'sim_load_current':.001,'sim_gain':20},nodes=list(n.values()),state=state or {})
        branches,trial=linearize(d,values,0,0,.001)
        def driven(label):
            output=[b for b in branches if b.a==n[label] and b.g>.001]
            return values.get(output[-1].b,0)-output[-1].offset/output[-1].g
        return driven,trial

    def test_nand_decoder_and_latches(self):
        drive,_=self.fake('CD4011',{'1A':5,'1B':5}); self.assertEqual(drive('1Y'),0)
        drive,_=self.fake('CD4011',{'1A':5}); self.assertEqual(drive('1Y'),5)
        drive,_=self.fake('74HC138',{'G1':5,'A':5}); self.assertEqual(drive('/Y1'),0); self.assertEqual(drive('/Y0'),5)
        drive,state=self.fake('CD4017',{'CLK':5},{'count':2,'clock':False}); self.assertEqual(state['count'],3); self.assertEqual(drive('Q3'),5)
        _,state=self.fake('CD4017',{'CLK':5},{'count':2,'clock':True}); self.assertEqual(state['count'],2)
        drive,state=self.fake('74HC165',{'H':5}); self.assertEqual(state['shift'],128); self.assertEqual(drive('QH'),5)
        drive,_=self.fake('CD4511',{'/BI':5,'/LT':5,'A':5}); self.assertEqual(drive('b'),5); self.assertEqual(drive('a'),0)

    def test_switch_can_disable_off(self):
        from app.simulation.extended import linearize as switch_model
        d=SimpleNamespace(kind='multi_switch',parameters={'pins':{'COM':1,'1':2,'2':3},'sim_outputs':'2','sim_position':'0','sim_allow_off':'false'},state={})
        branches,_=switch_model(d,{1:0,2:0,3:0},0,0,.001)
        self.assertGreater(branches[0].g,1); self.assertLess(branches[1].g,1e-6)
        d.parameters['sim_allow_off']='true'
        branches,_=switch_model(d,{},0,0,.001); self.assertTrue(all(b.g<1e-6 for b in branches))

class LocalTests(unittest.TestCase):
    def test_loopback_only_and_untrusted_response(self):
        for url in ('http://127.0.0.1:11434/v1','http://localhost:1234','http://[::1]:1234/v1/'):
            self.assertTrue(endpoint(url).endswith('/v1/chat/completions'))
        for url in ('https://api.openai.com/v1','http://localhost.evil/v1','file:///x','http://user:pass@localhost/v1','http://localhost/v1?key=x'):
            with self.assertRaises(ValueError): endpoint(url)
        for result in (None,[],{'choices':[None]},{'choices':[{'message':None}]},{'choices':[{'finish_reason':'length','message':{'content':'x'}}]}):
            with self.assertRaises(ValueError): answer(result)
        self.assertEqual(body('model','rules','context')['model'],'model')

    def test_local_transport_has_no_cloud_key_and_rejects_redirect(self):
        class Reply(FakeReply):
            def readAll(self): return self.read(len(self.body))
        for status in (200,302):
            client=AssistantClient(); completed=[]; errors=[]
            client.completed.connect(completed.append); client.failed.connect(errors.append)
            text=json.dumps({'summary':'Offline fixture','commands':''})
            reply=Reply(status=status,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':text}}]}).encode())
            settings=AppSettings(ai_provider='local',local_ai_model='test-model',api_key='SECRET',openai_api_key='SECRET')
            with patch.object(client.network,'post',return_value=reply) as post,patch('app.services.assistant_curriculum.remembered_knowledge',return_value=[]):
                client.start(settings,'hello',{},[])
            request,payload=post.call_args.args
            self.assertEqual(bytes(request.rawHeader('Authorization')),b'')
            self.assertNotIn(b'SECRET',bytes(payload))
            self.assertEqual(request.attribute(QNetworkRequest.Attribute.RedirectPolicyAttribute),QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            reply.finished.emit()
            self.assertEqual(bool(completed),status==200); self.assertEqual(bool(errors),status!=200)

    def test_local_settings_hides_cloud_keys(self):
        dialog=SettingsDialog(AppSettings(ai_provider='local',local_ai_model='test-model'))
        dialog.settings_tabs.setCurrentIndex(2); dialog.show(); APP.processEvents()
        self.assertEqual(dialog.provider.currentData(),'local')
        self.assertFalse(dialog.key.isVisible()); self.assertTrue(dialog.local_url.isVisible())
        dialog.provider.setCurrentIndex(dialog.provider.findData('gemini')); APP.processEvents()
        self.assertTrue(dialog.key.isVisible()); self.assertFalse(dialog.local_url.isVisible())
        dialog.reject(); dialog.deleteLater()

class UITests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False)
    def tearDown(self):
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict()
        self.window.close(); self.window.deleteLater(); APP.processEvents()
    def test_usb_socket_is_opposite_pins(self):
        b=Bench()
        for name,top in (('Port USB A',True),('Port USB C',False)):
            c=b.add(name); item=ComponentItem(c,get_definition(c.library_id))
            body=QRectF(-item.definition.width/2,-item.definition.height/2,item.definition.width,item.definition.height)
            region=socket_regions(item,body)[0][1]
            self.assertTrue(region.bottom()<body.top() if top else region.top()>body.bottom())
            self.assertTrue(item.boundingRect().contains(region))
    def test_e_holds_tactile_until_release(self):
        b=Bench(); s,g=b.power(); button=b.add('Przycisk Tact Switch'); r=b.add('Rezystor','1','kΩ')
        b.connect(s,0,button,0); b.connect(button,2,r,0); b.connect(r,1,g,0)
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        self.window._rebuild_tabs(); self.window.show(); self.window.show_simulation(); APP.processEvents()
        sim=self.window.simulation_window; item=sim.symbols[button.id]; item.setSelected(True)
        sim.view.setFocus(); APP.processEvents()
        QTest.keyPress(sim.view,Qt.Key.Key_E)
        self.assertEqual(item.component.properties['sim_closed'],'true')
        QTest.keyRelease(sim.view,Qt.Key.Key_E)
        self.assertEqual(item.component.properties['sim_closed'],'false')
        sim.close()
    def test_regeneration_replaces_not_duplicates_proposal(self):
        self.window.show_command_panel(); panel=self.window.command_panel; panel.prepare()
        base=deepcopy(panel.session.working.to_dict())
        resistor=next(d for d in AVAILABLE_ITEMS if d.name=='Rezystor')
        panel.request_snapshot={'working':base,'history':[],'report':None,'prompt':'fixture'}
        response={'summary':'Fixture','commands':f'ADD_COMPONENT type={resistor.id} id=R1 x=200 y=200'}
        panel.completed(response); panel.completed(response)
        self.assertEqual(len(panel.session.working.sheets[0].components),1)
        self.assertEqual(len(self.window.project.sheets[0].components),0)
        panel.reject()

    def test_regenerate_reuses_original_prompt_and_context(self):
        self.window.settings.ai_provider='local'; self.window.settings.local_ai_model='fixture'; self.window.settings.ai_chat_consent=True
        self.window.show_command_panel(); panel=self.window.command_panel; panel.prepare()
        snapshot={'working':panel.session.working.to_dict(),'history':[],'report':None,'prompt':'Original prompt'}
        panel.last_request=deepcopy(snapshot)
        with patch('app.services.assistant_curriculum.read_profile',return_value={'exercises':[{}]*20}),patch('app.ui.ai_cost_dialog.confirm_requests',return_value=True),patch.object(panel.planner,'start') as start:
            panel.regenerate_response()
        self.assertEqual(start.call_args.args[1],'Original prompt')
        self.assertEqual(start.call_args.args[2]['sheet'],snapshot['working']['sheets'][0])
        panel.cancel_request(); panel.reject()

if __name__=='__main__': unittest.main()
