import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from app.core.models import Project,Sheet,ComponentInstance,Wire
from app.core.editor_commands import execute_batch
from app.core.i2c_address import parse_address
from app.services.power_recipe import commands,matches,OUTPUTS
from app.libraries.built_in import AVAILABLE_ITEMS,get_definition
from app.simulation.engine import Circuit
from app.ui.usb_keyboard import UsbKeyboard
from test_simulation import wire

APP=QApplication.instance() or QApplication([])

class RC3Tests(unittest.TestCase):
    def test_power_recipe_has_distinct_outputs_and_rotated_goldpins(self):
        project=execute_batch(Project(sheets=[Sheet(paper_size='A3')]),0,commands())
        sheet=project.sheets[0]; by_ref={c.reference:c for c in sheet.components}
        circuit=Circuit(sheet)
        nodes=[circuit.netlist.pins[by_ref[f'J{i}'].id,1] for i in range(5)]
        self.assertEqual(len(set(nodes)),5)
        ground=circuit.netlist.pins[by_ref['J_GND'].id,1]
        self.assertNotIn(ground,nodes)
        for i,(voltage,current) in enumerate(OUTPUTS):
            self.assertEqual(by_ref[f'J{i}'].rotation,270)
            definition=next(d for d in AVAILABLE_ITEMS if d.name=='Rezystor')
            load=ComponentInstance(definition.id,2000+400*i,2000,reference=f'LOAD{i}',value=str(voltage/current),unit='Ω',properties={'sim_max_power':'100 W'})
            sheet.components.append(load)
            sheet.wires.extend((wire(by_ref[f'J{i}'],1,load,0),wire(load,1,by_ref['J_GND'],1)))
        circuit=Circuit(sheet)
        for _ in range(20): result=circuit.step(.0001)
        self.assertFalse(result.faults)
        for i,(voltage,current) in enumerate(OUTPUTS):
            v=result.voltages[circuit.netlist.pins[by_ref[f'J{i}'].id,1]]-result.voltages[circuit.netlist.pins[by_ref['J_GND'].id,1]]
            self.assertAlmostEqual(v,voltage,delta=voltage*.06)
        self.assertTrue(matches('USB-C: 3.3V,5V,9V,12V,25V każde oprócz 25V max 1,5A, a 25V 1A'))
        self.assertFalse(matches('USB-C: 3.3V,5V,9V,12V,25V każde oprócz 25V max 2A, a 25V 1A'))

    def test_full_keyboard_and_one_shot_modifiers(self):
        window=Mock(); window.t=lambda en,pl:pl
        device=Mock(); device.state={}
        keyboard=UsbKeyboard(window,device)
        self.assertEqual(len(keyboard.buttons),104)
        keyboard.buttons['Shift'].click(); keyboard.buttons['a'].click(); keyboard.buttons['b'].click()
        self.assertEqual(keyboard.entry.text(),'Ab'); self.assertFalse(keyboard.shift)
        keyboard.buttons['AltGr'].click(); keyboard.buttons['a'].click(); keyboard.buttons['a'].click()
        self.assertEqual(keyboard.entry.text(),'Abąa'); self.assertFalse(keyboard.altgr)
        keyboard.buttons['Alt'].click(); keyboard.buttons['Num1'].click()
        self.assertFalse(keyboard.alt); self.assertTrue(keyboard.entry.text().endswith('1'))
        keyboard.close()

    def test_hex_address_and_no_breadboard_in_catalog(self):
        self.assertEqual(parse_address('0x27'),39); self.assertEqual(parse_address('39'),39)
        self.assertEqual(parse_address('0x7F'),127)
        with self.assertRaises(ValueError): parse_address('0x80')
        self.assertNotIn('Płytka stykowa',{d.name for d in AVAILABLE_ITEMS})
        from test_simulation_alpha2 import Bench
        from app.ui.properties_dialog import ComponentPropertiesDialog
        from app.libraries.simulation_catalog import behavior_for
        definition=next(d for d in AVAILABLE_ITEMS if behavior_for(d).kind=='lcd_i2c')
        bench=Bench(); lcd=bench.add(definition.name,sim_address='39')
        dialog=ComponentPropertiesDialog(lcd,definition,'pl')
        self.assertEqual(dialog.simulation_fields['sim_address'].text(),'0x27')
        dialog.simulation_fields['sim_address'].setText('3F'); dialog.accept()
        self.assertEqual(dialog.values['simulation_properties']['sim_address'],'0x3F')
        dialog.close()

    def test_recipe_in_assistant_uses_no_provider_and_requires_accept(self):
        from app.ui.main_window import MainWindow
        from app.ui.command_panel import CommandPanel
        from app.core.settings import AppSettings
        from PySide6.QtWidgets import QMessageBox
        window=MainWindow(AppSettings(language='pl',ai_provider='local',local_ai_model='test'),start_setup=False)
        panel=CommandPanel(window)
        panel.prepare()  # Existing empty working session after an earlier failed request.
        panel.prompt.setPlainText('USB-C: 3.3V,5V,9V,12V,25V każde oprócz 25V max 1,5A, a 25V 1A')
        try:
            with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(panel.client,'start') as drawing,patch.object(panel.planner,'start') as planning:
                panel.send_request()
                drawing.assert_not_called(); planning.assert_not_called()
            self.assertFalse(window.project.sheets[0].components)
            self.assertTrue(panel.session.working.sheets[0].components)
            self.assertEqual(panel.session.working.sheets[0].paper_size,'A3')
            self.assertFalse(panel.preview.image.isNull())
            self.assertEqual(panel.simulation_report['status'],'sampled')
        finally:
            panel.close(); window._saved_state=window.project.to_dict(); window.close()
