"""Offline regression coverage for alpha7."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import math, unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtTest import QTest
from app.core.models import Project, Sheet, Wire
from app.core.settings import AppSettings, save_settings, load_settings
from app.canvas.component_item import ComponentItem
from app.canvas.connector_art import socket_regions
from app.ui.main_window import MainWindow, APP_VERSION
from app.simulation.engine import Circuit, ac_voltage
from app.simulation.netlist import build_netlist
from app.simulation.measurements import resistance
from app.simulation.examples import example
from app.libraries.built_in import get_definition
from test_simulation_alpha2 import Bench

APP=QApplication.instance() or QApplication([])

class ModelTests(unittest.TestCase):
    def test_labels_preserve_physical_pin_numbers(self):
        b=Bench()
        for name,labels in (("Prostownik AC/DC",["AC+","AC-","DC+","DC-"]), ("Przetwornica DC/AC",["DC+","DC-","AC+","AC-"])):
            d=get_definition(b.add(name).library_id)
            self.assertEqual([p.name for p in d.pins],labels)
            self.assertEqual([p.number for p in d.pins],["1","2","3","4"])
        self.assertEqual(APP_VERSION,"1.3.0")

    def test_unpowered_resistor_led_with_and_without_meter(self):
        for include_meter in (False,True):
            b=Bench(); r=b.add("Rezystor","330","Ω"); led=b.add("Dioda LED 3mm")
            b.connect(r,1,led,0)
            if include_meter:
                meter=b.add("Omomierz"); b.connect(meter,0,r,0); b.connect(meter,1,led,1)
            circuit=b.circuit(); before=deepcopy(circuit.sheet)
            a,z=circuit.netlist.pins[r.id,0],circuit.netlist.pins[led.id,1]
            self.assertAlmostEqual(resistance(circuit.sheet,[],circuit.netlist,a,z,circuit.devices),2340,places=3)
            self.assertTrue(math.isinf(resistance(circuit.sheet,[],circuit.netlist,z,a,circuit.devices)))
            result=circuit.step(); self.assertFalse(any(result.currents.values()))
            self.assertEqual(circuit.sheet,before)
            if include_meter: self.assertIn("2340",result.readings[meter.id])

    def test_disconnected_passive_island_beside_live_circuit(self):
        b=Bench(); supply,ground=b.power(); live=b.add("Rezystor","1000","Ω")
        b.connect(supply,0,live,0); b.connect(live,1,ground,0)
        r=b.add("Rezystor","330","Ω"); led=b.add("Dioda LED 3mm"); b.connect(r,1,led,0)
        circuit=b.circuit(); result=circuit.step()
        self.assertAlmostEqual(result.currents[live.id],.005)
        self.assertEqual(result.currents[r.id],0)
        self.assertAlmostEqual(resistance(circuit.sheet,[],circuit.netlist,circuit.netlist.pins[r.id,0],circuit.netlist.pins[led.id,1],circuit.devices),2340,places=3)

    def test_waveforms_have_requested_rms_and_distinct_shapes(self):
        for shape in ("sine","square","triangle","sawtooth"):
            samples=[ac_voltage(5,50,i/100000,shape) for i in range(2000)]
            self.assertAlmostEqual(math.sqrt(sum(v*v for v in samples)/len(samples)),5,places=4)
        self.assertAlmostEqual(ac_voltage(5,50,.005,"square"),5)
        self.assertAlmostEqual(ac_voltage(5,50,.005),5*math.sqrt(2))

    def test_usb_c_led_example_has_real_power_and_no_pin_snap_targets(self):
        sheet=example("usb_c_led"); circuit=Circuit(sheet); result=circuit.step()
        led=next(c for c in sheet.components if get_definition(c.library_id).symbol=="led")
        self.assertGreater(result.brightness[led.id],.05); self.assertFalse(result.faults)
        for c in sheet.components:
            if get_definition(c.library_id).name in {"Kabel USB","Kostka zasilająca USB"}:
                self.assertEqual(ComponentItem(c).pin_positions(),[])

    def test_favorites_persist_separately_from_projects(self):
        settings=AppSettings(favorite_components={"example":{"value":"330","unit":"Ω"}})
        with TemporaryDirectory() as directory:
            store=QSettings(str(Path(directory)/"prefs.ini"),QSettings.Format.IniFormat)
            save_settings(settings,store)
            self.assertEqual(load_settings(store).favorite_components["example"]["value"],"330")
            self.assertEqual(load_settings(store).favorite_components["example"]["unit"],"Ω")

    def test_remote_led_does_not_limit_plain_resistor_meter_range(self):
        b=Bench(); r=b.add("Rezystor","10","kΩ"); b.add("Dioda LED 3mm")
        sheet=Sheet(components=b.components); net=build_netlist(sheet)
        self.assertAlmostEqual(resistance(sheet,[],net,net.pins[r.id,0],net.pins[r.id,1]),10000)

    def test_inverter_uses_dc_input_and_ac_output_labels(self):
        b=Bench(); source=b.add("Bateria","5","V"); inverter=b.add("Przetwornica DC/AC",sim_output_voltage="5 V"); load=b.add("Rezystor","1","kΩ")
        for a,ap,z,zp in ((source,0,inverter,"DC+"),(source,1,inverter,"DC-"),(inverter,"AC+",load,0),(inverter,"AC-",load,1)): b.connect(a,ap,z,zp)
        circuit=b.circuit(); result=circuit.step(.0001)
        self.assertGreater(result.voltages[circuit.netlist.pins[load.id,0]]-result.voltages[circuit.netlist.pins[load.id,1]],.1)
        self.assertFalse(result.faults)

class UITests(unittest.TestCase):
    def setUp(self):
        self.window=MainWindow(AppSettings(language="pl",window_mode="windowed"),start_setup=False)
        self.window.show(); APP.processEvents()
    def tearDown(self):
        self.window._saved_state=self.window.project.to_dict(); self.window.close(); self.window.deleteLater(); APP.processEvents()
    def load(self,sheet):
        self.window.project=Project(sheets=[sheet]); self.window._rebuild_tabs(); APP.processEvents()
        return self.window._current_view()
    def test_y_junction_dot_but_no_dot_at_two_wire_bend(self):
        wires=[Wire(300,300,400,400),Wire(500,300,400,400),Wire(400,400,400,500)]
        view=self.load(Sheet(wires=wires))
        self.assertTrue(view._wire_items[wires[0].id].endpoint_dots[1])
        self.assertTrue(view._wire_items[wires[2].id].endpoint_dots[0])
        view=self.load(Sheet(wires=wires[:2]))
        self.assertFalse(view._wire_items[wires[0].id].endpoint_dots[1])

    def test_isolated_wire_displays_nodes_at_both_free_ends(self):
        wire=Wire(300,300,400,300,points=[[300,300],[400,300]])
        view=self.load(Sheet(wires=[wire]))
        self.assertEqual(view._wire_items[wire.id].endpoint_dots,(True,True))
        bend=Wire(400,300,500,400,points=[[400,300],[500,400]])
        view=self.load(Sheet(wires=[wire,bend]))
        self.assertFalse(view._wire_items[wire.id].endpoint_dots[1])

    def test_old_endpoint_to_middle_y_join_is_normalized_but_crossing_is_not(self):
        through=Wire(300,300,500,300,points=[[300,300],[400,400],[500,300]],group_id="asset")
        branch=Wire(400,400,400,500)
        view=self.load(Sheet(wires=[through,branch]))
        self.assertEqual(len(view._sheet.wires),3)
        self.assertTrue(view._wire_items[branch.id].endpoint_dots[0])
        net=build_netlist(view._sheet); self.assertEqual(net.wires[through.id],net.wires[branch.id])
        self.assertEqual(sum(w.group_id=="asset" for w in view._sheet.wires),2)
        crossing=[Wire(300,400,500,400),Wire(400,300,400,500)]
        view=self.load(Sheet(wires=crossing)); self.assertEqual(len(view._sheet.wires),2)
        net=build_netlist(view._sheet); self.assertNotEqual(net.wires[crossing[0].id],net.wires[crossing[1].id])

    def test_component_anchored_end_does_not_join_an_overlapping_route(self):
        b=Bench(); source=b.add("Bateria","5","V"); resistor=b.add("Rezystor","1000","Ω")
        b.connect(source,0,resistor,0); b.connect(source,1,resistor,1)
        view=self.load(Sheet(components=b.components,wires=b.wires))
        self.assertEqual(len(view._sheet.wires),2)
        result=Circuit(view._sheet).step(); self.assertAlmostEqual(result.currents[resistor.id],.005)
    def test_asset_rotation_preserves_relative_geometry_and_wire(self):
        b=Bench(); a=b.add("Rezystor","330","Ω"); z=b.add("Rezystor","1000","Ω")
        a.x,a.y=400,300; z.x,z.y=600,300
        for c in b.components: c.properties["asset_group"]="group"
        b.connect(a,1,z,0); b.wires[0].group_id="group"
        view=self.load(Sheet(components=b.components,wires=b.wires))
        for item in view._component_items.values(): item.setSelected(True)
        view.rotate_selected_components()
        self.assertEqual((a.x,a.y,z.x,z.y),(500,200,500,400))
        self.assertEqual((a.rotation,z.rotation),(90,90))
        self.assertEqual(b.wires[0].start_x,500)
        for _ in range(3): view.rotate_selected_components()
        self.assertEqual((a.x,a.y,z.x,z.y),(400,300,600,300))
    def test_socket_row_below_all_gpio_labels(self):
        b=Bench(); board=b.add("Raspberry Pi 5"); item=ComponentItem(board)
        body=item.connector_body()
        regions=socket_regions(item,body)
        self.assertEqual(len(regions),4)
        self.assertTrue(all(rect.top()>max(p.y for p in item.definition.pins) for _,rect in regions))
        self.assertTrue(all(item.boundingRect().contains(rect) for _,rect in regions))
    def test_favorite_shortcuts_and_reuse(self):
        b=Bench(); c=b.add("Rezystor","330","Ω"); c.x,c.y=400,300
        view=self.load(Sheet(components=b.components)); view._component_items[c.id].setSelected(True); view.setFocus(); APP.processEvents()
        with patch("app.ui.main_window.save_settings") as saved:
            QTest.keyClick(view,Qt.Key.Key_F); self.assertTrue(saved.called)
        self.assertIn(c.library_id,self.window.settings.favorite_components)
        with patch.object(self.window,"open_library") as opened:
            QTest.keyClick(view,Qt.Key.Key_F,Qt.KeyboardModifier.ShiftModifier)
            opened.assert_called_with(5)
        menu=QMenu(); self.window._populate_library_menu(menu,5,None)
        self.assertEqual(menu.actions()[0].data(),c.library_id)
        added=self.window.add_favorite(c.library_id)
        self.assertEqual(added.value,"330"); self.assertNotEqual(added.id,c.id)
        self.assertIsNot(added.properties,c.properties)

    def test_usb_attached_plugs_start_at_their_actual_sockets(self):
        sheet=example("usb_c_led"); self.load(sheet); self.window.show_simulation(); APP.processEvents()
        sim=self.window.simulation_window
        cable=sim.usb_cables[0]
        for plug in cable.plugs:
            cid=cable.component.properties["usb_"+plug.side.lower()+"_target"]
            target=next(point for identity,point in cable.targets(plug) if identity==cid)
            self.assertEqual(plug.pos(),target)
        sim.close()

    def test_search_shows_category_without_changing_placement_identity(self):
        from PySide6.QtWidgets import QDialog,QListWidget,QLineEdit
        def inspect(dialog):
            dialog.findChild(QLineEdit).setText("Rezystor")
            entries=dialog.findChild(QListWidget)
            self.assertGreater(entries.count(),0)
            self.assertTrue(all("Elementy elektroniczne" in entries.item(i).text() for i in range(entries.count())))
            self.assertTrue(all(get_definition(entries.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(entries.count())))
            return 0
        with patch.object(QDialog,"exec",inspect): self.window.search_components()

    def test_saving_other_settings_keeps_favorites(self):
        from app.ui.settings_dialog import SettingsDialog
        with TemporaryDirectory() as directory:
            settings=AppSettings(default_directory=directory,default_code_directory=directory,favorite_components={"part":{"value":"330","properties":{}}})
            dialog=SettingsDialog(settings); dialog._accept()
            self.assertEqual(dialog.result_settings().favorite_components,settings.favorite_components)
            self.assertIsNot(dialog.result_settings().favorite_components,settings.favorite_components)
            dialog.close(); dialog.deleteLater()

    def test_meter_ui_allows_resistance_in_disconnected_led_island(self):
        b=Bench(); supply,ground=b.power(); powered=b.add("Rezystor","1000","Ω")
        b.connect(supply,0,powered,0); b.connect(powered,1,ground,0)
        r=b.add("Rezystor","330","Ω"); led=b.add("Dioda LED 3mm"); b.connect(r,1,led,0)
        for c,point in zip(b.components,((200,200),(200,480),(450,200),(600,350),(850,350))): c.x,c.y=point
        self.load(Sheet(components=b.components,wires=b.wires)); self.window.show_simulation(); sim=self.window.simulation_window
        sim.buzzer_sound_button.setChecked(True); sim.single_step(); sim.open_measurements(); panel=sim.measurement_panel
        panel.positive.setCurrentIndex(panel.positive.findData(panel.netlist.pins[r.id,0]))
        panel.negative.setCurrentIndex(panel.negative.findData(panel.netlist.pins[led.id,1]))
        panel.mode.setCurrentIndex(panel.mode.findData("Ω")); panel.refresh()
        self.assertEqual(panel.reading.text(),"2340 Ω")
        panel.positive.setCurrentIndex(panel.positive.findData(panel.netlist.pins[powered.id,0]))
        panel.negative.setCurrentIndex(panel.negative.findData(panel.netlist.pins[powered.id,1])); panel.refresh()
        self.assertIn("Odłącz zasilanie",panel.reading.text()); sim.close()

if __name__=="__main__": unittest.main()
