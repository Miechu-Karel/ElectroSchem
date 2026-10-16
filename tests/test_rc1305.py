import unittest
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF,QSettings
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from app.core.models import Project,Sheet
from app.core.assets import make_asset,validate_asset
from app.core.settings import AppSettings
from app.ui.asset_case_editor import AssetCaseEditor
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench
APP=QApplication.instance() or QApplication([])

class RC5Tests(unittest.TestCase):
    def test_moving_ai_part_preserves_waypoints_and_network(self):
        from app.core.editor_commands import execute_batch
        from app.services.power_recipe import commands
        from app.canvas.schematic_view import SchematicView
        from app.ui.ai_preview import connectivity
        p=execute_batch(Project(sheets=[Sheet(paper_size='A3')]),0,commands())
        view=SchematicView(project=p,sheet=p.sheets[0],settings=AppSettings())
        try:
            before=connectivity(p,0); ids={w.id for w in p.sheets[0].wires}
            c=next(c for c in p.sheets[0].components if c.reference=='CV2')
            item=view._component_items[c.id]; item.setSelected(True)
            untouched={w.id:deepcopy(w.points) for w in p.sheets[0].wires if c.id not in (w.start_component_id,w.end_component_id)}
            view._begin_selection_group(item.pos()); self.assertTrue(view._move_selection_group(QPointF(20,20)))
            view._group_drag=None
            self.assertEqual(connectivity(p,0),before)
            for w in p.sheets[0].wires:
                if w.id in untouched: self.assertEqual(w.points,untouched[w.id])
                for a,b in zip(w.points,w.points[1:]): self.assertTrue(a[0]==b[0] or a[1]==b[1])
            view.rotate_selected_components()
            self.assertEqual(connectivity(p,0),before); self.assertEqual({w.id for w in p.sheets[0].wires},ids)
        finally:
            view.deleteLater(); APP.processEvents()
    def test_fanout_routes_remain_orthogonal(self):
        from app.core.editor_commands import execute_batch
        from app.services.power_recipe import commands
        p=execute_batch(Project(sheets=[Sheet(paper_size='A3')]),0,commands())
        for wire in p.sheets[0].wires:
            for a,b in zip(wire.points,wire.points[1:]):
                self.assertTrue(a[0]==b[0] or a[1]==b[1],wire.points)
    def test_case_editor_preserves_network_and_saves_shapes_and_ports(self):
        b=Bench(); r=b.add('Rezystor','330','Ω'); r.x,r.y=300,300
        p=Project(sheets=[Sheet(components=b.components)])
        definition=make_asset(p,p.sheets[0],'Case',boxed=True,selected={r.id})
        dialog=AssetCaseEditor(definition,AppSettings(language='pl'))
        before=deepcopy(dialog.definition['asset']['sheet'])
        dialog.shapes=[dict(kind='circle',rect=[-60,-60,120,120])]
        dialog.port.setCurrentIndex(0); dialog.move_pin(QPointF(0,-60))
        dialog.scale.setValue(25); dialog.save()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.definition['asset']['sheet'],before)
        self.assertEqual(dialog.definition['asset']['case']['scale'],.25)
        self.assertEqual(dialog.definition['pins'][0]['y'],-60)
        from app.canvas.component_item import ComponentItem
        p.custom_components.append(dialog.definition)
        instance=p.new_component(dialog.definition['id'],300,300)
        item=ComponentItem(instance,custom_components=[dialog.definition]); self.assertTrue(item.asset_case)
        dialog.deleteLater(); APP.processEvents()
    def test_case_payload_rejects_nonfinite_and_executable_data(self):
        b=Bench(); b.add('Rezystor'); p=Project(sheets=[Sheet(components=b.components)])
        asset=make_asset(p,p.sheets[0],'Case')['asset']
        for shape in (dict(kind='script',rect=[0,0,20,20]),dict(kind='rect',rect=[0,0,float('inf'),20])):
            with self.assertRaises(ValueError): validate_asset(dict(asset,case={'scale':.5,'shapes':[shape]}))
    def test_selection_required_and_peek_is_held_not_destructive(self):
        window=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False)
        try:
            with patch.object(window,'_error') as error,patch('app.ui.main_window.QInputDialog.getText') as ask:
                window.save_as_asset(); error.assert_called_once(); ask.assert_not_called()
            view=window._current_view(); before=window.project.to_dict()
            QTest.keyPress(view,Qt.Key.Key_S,Qt.KeyboardModifier.ShiftModifier); self.assertTrue(view._show_hidden_wires)
            QTest.keyRelease(view,Qt.Key.Key_S,Qt.KeyboardModifier.ShiftModifier); self.assertFalse(view._show_hidden_wires)
            self.assertEqual(window.project.to_dict(),before)
        finally:
            window._saved_state=window.project.to_dict(); window.close(); window.deleteLater(); APP.processEvents()

if __name__=='__main__': unittest.main()
