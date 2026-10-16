import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF,QSettings
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from app.core.models import Project,Sheet,Wire
from app.core.assets import make_asset
from app.core.settings import AppSettings,save_settings,load_settings
from app.ui.paint_case_editor import PaintAssetCaseEditor
from app.ui.main_window import MainWindow
from app.canvas.case_shapes import outline,pin_root
from app.canvas.wire_geometry import stretch,compact_route
from app.services.local_ai import localized_error,answer
from app.services.ai_errors import explanation
from test_simulation_alpha2 import Bench
APP=QApplication.instance() or QApplication([])


class RC8Tests(unittest.TestCase):
    def editor(self):
        b=Bench(); r=b.add('Rezystor','330','Ω'); led=b.add('Dioda LED 3mm',color='red'); button=b.add('Przycisk Tact Switch')
        for i,c in enumerate(b.components): c.x,c.y=200+i*100,300
        b.connect(r,1,led,0); b.connect(led,1,button,0)
        p=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        d=PaintAssetCaseEditor(make_asset(p,p.sheets[0],'LED + przycisk',True),AppSettings(language='pl'))
        d.show(); APP.processEvents(); self.addCleanup(lambda:(d.close(),d.deleteLater(),APP.processEvents()))
        return d,r,led,button

    def test_one_pin_tool_snaps_and_stem_reaches_shell(self):
        d,_,_,_=self.editor(); self.assertGreaterEqual(d.tool.findData('terminal'),0)
        self.assertEqual(d.tool.findData('in'),-1); self.assertEqual(d.tool.findData('out'),-1)
        d.shapes=[dict(kind='rect',rect=[-80,-40,160,80])]; d.add_pin(QPointF(-113.9,11.4),'PIN')
        self.assertEqual((d.pins[0]['x'],d.pins[0]['y']),(-120,20))
        self.assertEqual(pin_root(d.shapes,QPointF(-120,20)),QPointF(-80,20))
        d.move_pin(QPointF(-9000,9000)); self.assertTrue(d.bounds().contains(QPointF(d.pins[0]['x'],d.pins[0]['y'])))

    def test_selection_tool_undo_persistence_and_actual_hit_area(self):
        d,r,led,button=self.editor(); d.shapes=[dict(kind='rect',rect=[-120,-40,240,80])]; d.render()
        d.tool.setCurrentIndex(d.tool.findData('selection')); v=d.view
        for method,p in ((QTest.mousePress,QPointF(-100,-40)),(QTest.mouseRelease,QPointF(100,40))): method(v.viewport(),Qt.MouseButton.LeftButton,pos=v.mapFromScene(p))
        self.assertIsNotNone(d.selection); selected=deepcopy(d.selection); d.undo(); self.assertIsNone(d.selection)
        d.selection=selected; d.add_pin(QPointF(-120,0),'PIN'); d.exports[0]=dict(component=r.id,pin=0,name='PIN1')
        d.regions=[dict(kind='light',component=led.id,rect=[-80,-20,20,20]),
                   dict(kind='interaction',component=button.id,rect=[20,-20,20,20])]
        d.save()
        self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        from app.canvas.component_item import ComponentItem
        p=Project(custom_components=[d.definition]); c=p.new_component(d.definition['id'],400,300); item=ComponentItem(c,custom_components=p.custom_components)
        self.assertFalse(item.shape().contains(QPointF(140,0))); self.assertTrue(item.boundingRect().contains(QPointF(120,0)))
        self.assertEqual(d.definition['asset']['case']['selection_rect'],selected)

    def test_pencil_scribbles_only_form_outer_envelope(self):
        shapes=[dict(kind='rect',rect=[-100,-60,200,120]),dict(kind='path',points=[[-80,-40],[80,40],[-80,40],[80,-40]],closed=False)]
        body,strokes=outline(shapes); self.assertTrue(strokes.isEmpty()); self.assertTrue(body.contains(QPointF(0,0)))
        self.assertEqual(body.boundingRect().width(),200)
        body,_=outline([dict(kind='path',points=[[-80,-40],[80,40],[-80,40],[80,-40]],closed=False)])
        self.assertFalse(body.isEmpty())

    def test_repeated_moves_do_not_grow_diagonal_loops(self):
        points=[[100,100],[200,200],[300,200],[400,300]]
        for i in range(100):
            result=stretch(points,QPointF(100+(i%2)*40,100+(i%3)*20),QPointF(400,300))
            points=[[p.x(),p.y()] for p in result]
            self.assertLessEqual(len(points),8)
            for a,b in zip(result,result[1:]):
                dx,dy=abs(a.x()-b.x()),abs(a.y()-b.y()); self.assertTrue(dx==0 or dy==0 or abs(dx-dy)<.001)
        points=compact_route([QPointF(0,0),QPointF(100,100),QPointF(0,100),QPointF(100,0),QPointF(200,0)])
        self.assertLess(len(points),5); self.assertEqual(points[0],QPointF(0,0)); self.assertEqual(points[-1],QPointF(200,0))

    def test_real_asset_light_and_button_with_actual_circuit(self):
        d,r,led,button=self.editor(); d.shapes=[dict(kind='rect',rect=[-160,-60,320,120])]; d.render()
        d.selection=[-160,-60,320,120]
        d.regions=[dict(kind='light',component=None,rect=[-90,-20,30,30]),dict(kind='interaction',component=None,rect=[-20,-20,40,40])]
        for index,(kind,target) in enumerate((('light',led),('interaction',button))):
            rect=d.regions[index]['rect']; anchor=QPointF(rect[0]+rect[2]/2,rect[1]+rect[3]/2)
            d.connect_at(anchor)
            self.assertIsNotNone(d.connect_preview)
            target_rect=next(rect for cid,rect in d.component_bounds if cid==target.id)
            d.connect_at(target_rect.center())
            self.assertEqual(d.regions[index]['component'],target.id)
            self.assertIn('link_line',d.regions[index])
        for x,c,pin in ((-160,r,0),(160,button,1)):
            d.add_pin(QPointF(x,0),'PIN'); d.exports[-1]=dict(component=c.id,pin=pin,name='PIN'+str(len(d.pins)))
        d.save(); self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        b=Bench(); source=b.add('Bateria 9V','5','V'); source.x,source.y=200,300
        p=Project(sheets=[Sheet(components=b.components)],custom_components=[d.definition]); case=p.new_component(d.definition['id'],500,300); p.sheets[0].components.append(case)
        from app.libraries.built_in import get_instance_definition
        for i,pin in enumerate(get_instance_definition(source).pins):
            port=d.pins[i]; p.sheets[0].wires.append(Wire(source.x+pin.x,source.y+pin.y,case.x+port['x'],case.y+port['y'],start_component_id=source.id,start_pin_index=i,end_component_id=case.id,end_pin_index=i))
        w=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False)
        try:
            w.project=p; w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window; shell=sim.asset_cases[case.id]
            self.assertIsNotNone(sim.circuit); sim.single_step(); off=sim.circuit.result.brightness.get(shell.targets[led.id],0)
            sim.view.fitInView(sim.scene.itemsBoundingRect()); APP.processEvents(); point=sim.view.mapFromScene(shell.mapToScene(QPointF(0,0)))
            QTest.mousePress(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
            device=next(dev for dev in sim.circuit.devices if dev.component.id==shell.targets[button.id]); self.assertTrue(device.closed)
            self.assertGreater(shell.result.brightness.get(shell.targets[led.id],0),off)
            QTest.mouseRelease(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=point); self.assertFalse(device.closed)
            self.assertEqual(shell.result,sim.circuit.result)
        finally:
            if w.simulation_window: w.simulation_window.close()
            w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); w.deleteLater(); APP.processEvents()

    def test_local_auth_error_keeps_code_and_explanation(self):
        message='Practice stopped. Local AI request failed (HTTP 401). Start the local server and check the installed model.'
        localized=localized_error(message,'pl'); self.assertIn('401',localized); self.assertIn('token',localized)
        self.assertIn('Manage Tokens',explanation(localized,'local','pl'))
        with self.assertRaisesRegex(ValueError,'endpoint'): answer({'error':'Unexpected endpoint'})

    def test_local_token_protected_storage_and_repr(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as folder,patch('app.core.settings._dpapi',side_effect=lambda b,**kw:b[::-1]):
            store=QSettings(str(Path(folder)/'test.ini'),QSettings.Format.IniFormat); settings=AppSettings(local_ai_token='test-token')
            save_settings(settings,store); store.sync(); self.assertNotIn('test-token',repr(settings))
            self.assertNotIn('local_ai_token',store.allKeys()); self.assertEqual(load_settings(store).local_ai_token,'test-token')

    def test_local_token_header_only_and_copy_error(self):
        from app.services.assistant_client import AssistantClient
        from test_ai_settings import FakeReply
        client=AssistantClient(); reply=FakeReply()
        settings=AppSettings(ai_provider='local',local_ai_model='fixture',local_ai_token='local-secret',api_key='cloud-secret')
        with patch.object(client.network,'post',return_value=reply) as post,patch('app.services.assistant_curriculum.remembered_knowledge',return_value=[]):
            client.start(settings,'test',{},[])
        request,payload=post.call_args.args
        self.assertEqual(bytes(request.rawHeader('Authorization')),b'Bearer local-secret')
        self.assertNotIn(b'local-secret',bytes(payload)); self.assertNotIn(b'cloud-secret',bytes(payload)); client.cancel()
        from app.ui.command_panel import CommandPanel
        w=MainWindow(AppSettings(language='pl',ai_provider='local'),start_setup=False)
        try:
            panel=CommandPanel(w); panel.failed('Local AI request failed (HTTP 401).'); panel.copy_error()
            self.assertIn('401',APP.clipboard().text()); self.assertEqual(APP.clipboard().text(),panel.last_error)
        finally:
            w._saved_state=w.project.to_dict(); w.close(); w.deleteLater(); APP.processEvents()

    def test_cable_plugs_stay_inside_drawing_area(self):
        from app.canvas.page import drawing_contains,title_block_rect
        from PySide6.QtGui import QTransform
        b=Bench(); cable=b.add('Kabel USB'); cable.x,cable.y=400,300
        w=MainWindow(AppSettings(language='pl'),start_setup=False)
        try:
            w.project=Project(sheets=[Sheet(components=b.components)]); w._rebuild_tabs(); view=w._current_view(); plug=view.cable_layer.usb_cables[0].plugs[0]
            for point in (QPointF(-300,-300),title_block_rect(view._sheet).center(),QPointF(9999,9999)):
                plug.setPos(point)
                bounds=QTransform().rotate(plug.rotation()).mapRect(plug.boundingRect()).translated(plug.pos())
                self.assertTrue(drawing_contains(view._sheet,bounds))
        finally:
            w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); w.deleteLater(); APP.processEvents()
