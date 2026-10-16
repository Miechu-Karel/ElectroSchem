"""RC1 regression: real menu paths, cable-only contacts, breadboard, inline scope."""
import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMenu
from PySide6.QtCore import QPointF
from app.core.models import Project,Sheet,Wire
from app.core.settings import AppSettings
from app.core.cable_connections import attach
from app.core.editor_commands import execute_batch
from app.libraries.built_in import AVAILABLE_ITEMS,get_definition
from app.simulation.netlist import build_netlist
from app.services.power_requirements import requirements,validate_plan
from app.ui.main_window import MainWindow
from test_simulation_alpha2 import Bench
from test_alpha1310 import PLAN
APP=QApplication.instance() or QApplication([])

class ElectricalTests(unittest.TestCase):
    def test_breadboard_internal_groups_and_trench(self):
        b=Bench(); board=b.add('Płytka stykowa'); net=build_netlist(Sheet(components=b.components))
        definition=get_definition(board.library_id)
        def node(label): return net.pins[board.id,next(i for i,p in enumerate(definition.pins) if p.name==label)]
        self.assertEqual(node('L1.1'),node('L1.5')); self.assertNotEqual(node('L1.1'),node('L2.1'))
        self.assertNotEqual(node('L1.1'),node('R1.1')); self.assertEqual(node('RL.1'),node('RL.10')); self.assertNotEqual(node('RL.1'),node('RR.1'))
    def test_hole_attachments_and_gender_and_occupancy(self):
        b=Bench(); board=b.add('Płytka stykowa'); male=b.add('Goldpin'); cable=b.add('Kabel Męsko-Żeński')
        sheet=Sheet(components=b.components); attach(sheet,cable,'A',board,2); attach(sheet,cable,'B',male)
        net=build_netlist(sheet); self.assertEqual(net.pins[board.id,2],net.pins[male.id,1])
        other=b.add('Kabel Męsko-Męski'); sheet.components=b.components
        attach(sheet,other,'A',board,10)
        with self.assertRaisesRegex(ValueError,'occupied'): attach(sheet,other,'B',board,2)
        with self.assertRaises(ValueError): attach(sheet,cable,'B',board,11)
    def test_drawn_anchor_to_plug_contact_rejected(self):
        b=Bench(); male=b.add('Goldpin'); r=b.add('Rezystor','100','Ω'); b.connect(male,0,r,0)
        # Explicit anchors in existing ELS remain compatible; new commands do not.
        build_netlist(Sheet(components=b.components,wires=b.wires))
        male.x,male.y=300,300; r.x,r.y=700,300; male.reference='J1'; r.reference='R1'
        with self.assertRaisesRegex(ValueError,'cables only'):
            execute_batch(Project(sheets=[Sheet(components=b.components)]),0,'CONNECT from=J1 to=R1 from_pin=0 to_pin=0')
        b.wires=[]; b.connect(male,1,r,0); build_netlist(Sheet(components=b.components,wires=b.wires))
    def test_coincident_free_wire_cannot_contact_reserved_top(self):
        b=Bench(); male=b.add('Goldpin'); wire=Wire(male.x-40,male.y,male.x-100,male.y)
        net=build_netlist(Sheet(components=b.components,wires=[wire])); self.assertNotEqual(net.pins[male.id,0],net.wires[wire.id])
    def test_command_cable_attachment(self):
        ids={d.name:d.id for d in AVAILABLE_ITEMS}
        commands=f'ADD_COMPONENT type={ids["Goldpin"]} id=J1 x=300 y=300\nADD_COMPONENT type={ids["Goldpin"]} id=J2 x=700 y=300\nADD_COMPONENT type={ids["Kabel Żeńsko-Żeński"]} id=C1 x=500 y=500\nPLUG_CABLE id=C1 side=A target=J1\nPLUG_CABLE id=C1 side=B target=J2'
        project=execute_batch(Project(sheets=[Sheet()]),0,commands); a,b,c=project.sheets[0].components
        net=build_netlist(project.sheets[0]); self.assertEqual(net.pins[a.id,1],net.pins[b.id,1])
    def test_numeric_budget_and_reject_undersized_plan(self):
        prompt='USB-C: 3.3V,5V,9V,12V,25V każde oprócz 25V max 1,5A, a 25V 1A'
        req=requirements(prompt); self.assertAlmostEqual(req['output_power_W'],68.95); self.assertGreater(req['minimum_input_W_at_90_percent'],76)
        plan={**PLAN,'tasks':[dict(PLAN['tasks'][0],task='Use a 5 V / 5 A source')]}
        with self.assertRaisesRegex(ValueError,'Undersized'): validate_plan(plan,prompt)

