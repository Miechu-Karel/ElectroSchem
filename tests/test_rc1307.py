import unittest
from copy import deepcopy
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QImage,QPainter,QColor,QPen
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from app.core.models import Project,Sheet,Wire
from app.core.settings import AppSettings
from app.core.assets import make_asset
from app.canvas.case_shapes import outline
from app.ui.paint_case_editor import PaintAssetCaseEditor
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench
APP=QApplication.instance() or QApplication([])

class RC7Tests(unittest.TestCase):
    def test_region_drawing_target_persistence_and_undo(self):
        d=self.editor(); d.tool.setCurrentIndex(d.tool.findData('light')); v=d.view
        QTest.mousePress(v.viewport(),Qt.MouseButton.LeftButton,pos=v.mapFromScene(QPointF(-40,-20)))
        QTest.mouseMove(v.viewport(),v.mapFromScene(QPointF(10,20)))
        QTest.mouseRelease(v.viewport(),Qt.MouseButton.LeftButton,pos=v.mapFromScene(QPointF(10,20)))
        self.assertEqual(len(d.regions),1); self.assertEqual(d.regions[0]['component'],d.source.sheets[0].components[0].id)
        before=deepcopy(d.regions); d.undo(); self.assertFalse(d.regions)
        d.regions=before; d.shapes=[dict(kind='rect',rect=[-100,-50,200,100])]; d.render()
        d.add_pin(QPointF(0,0),'IN'); d.connect_at(QPointF(0,0)); d.connect_at(d.internal_pins[0][0]); d.save()
        self.assertEqual(d.definition['asset']['case']['regions'],before)
    def test_shell_light_and_momentary_interaction_forward_to_internal_part(self):
        from types import SimpleNamespace
        from app.core.assets import instantiate
        from app.ui.asset_shells import CaseShell
        from app.ui.simulation_window import LiveSymbol
        from PySide6.QtWidgets import QGraphicsScene,QGraphicsView
        b=Bench(); button=b.add('Przycisk Tact Switch'); button.x,button.y=300,300
        p=Project(sheets=[Sheet(components=b.components)]); d=make_asset(p,p.sheets[0],'Button',True)
        d['asset']['case']=dict(scale=.5,shapes=[dict(kind='rect',rect=[-160,-60,320,120])],regions=[dict(kind='interaction',component=button.id,rect=[-20,-20,40,40]),dict(kind='light',component=button.id,rect=[-70,-20,30,30])])
        p.custom_components=[d]; instance=p.new_component(d['id'],300,300); contents,_=instantiate(d['asset'],instance); target=contents.components[0]; held=[]
        live=LiveSymbol(target,held=lambda cid,name,value:held.append(value))
        window=SimpleNamespace(custom=[d],pl=True,symbols={target.id:live}); shell=CaseShell(window,instance,contents,d)
        scene=QGraphicsScene(); scene.addItem(shell); view=QGraphicsView(scene); view.resize(600,400); view.show(); view.fitInView(scene.itemsBoundingRect()); APP.processEvents()
        point=view.mapFromScene(shell.mapToScene(QPointF(0,0)))
        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=point); self.assertEqual(held,[True])
        QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=point); self.assertEqual(held,[True,False])
        shell.result=SimpleNamespace(brightness={target.id:1.})
        image=QImage(400,240,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.black); painter=QPainter(image); painter.translate(200,120); shell.paint(painter,None); painter.end()
        self.assertGreater(image.pixelColor(145,115).red(),150)
        view.close(); view.deleteLater(); APP.processEvents()
    def editor(self):
        b=Bench(); r=b.add('Rezystor','330','Ω'); r.x,r.y=300,300
        p=Project(sheets=[Sheet(components=b.components)])
        d=PaintAssetCaseEditor(make_asset(p,p.sheets[0],'Case',True,{r.id}),AppSettings(language='pl')); d.show(); APP.processEvents()
        self.addCleanup(lambda:(d.close(),d.deleteLater(),APP.processEvents()))
        return d
    def drag(self,d,tool,shift=False):
        d.tool.setCurrentIndex(d.tool.findData(tool)); v=d.view
        if shift: QTest.keyPress(v,Qt.Key.Key_Shift)
        mods=Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
        QTest.mousePress(v.viewport(),Qt.MouseButton.LeftButton,mods,v.mapFromScene(QPointF(-100,-40)))
        QTest.mouseMove(v.viewport(),v.mapFromScene(QPointF(80,30)))
        QTest.mouseRelease(v.viewport(),Qt.MouseButton.LeftButton,mods,v.mapFromScene(QPointF(80,30)))
        if shift: QTest.keyRelease(v,Qt.Key.Key_Shift)
        APP.processEvents(); return d.shapes[-1]['rect']
    def test_shift_square_and_circle_otherwise_rectangle_and_ellipse(self):
        d=self.editor()
        for tool in ('rect','circle'):
            r=self.drag(d,tool); self.assertNotAlmostEqual(r[2],r[3])
            r=self.drag(d,tool,True); self.assertAlmostEqual(r[2],r[3])
    def test_free_pin_position_save_reload_and_resize(self):
        d=self.editor(); d.shapes=[dict(kind='rect',rect=[-100,-50,200,100])]; d.render()
        d.add_pin(QPointF(35.5,12.25),'IN'); d.add_pin(QPointF(-63.25,10.5),'OUT')
        for i in range(2):
            pin=d.pins[i]; d.connect_at(QPointF(pin['x'],pin['y'])); d.connect_at(d.internal_pins[i][0])
        d.save(); self.assertEqual(d.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(d.definition['pins'][0]['x'],40); self.assertEqual(d.definition['pins'][0]['y'],20); self.assertTrue(d.definition['asset']['case']['free_pins'])
        again=PaintAssetCaseEditor(d.definition,AppSettings()); self.assertEqual(again.pins,d.pins); again.deleteLater()
        d.width.setValue(640); self.assertEqual(d.pins[0]['x'],80.); d.undo(); self.assertEqual(d.pins[0]['x'],40)
    def test_overlapping_primitives_have_no_internal_outline(self):
        body,strokes=outline([dict(kind='rect',rect=[-100,-60,130,120]),dict(kind='circle',rect=[-30,-60,120,120])])
        self.assertTrue(body.contains(QPointF(30,0))); self.assertTrue(strokes.isEmpty())
        image=QImage(400,240,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.white)
        painter=QPainter(image); painter.translate(200,120); painter.setPen(QPen(Qt.GlobalColor.black,2)); painter.setBrush(Qt.GlobalColor.white); painter.drawPath(body); painter.end()
        self.assertEqual(image.pixelColor(230,120),QColor('white'))
    def test_case_stays_visible_in_simulation_with_expanded_solver(self):
        d=self.editor(); d.shapes=[dict(kind='rect',rect=[-100,-50,200,100])]; d.render()
        d.add_pin(QPointF(-100,0),'IN'); d.add_pin(QPointF(100,0),'OUT')
        for i in range(2):
            pin=d.pins[i]; d.connect_at(QPointF(pin['x'],pin['y'])); d.connect_at(d.internal_pins[i][0])
        d.save(); definition=d.definition; b=Bench(); source=b.add('Bateria 9V','5','V'); source.x,source.y=200,300
        p=Project(sheets=[Sheet(components=b.components)],custom_components=[definition]); case=p.new_component(definition['id'],500,300); p.sheets[0].components.append(case)
        from app.libraries.built_in import get_instance_definition
        spec=get_instance_definition(source)
        for i in range(2):
            pin=spec.pins[i]; port=definition['pins'][i]
            p.sheets[0].wires.append(Wire(source.x+pin.x,source.y+pin.y,case.x+port['x'],case.y+port['y'],start_component_id=source.id,start_pin_index=i,end_component_id=case.id,end_pin_index=i))
        w=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False)
        try:
            w.project=p; w._rebuild_tabs(); w.show_simulation(); sim=w.simulation_window
            self.assertIn(case.id,sim.asset_cases); self.assertTrue(sim.asset_cases[case.id].isVisible()); self.assertIsNotNone(sim.circuit)
            self.assertTrue(sim.hidden_asset_contents)
            for cid in sim.hidden_asset_contents: self.assertFalse(sim.symbols[cid].isVisible())
            before=sim.circuit.time; sim.circuit.step(.001); self.assertGreater(sim.circuit.time,before)
        finally:
            if w.simulation_window: w.simulation_window.close()
            w._sync_positions(); w._saved_state=w.project.to_dict(); w.close(); w.deleteLater(); APP.processEvents()
