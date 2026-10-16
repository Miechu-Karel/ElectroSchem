"""Alpha4: real electrical/UI input paths, instruments, assets and onboarding."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint,QObject,Signal,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMenu,QMessageBox
from app.core.models import Project,Sheet,ComponentInstance
from app.core.settings import AppSettings
from app.libraries.built_in import get_definition,BUILT_IN_ITEMS,AVAILABLE_ITEMS,validate_custom_definition
from app.libraries.menu_groups import library_sort_key,subgroup
from app.simulation.netlist import build_netlist
from app.simulation.engine import Circuit,SimulationError
from app.simulation.python_board import PythonBoard
from app.simulation.measurements import resistance
from app.core.assets import make_asset,instantiate,expand_assets,save_asset,load_assets,remove_asset
from app.services.assistant_curriculum import tasks,validate_response,Curriculum,read_profile,remembered_knowledge
from app.ui.main_window import MainWindow,LIBRARY_GROUPS
from app.ui.settings_dialog import SettingsDialog
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)

class ElectricalTests(unittest.TestCase):
    def test_pad_default_high_while_held_and_physical_mode_opt_in(self):
        b=Bench(); s,g=b.power(); pad=b.add("Joystick Iduino ST1079",sim_closed="true")
        b.connect(s,0,pad,"VCC"); b.connect(g,0,pad,"GND"); c=b.circuit()
        d=next(d for d in c.devices if d.component.id==pad.id); node=c.netlist.pins[pad.id,4]
        self.assertFalse(d.closed); self.assertLess(c.step().voltages[node],.01)
        d.closed=True; self.assertGreater(c.step().voltages[node],4.99)
        d.closed=False; self.assertLess(c.step().voltages[node],.01)
        d.parameters["sim_switch_mode"]="contact"
        self.assertGreater(c.step().voltages[node],4.99)
        d.closed=True; self.assertLess(c.step().voltages[node],.01)

    def test_unpowered_ports_do_not_invent_voltage_even_with_legacy_source_flag(self):
        b=Bench(); port=b.add("Port USB A",sim_power="true",sim_voltage="5 V"); r=b.add("Rezystor","1","kΩ")
        b.connect(port,"VBUS",r,0); b.connect(port,"GND",r,1)
        result=b.circuit().step()
        self.assertFalse(any(result.voltages.values()))
        self.assertFalse(any(result.currents.values()))

    def test_goldpin_and_usb_cable_are_continuous_not_sources(self):
        b=Bench(); supply=b.add("Kostka zasilająca USB","5","V"); cable=b.add("Kabel USB"); pin=b.add("Goldpin"); r=b.add("Rezystor","1","kΩ")
        b.connect(supply,0,cable,"A.VBUS"); b.connect(supply,1,cable,"A.GND")
        b.connect(cable,"B.VBUS",pin,"BOTTOM"); b.connect(pin,"TOP",r,0); b.connect(r,1,cable,"B.GND")
        c=b.circuit(); result=c.step(); self.assertFalse(result.faults); self.assertAlmostEqual(result.currents[r.id],.005,places=7)
        self.assertEqual(c.netlist.pins[pin.id,0],c.netlist.pins[pin.id,1]); self.assertEqual(len(c.sources),1)

    def test_six_positions_and_off_only_close_selected_throw(self):
        b=Bench(); s,g=b.power(); switch=b.add("Przełącznik wielostopniowy"); b.connect(s,0,switch,"COM")
        loads=[]
        for i in range(1,7):
            r=b.add("Rezystor","1","kΩ"); loads.append(r); b.connect(switch,str(i),r,0); b.connect(r,1,g,0)
        c=b.circuit(); d=next(d for d in c.devices if d.component.id==switch.id)
        for position in range(7):
            d.parameters["sim_position"]=str(position); result=c.step(); self.assertFalse(result.faults)
            for i,r in enumerate(loads,1): self.assertAlmostEqual(result.currents[r.id],5/1000.001 if position==i else 0,places=7)

    def test_meters_do_not_change_voltage_and_ammeter_is_series(self):
        b=Bench(); s,g=b.power(); r=b.add("Rezystor","1","kΩ"); am=b.add("Amperomierz"); vm=b.add("Woltomierz")
        b.connect(s,0,am,0); b.connect(am,1,r,0); b.connect(r,1,g,0); b.connect(r,0,vm,0); b.connect(r,1,vm,1)
        result=b.circuit().step(); self.assertFalse(result.faults)
        self.assertAlmostEqual(result.currents[am.id],.005,places=7); self.assertIn("A",result.readings[am.id]); self.assertIn("V",result.readings[vm.id])

    def test_passive_resistance_parallel_and_continuity(self):
        b=Bench(); s,g=b.power(); r1=b.add("Rezystor","1","kΩ"); r2=b.add("Rezystor","1","kΩ")
        for r in (r1,r2): b.connect(s,0,r,0); b.connect(g,0,r,1)
        c=b.circuit(); before=deepcopy(c.sheet)
        a,z=c.netlist.pins[r1.id,0],c.netlist.pins[r1.id,1]
        self.assertAlmostEqual(resistance(c.sheet,[],c.netlist,a,z,c.devices),500)
        self.assertEqual(resistance(c.sheet,[],c.netlist,a,a,c.devices),0); self.assertEqual(c.sheet,before)

    def test_python_input_stdout_and_stderr_cooperate_without_host_execution(self):
        definition=next(d for d in BUILT_IN_ITEMS if d.name=="Raspberry Pi 5")
        script=PythonBoard((Path(__file__).parent/"fixtures"/"console_input.py").read_text(encoding="utf-8"),definition)
        self.assertIsInstance(script.advance(.001),dict); self.assertTrue(script.waiting_input)
        script.submit_input("Łukasz"); script.advance(.02)
        self.assertIn("Cześć Łukasz",script.serial); self.assertTrue(script.waiting_input)
        script.submit_input("żółć"); script.advance(.02); self.assertTrue(script.serial.endswith("żółć\n"))
        bad=PythonBoard("import os\nos.system('echo no')",definition)
        with self.assertRaises(ValueError): bad.advance(.001)

class AssetTests(unittest.TestCase):
    def source(self):
        b=Bench(); s,g=b.power(); r=b.add("Rezystor","1","kΩ"); b.connect(s,0,r,0); b.connect(r,1,g,0)
        return Project(sheets=[Sheet(components=b.components,wires=b.wires)])
    def test_asset_roundtrip_fresh_identifiers_and_equal_simulation(self):
        p=self.source(); original=deepcopy(p.to_dict()); asset=validate_custom_definition(make_asset(p,p.sheets[0],"Load",True))
        p.custom_components.append(asset)
        with TemporaryDirectory() as directory:
            path=Path(directory)/"assets.json"; save_asset(asset,path); self.assertEqual(load_assets(path)[0],asset)
        instance=p.new_component(asset["id"],600,400); p.sheets=[Sheet(components=[instance])]
        restored=Project.from_dict(p.to_dict()); expanded=expand_assets(restored.sheets[0],restored.custom_components)
        self.assertEqual(len(expanded.components),3); self.assertEqual(len(expanded.wires),2)
        self.assertTrue(set(c.id for c in expanded.components).isdisjoint({c["id"] for c in original["sheets"][0]["components"]}))
        result=Circuit(restored.sheets[0],restored.custom_components).step(); self.assertFalse(result.faults)
        resistor=next(c for c in expanded.components if "Rezystor" in get_definition(c.library_id).name)
        self.assertAlmostEqual(result.currents[resistor.id],.005,places=7)
    def test_bad_asset_port_and_nested_payload_are_rejected(self):
        p=self.source(); asset=make_asset(p,p.sheets[0],"Bad")
        asset["asset"]["exports"][0]["pin"]=999
        with self.assertRaises(ValueError): validate_custom_definition(asset)
    def test_two_instances_have_disjoint_pin_anchors(self):
        p=self.source(); asset=make_asset(p,p.sheets[0],"Load")
        a,_=instantiate(asset["asset"],ComponentInstance(asset["id"],600,400),p)
        b,_=instantiate(asset["asset"],ComponentInstance(asset["id"],900,400),p)
        self.assertTrue({c.id for c in a.components}.isdisjoint(c.id for c in b.components))
        self.assertTrue({c.reference for c in a.components}.isdisjoint(c.reference for c in b.components))
    def test_boxed_asset_external_wires_keep_original_electrical_connections(self):
        p=self.source(); sheet=p.sheets[0]
        r=next(c for c in sheet.components if get_definition(c.library_id).name=="Rezystor")
        asset=validate_custom_definition(make_asset(p,sheet,"Resistor",True,{r.id}))
        p.custom_components.append(asset); instance=p.new_component(asset["id"],r.x,r.y)
        sheet.components=[c for c in sheet.components if c.id!=r.id]+[instance]
        for wire in sheet.wires:
            for side in ("start","end"):
                if getattr(wire,side+"_component_id")==r.id:
                    index=getattr(wire,side+"_pin_index")
                    setattr(wire,side+"_component_id",instance.id)
                    setattr(wire,side+"_pin_number",asset["pins"][index]["number"])
        c=Circuit(sheet,p.custom_components); result=c.step()
        self.assertFalse(result.faults)
        restored=next(d for d in c.devices if d.kind=="resistor")
        self.assertAlmostEqual(result.currents[restored.component.id],.005,places=7)
    def test_remove_one_saved_asset_preserves_other_definitions_and_source(self):
        p=self.source(); before=deepcopy(p.to_dict())
        first=make_asset(p,p.sheets[0],"First"); second=make_asset(p,p.sheets[0],"Second")
        with TemporaryDirectory() as directory:
            path=Path(directory)/"assets.json"; save_asset(first,path); save_asset(second,path)
            remove_asset(first["id"],path)
            self.assertEqual([d["id"] for d in load_assets(path)],[second["id"]])
        self.assertEqual(p.to_dict(),before)

class CurriculumTests(unittest.TestCase):
    def test_duplicate_cache_records_cannot_bypass_preparation(self):
        from app.services.assistant_curriculum import write_profile,profile_key,REVISION
        settings=AppSettings(ai_provider="openai")
        task=tasks()[0]; record=validate_response(task,{"summary":"Checked","commands":task["commands"]})
        with TemporaryDirectory() as directory:
            path=Path(directory)/"course.json"
            write_profile(settings,{"version":REVISION,"key":profile_key(settings),"exercises":[record,record]},path)
            with self.assertRaises(ValueError): read_profile(settings,path)

    def test_twenty_executable_reference_solutions_and_wrong_answer_rejected(self):
        self.assertEqual(len(tasks()),20)
        for task in tasks():
            with self.subTest(task=task["name"]):
                record=validate_response(task,{"summary":"Reference","commands":task["commands"]})
                self.assertTrue(record["verified"])
        with self.assertRaises(ValueError): validate_response(tasks()[0],{"summary":"Pretend","commands":""})
    def test_fake_provider_completes_persists_resumes_and_replays_without_real_api(self):
        class FakeClient(QObject):
            completed=Signal(dict); failed=Signal(str)
            def __init__(self): super().__init__(); self.calls=0
            def start(self,settings,prompt,context,history):
                task=tasks()[self.calls]; self.calls+=1
                QTimer.singleShot(0,lambda:self.completed.emit({"summary":"Checked","commands":task["commands"]}))
            def cancel(self): pass
        settings=AppSettings(ai_provider="openai")
        with TemporaryDirectory() as directory:
            path=Path(directory)/"course.json"; client=FakeClient(); course=Curriculum(settings,client=client,path=path)
            completed=[]; errors=[]; course.completed.connect(lambda:completed.append(True)); course.failed.connect(errors.append)
            course.start()
            for _ in range(500):
                APP.processEvents()
                if completed or errors: break
            self.assertFalse(errors,errors); self.assertEqual(client.calls,20); self.assertTrue(completed)
            self.assertEqual(len(read_profile(settings,path)["exercises"]),20)
            with patch("app.services.assistant_curriculum.cache_path",return_value=path):
                self.assertEqual(remembered_knowledge(settings)["completed"],20)
            other=FakeClient(); resumed=Curriculum(settings,client=other,path=path); resumed.start(); self.assertEqual(other.calls,0)

class UITests(unittest.TestCase):
    def setUp(self): self.editor=MainWindow(AppSettings(language="pl",window_mode="windowed",fault_effect="mini"),start_setup=False)
    def tearDown(self):
        self.editor._sync_positions(); self.editor._saved_state=self.editor.project.to_dict()
        self.editor.close(); self.editor.deleteLater(); APP.processEvents()
    def sandbox(self,b):
        self.editor.project=Project(sheets=[Sheet(components=b.components,wires=b.wires)])
        self.editor._rebuild_tabs(); self.editor.show_simulation(); APP.processEvents(); return self.editor.simulation_window
    def test_actual_pi_scene_click_opens_console_and_input_reaches_program(self):
        b=Bench(); board=b.add("Raspberry Pi 5",sim_source=str(Path(__file__).parent/"fixtures"/"console_input.py"),sim_console=True)
        sim=self.sandbox(b); sim.single_step()
        pos=sim.view.mapFromScene(sim.symbols[board.id].scenePos())
        QTest.mouseClick(sim.view.viewport(),Qt.MouseButton.LeftButton,pos=pos); APP.processEvents()
        QTest.keyClick(sim.view,Qt.Key.Key_E); APP.processEvents()
        self.assertIn(board.id,sim.pi_consoles); console=sim.pi_consoles[board.id]; self.assertTrue(console.isVisible())
        console.entry.setText("Ala"); console.submit()
        for _ in range(200): sim.single_step()
        self.assertIn("Cześć Ala",console.toPlainText())
        sim.view.setFocus(); QTest.keyClick(sim.view,Qt.Key.Key_E); self.assertFalse(console.isVisible())
    def test_pad_actual_rmb_gives_high_until_release(self):
        b=Bench(); s,g=b.power(); pad=b.add("Joystick Iduino ST1079")
        b.connect(s,0,pad,"VCC"); b.connect(g,0,pad,"GND")
        sim=self.sandbox(b); sim.single_step(); node=sim.circuit.netlist.pins[pad.id,4]
        control=sim.controls[pad.id].joystick
        self.assertLess(sim.circuit.result.voltages[node],.01)
        QTest.mousePress(control,Qt.MouseButton.RightButton,pos=QPoint(75,75))
        self.assertGreater(sim.circuit.result.voltages[node],4.99)
        self.assertEqual(sim.controls[pad.id].switch_state.text(),"Wciśnięty")
        QTest.mouseRelease(control,Qt.MouseButton.RightButton,pos=QPoint(75,75))
        self.assertLess(sim.circuit.result.voltages[node],.01)
        self.assertEqual(sim.controls[pad.id].switch_state.text(),"Puszczony")
    def test_powered_usb_keyboard_supplies_python_input(self):
        b=Bench(); board=b.add("Raspberry Pi 5",sim_source=str(Path(__file__).parent/"fixtures"/"console_input.py"))
        keyboard=b.add("Klawiatura USB"); b.connect(board,"5V",keyboard,"VBUS"); b.connect(board,"GND",keyboard,"GND")
        sim=self.sandbox(b); sim.single_step()
        entry=sim.controls[keyboard.id].entry; entry.setText("Żaneta")
        QTest.keyClick(entry,Qt.Key.Key_Return)
        for _ in range(200): sim.single_step()
        self.assertIn("Cześć Żaneta",sim.console_script(board.id).serial)
    def test_rf_card_drag_uid_and_source_document_unchanged(self):
        b=Bench(); s,g=b.power(); reader=b.add("Moduł RFID RC522"); card=b.add("Karta RFID",rfid_id="1234ABCD")
        b.connect(s,0,reader,"3V3"); b.connect(g,0,reader,"GND")
        s.properties["sim_voltage"]="3.3 V"
        # Use a 3.3 V source rather than a fixed 5 V rail.
        s.library_id=next(d.id for d in BUILT_IN_ITEMS if d.name=="Szyna Zasilania +3.3V")
        sim=self.sandbox(b); before=deepcopy(self.editor.project.to_dict())
        item=sim.symbols[card.id]; item.setPos(reader.x,reader.y); APP.processEvents()
        d=next(d for d in sim.circuit.devices if d.component.id==reader.id)
        self.assertEqual(d.parameters["sim_stimulus"],int("1234ABCD",16)); item.setPos(reader.x+1000,reader.y)
        self.assertEqual(d.parameters["sim_stimulus"],0); self.assertEqual(self.editor.project.to_dict(),before)
    def test_settings_tabs_toolbar_and_adjacent_adc_dac(self):
        dialog=SettingsDialog(self.editor.settings)
        self.assertEqual(dialog.settings_tabs.count(),4); dialog.close(); dialog.deleteLater()
        self.assertIn(self.editor.ai_action,self.editor.toolbar.actions())
        self.assertEqual(self.editor.library_actions[-2].text().split(" (")[0],"Narzędzia pomiarowe")
        self.assertEqual(self.editor.library_actions[-1].text().split(" (")[0],"Elementy interaktywne")
        self.assertEqual(self.editor.library_actions[5].text().split(" (")[0],"Ulubione")
        self.assertEqual([button.defaultAction() for button in self.editor.library_buttons[-2:]],self.editor.library_actions[-2:])
        self.assertEqual([action.property("iconFile") for action in self.editor.library_actions],[group[2] for group in LIBRARY_GROUPS])
        self.assertTrue(all(not action.icon().isNull() for action in self.editor.library_actions))
        cables=QMenu(); measurement=QMenu()
        self.editor._populate_library_menu(cables,6,QPoint(0,0)); self.editor._populate_library_menu(measurement,7,QPoint(0,0))
        def leaf_ids(menu):
            return {action.data() for action in menu.actions() if action.data()} | {
                identity for action in menu.actions() if action.menu() for identity in leaf_ids(action.menu())
            }
        from app.simulation.jumper import CABLE_IDS
        cable_submenus={action.text():action.menu() for action in cables.actions() if action.menu()}
        self.assertEqual(list(cable_submenus),["Porty USB","Goldpiny","Kable","Terminale"])
        self.assertEqual(leaf_ids(cable_submenus["Kable"]),CABLE_IDS)
        self.assertTrue({item.id for item in BUILT_IN_ITEMS if item.name.startswith(("Port USB","Port Lightning"))}.issubset(leaf_ids(cable_submenus["Porty USB"])))
        self.assertTrue({item.id for item in AVAILABLE_ITEMS if item.symbol=="goldpin" or "Goldpin" in item.name}.issubset(leaf_ids(cable_submenus["Goldpiny"])))
        terminal_ids={item.id for item in AVAILABLE_ITEMS if item.name.startswith("Terminale Śrubowe")}
        self.assertTrue(terminal_ids)
        self.assertEqual(leaf_ids(cable_submenus["Terminale"]),terminal_ids)
        self.assertTrue({item.id for item in BUILT_IN_ITEMS if item.category=="Narzędzia pomiarowe"}.issubset(leaf_ids(measurement)))
        self.assertFalse(any(action.menu() for action in measurement.actions()))
        groups=[]
        for item in sorted((d for d in BUILT_IN_ITEMS if d.category=="Układy i sterowniki"),key=library_sort_key):
            group=subgroup(item)[1]
            if group not in groups: groups.append(group)
        self.assertEqual(groups.index("Przetworniki cyfrowo-analogowe"),groups.index("Przetworniki analogowo-cyfrowe")+1)

if __name__=="__main__": unittest.main()
