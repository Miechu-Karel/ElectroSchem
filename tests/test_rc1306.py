import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from app.ui.paint_case_editor import PaintAssetCaseEditor
from app.core.models import Project,Sheet
from app.core.assets import make_asset,expand_assets
from app.core.settings import AppSettings
from app.canvas.wire_geometry import stretch
from test_simulation_alpha2 import Bench
APP=QApplication.instance() or QApplication([])

class RC6Tests(unittest.TestCase):
    def setUp(self):
        b=Bench(); self.r=b.add('Rezystor','330','Ω'); self.r.x,self.r.y=300,300
        self.p=Project(sheets=[Sheet(components=b.components)])
        self.d=PaintAssetCaseEditor(make_asset(self.p,self.p.sheets[0],'Case',True,{self.r.id}),AppSettings(language='pl'))
        self.d.show(); APP.processEvents()
    def tearDown(self): self.d.close(); self.d.deleteLater(); APP.processEvents()
    def tool(self,key): self.d.tool.setCurrentIndex(self.d.tool.findData(key))
    def click(self,p): QTest.mouseClick(self.d.view.viewport(),Qt.MouseButton.LeftButton,pos=self.d.view.mapFromScene(p)); APP.processEvents()
    def drag(self,a,b,modifier=Qt.KeyboardModifier.NoModifier):
        v=self.d.view; QTest.mousePress(v.viewport(),Qt.MouseButton.LeftButton,modifier,v.mapFromScene(a)); QTest.mouseMove(v.viewport(),v.mapFromScene(b)); QTest.mouseRelease(v.viewport(),Qt.MouseButton.LeftButton,modifier,v.mapFromScene(b)); APP.processEvents()
    def test_actual_pencil_shift_rectangle_and_ctrl_z(self):
        self.assertFalse(self.d.pins)
        self.tool('pencil'); self.drag(QPointF(-100,-30),QPointF(80,40),Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.d.shapes[0]['kind'],'path'); self.assertEqual(len(self.d.shapes[0]['points']),2)
        QTest.keyClick(self.d.view,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier); APP.processEvents(); self.assertFalse(self.d.shapes)
        self.tool('rect'); self.drag(QPointF(-140,-40),QPointF(140,40)); self.assertEqual(self.d.shapes[0]['kind'],'rect')
        self.tool('erase'); self.click(QPointF(0,0)); self.assertFalse(self.d.shapes); self.d.undo(); self.assertEqual(len(self.d.shapes),1)
    def test_new_ports_manual_connections_save_reload_and_expansion(self):
        self.d.shapes=[dict(kind='rect',rect=[-160,-60,320,120])]; self.d.render(); original=deepcopy(self.d.source.to_dict())
        self.tool('terminal'); self.click(QPointF(-160,0)); self.click(QPointF(160,0))
        self.tool('connect')
        for i in range(2):
            pin=self.d.pins[i]; self.click(QPointF(pin['x'],pin['y'])); self.click(self.d.internal_pins[i][0])
        self.assertFalse(any(p['component'] is None for p in self.d.exports)); self.d.save(); self.assertEqual(self.d.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(self.d.source.to_dict(),original)
        definition=self.d.definition; self.p.custom_components=[definition]; instance=self.p.new_component(definition['id'],500,400); self.p.sheets[0].components=[instance]
        expanded=expand_assets(self.p.sheets[0],[definition]); self.assertEqual(len(expanded.components),1); self.assertEqual(expanded.components[0].value,'330')
        again=PaintAssetCaseEditor(definition,AppSettings()); self.assertEqual(again.exports,self.d.exports); self.assertEqual(again.shapes,self.d.shapes); again.deleteLater()
    def test_unconnected_port_blocked_and_resize_undo(self):
        self.d.shapes=[dict(kind='rect',rect=[-160,-60,320,120])]; self.d.render(); self.d.add_pin(QPointF(-160,0),'IN')
        with patch('app.ui.paint_case_editor.QMessageBox.warning') as warning: self.d.save(); warning.assert_called_once()
        self.assertNotEqual(self.d.result(),QDialog.DialogCode.Accepted)
        before=self.d.snapshot(); self.d.width.setValue(400); self.assertEqual(self.d.pins[0]['x'],-200); self.d.undo(); self.assertEqual(self.d.snapshot(),before)
    def test_legacy_diagonal_bends_stay_at_45_degrees(self):
        for points in ([[100,100],[200,200]],[[100,100],[200,200],[300,200],[400,300]]):
            result=stretch(points,QPointF(120,140),QPointF(*points[-1]))
            for a,b in zip(result,result[1:]):
                dx,dy=abs(a.x()-b.x()),abs(a.y()-b.y()); self.assertTrue(dx==0 or dy==0 or abs(dx-dy)<.001)
    def test_new_drawing_paths_reject_nonfinite_data(self):
        from app.core.assets import validate_asset
        asset=deepcopy(self.d.definition['asset']); asset['case']=dict(scale=.5,shapes=[dict(kind='path',points=[[0,0],[float('nan'),2]])])
        with self.assertRaises(ValueError): validate_asset(asset)
