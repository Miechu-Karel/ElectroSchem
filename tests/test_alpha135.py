"""Alpha5: instruments, USB cables, grouped assets and safe generated commands."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest,json,math
from copy import deepcopy
from unittest.mock import patch,MagicMock
from PySide6.QtCore import QPointF,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMenu
from app.core.models import Project,Sheet,Wire,ComponentInstance
from app.core.settings import AppSettings
from app.libraries.built_in import AVAILABLE_ITEMS,get_definition,get_instance_definition
from app.libraries.simulation_catalog import behavior_for
from app.simulation.engine import Circuit
from app.simulation.examples import example
from app.simulation.netlist import build_netlist
from app.simulation.measurements import resistance
from app.services.assistant_client import decode_answer
from app.services.assistant_curriculum import tasks,validate_response
from app.services.clipboard import encode_selection,decode_selection,prepare_paste
from app.canvas.routing import overlap_allowed,safe_route
from app.core.assets import make_asset,instantiate
from app.ui.measurement_panel import rms
from app.ui.instrument_graphics import waveform_value_at
from app.ui.main_window import MainWindow,APP_VERSION
from test_simulation_alpha2 import Bench
from test_alpha134 import UITests as ExistingUI

APP=QApplication.instance() or QApplication([])

class ModelTests(unittest.TestCase):
    def test_version_and_adjustable_battery_stable_id(self):
        self.assertEqual(APP_VERSION,"1.3.1")
        battery=next(d for d in AVAILABLE_ITEMS if d.name=="Bateria")
        self.assertIn("9v",battery.id.lower()); self.assertEqual(behavior_for(battery).kind,"dc")
    def test_exercise13_declared_add_properties_normalized(self):
        task=tasks()[12]; commands=task["commands"]
        led=next(d for d in AVAILABLE_ITEMS if d.name=="Dioda LED 3mm")
        lines=commands.splitlines()
        for i,line in enumerate(lines):
            if line.startswith("ADD_COMPONENT") and led.id in line: lines[i]=line+" color=red"
        answer=decode_answer(json.dumps({"summary":"Check","commands":"\n".join(lines)}))
        self.assertIn("SET_PROPERTY",answer["commands"]); self.assertTrue(validate_response(task,answer)["verified"])
        with self.assertRaisesRegex(ValueError,"unsupported"):
            decode_answer(json.dumps({"summary":"No","commands":f"ADD_COMPONENT type={led.id} id=L1 x=200 y=200 unsupported=7"}))
    def test_unpowered_ohmmeter_reads_lamp_and_switch(self):
        sheet=example("meter_ohm"); circuit=Circuit(sheet); result=circuit.step()
        meter=next(c for c in sheet.components if get_definition(c.library_id).name=="Omomierz")
        self.assertIn("25",result.readings[meter.id]); self.assertFalse(any(result.currents.values()))
        switch=next(d for d in circuit.devices if d.kind=="switch"); switch.closed=False
        self.assertEqual(circuit.step().readings[meter.id],"OL")
    def test_time_weighted_rms(self):
        data=[(i/10000,5*math.sqrt(2)*math.sin(2*math.pi*50*i/10000)) for i in range(1001)]
        self.assertAlmostEqual(rms(data,.04),5,places=3)
    def test_scope_cursor_interpolates_instantaneous_voltage(self):
        self.assertEqual(waveform_value_at([(0.,0.),(1.,10.)],.25,duration=None),(0.25,2.5))
    def test_usb_power_only_from_source_and_connector_type(self):
        b=Bench(); brick=b.add("Kostka zasilająca USB",value="5",unit="V"); port=b.add("Port USB C"); cable=b.add("Kabel USB",usb_a_target=brick.id,usb_b_target=port.id)
        load=b.add("Rezystor",value="1000"); b.connect(port,"VBUS.A4",load,0); b.connect(port,"GND.A1",load,1)
        c=b.circuit(); self.assertAlmostEqual(abs(c.step().currents[load.id]),.005,places=5)
        cable.properties["sim_usb_b_type"]="B"; netlist=build_netlist(Sheet(components=b.components,wires=b.wires))
        self.assertNotEqual(netlist.pins[cable.id,4],netlist.pins[port.id,3])
    def test_switch_variable_outputs(self):
        b=Bench(); switch=b.add("Przełącznik wielostopniowy",sim_outputs="10",sim_position="10")
        definition=get_instance_definition(switch); self.assertEqual(len(definition.pins),11)
        sheet=Sheet(components=[switch]); netlist=build_netlist(sheet)
        self.assertLess(resistance(sheet,[],netlist,netlist.pins[switch.id,0],netlist.pins[switch.id,10]),.002)
        switch.properties["sim_outputs"]="11"
        with self.assertRaises(ValueError): build_netlist(sheet)
    def test_half_cell_overlap_route(self):
        sheet=Sheet(wires=[Wire(100,100,300,100,points=[[100,100],[300,100]])])
        self.assertFalse(overlap_allowed(sheet,[QPointF(150,100),QPointF(350,100)]))
        self.assertTrue(overlap_allowed(sheet,[QPointF(290,100),QPointF(400,100)]))
        route=safe_route(sheet,QPointF(100,100),QPointF(350,100))
        self.assertIsNotNone(route); self.assertTrue(overlap_allowed(sheet,route))
    def test_asset_groups_roundtrip_and_duplicate_independent(self):
        bench=Bench(); first=bench.add("Rezystor","1000"); second=bench.add("Rezystor","2200")
        bench.connect(first,1,second,0)
        source=Project(sheets=[Sheet(components=bench.components,wires=bench.wires)])
        definition=make_asset(source,source.sheets[0],"Test")
        destination=Project(sheets=[Sheet()]); fragment,_=instantiate(definition["asset"],ComponentInstance(definition["id"],500,400),project=destination)
        destination.sheets[0]=fragment
        restored=Project.from_dict(destination.to_dict()); sheet=restored.sheets[0]
        groups={c.properties["asset_group"] for c in sheet.components}; self.assertEqual(len(groups),1)
        copied=decode_selection(encode_selection(restored,sheet,{c.id for c in sheet.components}|{w.id for w in sheet.wires}))
        _,pasted=prepare_paste(restored,copied,20,20)
        self.assertNotEqual(next(iter(groups)),pasted.components[0].properties["asset_group"])
    def test_demo_pi_blinks_without_external_file(self):
        circuit=Circuit(example("pi_blink")); values=[]
        for _ in range(1200): values.append(max(circuit.step(.001).brightness.values(),default=0))
        self.assertGreater(max(values),.05); self.assertLess(min(values),.01)

class UIRegression(unittest.TestCase):
    setUp=ExistingUI.setUp
    tearDown=ExistingUI.tearDown
    sandbox=ExistingUI.sandbox
    def test_wire_junction_dot_only_marks_a_real_three_way_branch(self):
        first=Wire(100,100,200,100,points=[[100,100],[200,100]])
        second=Wire(200,100,300,100,points=[[200,100],[300,100]])
        redundant=Wire(200,100,400,100,points=[[200,100],[400,100]])
        self.editor.project=Project(sheets=[Sheet(wires=[first,second,redundant])])
        self.editor._rebuild_tabs(); view=self.editor._current_view(); view._join_coincident_ends()
        self.assertFalse(view._wire_items[first.id].endpoint_dots[1])
        self.assertFalse(view._wire_items[second.id].endpoint_dots[0])
        branch=Wire(200,100,200,200,points=[[200,100],[200,200]])
        self.editor.project.sheets[0].wires.append(branch); view._add_wire_item(branch); view._join_coincident_ends()
        self.assertTrue(view._wire_items[first.id].endpoint_dots[1])
        self.assertTrue(view._wire_items[branch.id].endpoint_dots[0])

    def test_meter_real_probes_drag_open_and_ac_rms(self):
        b=Bench(); source=b.add("Źródło napięcia przemiennego",value="5",unit="V",sim_frequency="50 Hz"); load=b.add("Żarówka",value="1",unit="W",sim_rated_voltage="5 V")
        b.connect(source,0,load,0); b.connect(source,1,load,1); sim=self.sandbox(b)
        sim.open_measurements(); panel=sim.measurement_panel
        panel.positive.setCurrentIndex(0); panel.negative.setCurrentIndex(1)
        for _ in range(1000): sim.single_step()
        self.assertIn("RMS",panel.reading.text()); self.assertAlmostEqual(float(panel.reading.text().split()[0]),5,delta=.1)
        panel.probes[0].setPos(QPointF(-500,-500)); panel.probe_moved(panel.probes[0])
        self.assertIsNone(panel.probes[0].node); self.assertIn("sondy",panel.reading.text())
    def test_meter_continuity_audio_and_compact_rows(self):
        b=Bench(); s,g=b.power(); switch=b.add("Łącznik",sim_closed="true"); b.connect(g,0,switch,0); sim=self.sandbox(b)
        sim.single_step(); sim.open_measurements(); panel=sim.measurement_panel
        for field,index in ((panel.positive,0),(panel.negative,1)): field.setCurrentIndex(field.findText(switch.reference+"."+get_definition(switch.library_id).pins[index].name))
        panel.mode.setCurrentIndex(3)
        with patch("app.ui.buzzer_audio.BuzzerAudio") as audio:
            panel.beep=None; panel.audio_unavailable=False; panel.refresh()
            self.assertIn("Zwarte",panel.reading.text()); audio.return_value.update.assert_called()
            sim.buzzer_sound_button.setChecked(True); panel.refresh(); self.assertEqual(audio.return_value.update.call_args.args[0],{})
        self.assertFalse(panel.branch.isVisible()); self.assertEqual(sim.measurement_button.width(),44)
    def test_usb_draggable_plugs_editor_immutable(self):
        b=Bench(); brick=b.add("Kostka zasilająca USB",value="5",unit="V"); cable=b.add("Kabel USB"); port=b.add("Port USB C")
        sim=self.sandbox(b); before=deepcopy(self.editor.project.to_dict())
        self.assertEqual(len(sim.usb_cables),1); visual=sim.usb_cables[0]; plug=visual.plugs[0]
        target=next(point for cid,point in visual.targets(plug) if cid==brick.id)
        plug.setPos(target); visual.attach(plug); APP.processEvents()
        actual=next(c for c in sim.sheet.components if c.id==cable.id)
        self.assertEqual(actual.properties["usb_a_target"],brick.id); self.assertEqual(self.editor.project.to_dict(),before)
    def test_connector_menu_has_four_subcategories_and_icons(self):
        menu=QMenu(); self.editor._populate_library_menu(menu,6,None)
        self.assertEqual(len(menu.actions()),4); self.assertTrue(all(a.menu() is not None for a in menu.actions()))
        self.assertFalse(self.editor.library_actions[6].icon().isNull())
        self.assertFalse(self.editor.library_actions[7].icon().isNull())
    def test_asset_actual_drag_and_shift_drag(self):
        b=Bench(); b.add("Rezystor",value="1000"); b.add("Rezystor",value="2200")
        source=Project(sheets=[Sheet(components=b.components)])
        definition=make_asset(source,source.sheets[0],"Pair")
        project=Project(sheets=[Sheet()]); sheet,_=instantiate(definition["asset"],ComponentInstance(definition["id"],600,400),project)
        project.sheets=[sheet]; self.editor.project=project; self.editor._rebuild_tabs(); self.editor.show(); APP.processEvents()
        view=self.editor._current_view(); view.fit_page()
        def drag(mods):
            item=view._component_items[sheet.components[0].id]
            start=view.mapFromScene(item.pos()); end=view.mapFromScene(item.pos()+QPointF(40,0))
            QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,mods,pos=start)
            QTest.mouseMove(view.viewport(),end); QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,mods,pos=end); APP.processEvents()
        before=[c.x for c in sheet.components]; drag(Qt.KeyboardModifier.NoModifier)
        self.assertEqual([c.x for c in sheet.components],[x+40 for x in before])
        before=[c.x for c in sheet.components]; drag(Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(sheet.components[0].x,before[0]+40); self.assertEqual(sheet.components[1].x,before[1])
    def test_custom_actual_rmb_edits_not_places(self):
        from test_rc4 import definition
        self.editor.project.custom_components.append(definition()); menu=QMenu(self.editor)
        with patch("app.core.assets.load_assets",return_value=[]): self.editor._populate_library_menu(menu,3,None)
        menu.show(); APP.processEvents()
        action=next(a for a in menu.actions() if a.data()=="custom-rc4")
        def select_edit():
            popup=APP.activePopupWidget(); popup.actions()[0].trigger(); popup.close()
        with patch.object(self.editor,"edit_custom_component") as edit,patch.object(self.editor,"add_component_from_id") as place:
            QTimer.singleShot(0,select_edit)
            QTest.mouseClick(menu,Qt.MouseButton.RightButton,pos=menu.actionGeometry(action).center())
            edit.assert_called_once_with("custom-rc4"); place.assert_not_called()
        menu.close()
    def test_cost_cancel_never_sends_request(self):
        from app.ui.command_panel import CommandPanel
        panel=CommandPanel(self.editor); panel.prompt.setPlainText("Test")
        self.editor.settings.ai_provider="openai"; self.editor.settings.ai_chat_consent=True
        with patch.object(panel,"provider_key",return_value="fake"),patch("app.services.assistant_curriculum.read_profile",return_value={"exercises":[{}]*20}),patch("app.ui.ai_cost_dialog.confirm_requests",return_value=False),patch.object(panel.client,"start") as start:
            panel.send_request(); start.assert_not_called()
        panel.close()
    def test_two_wire_bend_hides_dot_but_branch_keeps_dot(self):
        sheet=Sheet(wires=[Wire(200,200,400,200),Wire(400,200,500,300)])
        self.editor.project=Project(sheets=[sheet]); self.editor._rebuild_tabs(); view=self.editor._current_view()
        self.assertFalse(view._wire_items[sheet.wires[0].id].endpoint_dots[1])
        sheet.wires.append(Wire(400,200,400,100)); self.editor._rebuild_tabs(); view=self.editor._current_view()
        self.assertTrue(view._wire_items[sheet.wires[0].id].endpoint_dots[1])
    def test_mute_stops_all_audio_immediately(self):
        sim=self.sandbox(Bench())
        sim.buzzer_audio=MagicMock(); sim.fault_sound=MagicMock()
        sim.measurement_panel=MagicMock(); sim.measurement_panel.beep=MagicMock()
        sim.buzzer_sound_button.setChecked(True)
        sim.buzzer_audio.stop.assert_called_once(); sim.fault_sound.stop.assert_called_once(); sim.measurement_panel.beep.stop.assert_called_once()
        sim.measurement_panel=None; sim.buzzer_audio=None; sim.fault_sound=None
    def test_boxed_asset_probes_resolve_original_passive_network(self):
        b=Bench(); resistor=b.add("Rezystor",value="1000")
        project=Project(sheets=[Sheet(components=b.components)])
        definition=make_asset(project,project.sheets[0],"Resistor case",boxed=True)
        project.custom_components=[definition]; instance=project.new_component(definition["id"],500,400)
        project.sheets=[Sheet(components=[instance])]
        self.editor.project=project; self.editor._rebuild_tabs(); self.editor.show_simulation(); APP.processEvents()
        sim=self.editor.simulation_window; sim.open_measurements(); panel=sim.measurement_panel
        panel.positive.setCurrentIndex(0); panel.negative.setCurrentIndex(1)
        panel.mode.setCurrentIndex(2); self.assertEqual(panel.reading.text(),"1 kΩ")

if __name__=="__main__": unittest.main()
