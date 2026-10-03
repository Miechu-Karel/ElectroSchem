"""High-frequency AC must be sampled, not mistaken for a broken component."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from app.core.models import Sheet
from app.core.settings import AppSettings
from app.libraries.built_in import get_definition
from app.simulation.engine import Circuit, SimulationError
from app.ui.main_window import MainWindow
from test_simulation import component, loop, led_circuit

APP=QApplication.instance() or QApplication([])


def buzzer_sheet(frequency=2000,voltage='5'):
    source=component('Źródło napięcia przemiennego',160,100,voltage,sim_frequency=f'{frequency} Hz')
    buzzer=component('Buzzer Pasywny',440,200,sim_rated_voltage='5 V')
    return loop(source,buzzer),buzzer


class PatchAlpha2Tests(unittest.TestCase):
    def test_short_switch_name_preserves_legacy_library_id_and_pins(self):
        definition=get_definition('moduły-i-interfejsy-łącznik-on-off')
        self.assertEqual(definition.name,'Łącznik')
        self.assertEqual(definition.name_en,'Switch')
        self.assertEqual([p.number for p in definition.pins],['1','2'])
        self.assertEqual(definition.symbol,'spst')

    def test_two_kilohertz_buzzer_tone_without_false_damage(self):
        sheet,buzzer=buzzer_sheet()
        circuit=Circuit(sheet)
        dt=circuit.maximum_time_step()
        self.assertLess(dt,.0001)
        for _ in range(600):
            result=circuit.step(dt)
            self.assertFalse(result.faults)
        self.assertAlmostEqual(result.sounds[buzzer.id]['frequency'],2000,delta=50)
        self.assertGreater(result.sounds[buzzer.id]['level'],.1)

    def test_invalid_sampling_does_not_damage_or_advance_any_island(self):
        fast,_=buzzer_sheet()
        healthy,_,_,_=led_circuit()
        for item in healthy.components: item.x+=800; item.y+=400
        # Anchored wires use pin positions from their components.
        sheet=Sheet(components=fast.components+healthy.components,wires=fast.wires+healthy.wires)
        circuit=Circuit(sheet)
        self.assertEqual(len(circuit.parts),2)
        with self.assertRaises(SimulationError): circuit.step(.0001)
        self.assertFalse(circuit.result.faults)
        self.assertTrue(all(not part.result.faults and part.time==0 for part in circuit.parts))
        self.assertEqual(circuit.time,0)
        self.assertFalse(circuit.step(circuit.maximum_time_step()).faults)

    def test_physical_overvoltage_is_still_a_fault(self):
        sheet,buzzer=buzzer_sheet(voltage='20')
        circuit=Circuit(sheet)
        for _ in range(100):
            result=circuit.step(circuit.maximum_time_step())
            if result.faults: break
        self.assertIn(buzzer.id,result.faults)

    def test_sandbox_reduces_step_and_rejects_larger_manual_step(self):
        window=MainWindow(AppSettings(fault_effect='mini',window_mode='windowed'),start_setup=False)
        try:
            sheet,buzzer=buzzer_sheet()
            window.project.sheets=[sheet]; window._rebuild_tabs(); window.show_simulation()
            sim=window.simulation_window
            self.assertIsNotNone(sim.circuit,sim.log.toPlainText())
            self.assertLessEqual(sim.dt.value()/1000,sim.circuit.maximum_time_step())
            sim.dt.setValue(1)
            self.assertLessEqual(sim.dt.value()/1000,sim.circuit.maximum_time_step())
            for _ in range(150): sim.single_step()
            self.assertFalse(sim.circuit.result.faults)
            self.assertTrue(sim.run_button.isEnabled())
            self.assertGreater(sim.circuit.result.sounds[buzzer.id]['frequency'],1900)
        finally:
            window._saved_state=deepcopy(window.project.to_dict())
            with patch.object(window,'_confirm_discard',return_value=True): window.close()
            window.deleteLater(); APP.processEvents()