class UITests(unittest.TestCase):
    def setUp(self): self.window=MainWindow(AppSettings(language='pl',window_mode='windowed'),start_setup=False)
    def tearDown(self):
        self.window._sync_positions(); self.window._saved_state=self.window.project.to_dict(); self.window.close(); self.window.deleteLater(); APP.processEvents()
    def test_sound_menu_contains_buzzers_and_cables_are_separate(self):
        menu=QMenu(); self.window._populate_library_menu(menu,1,QPointF().toPoint())
        sound=next(a.menu() for a in menu.actions() if a.text()=='Dźwięk')
        self.assertTrue(any('Buzzer' in a.text() for a in sound.actions()))
        cables=QMenu(); self.window._populate_library_menu(cables,7,QPointF().toPoint())
        self.assertEqual(len(cables.actions()),3); self.assertTrue(all(a.menu() for a in cables.actions()))
    def test_editor_cable_remains_without_connection_mode(self):
        view=self.window._current_view()
        ids={d.name:d.id for d in AVAILABLE_ITEMS}
        first=view.add_component(ids['Goldpin']); second=view.add_component(ids['Goldpin żeński'])
        view._component_items[first.id].setPos(300,300); view._component_items[second.id].setPos(800,300)
        a=view._component_items[first.id].pin_positions()[0]; target=view._component_items[second.id].pin_positions()[0]
        from app.core.cable_connections import attach
        component=view.add_component(ids['Kabel Męsko-Żeński'])
        attach(view._sheet,component,'A',second,0)
        attach(view._sheet,component,'B',first,0)
        view.load_sheet(view._sheet)
        target=view._component_items[second.id].pin_positions()[0]
        cable=view.cable_layer.usb_cables[0]; self.assertEqual(cable.component.properties['jumper_a_pin'],'0')
        self.assertEqual(cable.plugs[0].pos(),target); view._component_items[second.id].setPos(820,340); view._refresh_attached_wires()
        self.assertEqual(cable.plugs[0].pos(),view._component_items[second.id].pin_positions()[0])
        self.assertFalse(hasattr(self.window,'connection_choice'))
        self.assertFalse(hasattr(view,'_jumper_click'))
    def test_scope_controls_embedded_not_new_window(self):
        from app.ui.simulation_window import SimulationWindow
        b=Bench(); s,g=b.power(); scope=b.add('Oscyloskop'); b.connect(s,0,scope,0); b.connect(g,0,scope,1)
        self.window.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)]); self.window._rebuild_tabs()
        sim=SimulationWindow(self.window); sim.open_scope(scope.id)
        self.assertIsNone(sim.measurement_panel); self.assertIsNotNone(sim.scope_controls.graphicsProxyWidget())
        sim.scope_controls.volts_div.setValue(2); sim.scope_controls.time_div.setValue(.02)
        self.assertEqual(sim.scopes[scope.id].scope_bounds,(-4,4)); self.assertAlmostEqual(sim.scopes[scope.id].scope_duration,.16)
        self.assertEqual(sim.scope_controls.time_div.singleStep(),.01)
        item=sim.scopes[scope.id]; item.scope_samples.extend(((0.,0.),(.08,10.)))
        plot=item._scope_plot_rect(); item._update_scope_cursor(QPointF(plot.left()+plot.width()*.25,plot.center().y()))
        self.assertAlmostEqual(item.scope_cursor_fraction,.25)
        sim.close()
    def test_all_socket_regions_same_dimensions(self):
        from app.canvas.component_item import ComponentItem
        from app.canvas.connector_art import socket_regions
        b=Bench()
        for name in ('Port USB A','Port USB C','Kostka zasilająca USB','Raspberry Pi 5','Arduino Uno R3','Klawiatura USB'):
            item=ComponentItem(b.add(name)); self.assertTrue(socket_regions(item,item.connector_body()))
            for _,rect in socket_regions(item,item.connector_body()): self.assertEqual((rect.width(),rect.height()),(46,28))

if __name__=='__main__': unittest.main()
