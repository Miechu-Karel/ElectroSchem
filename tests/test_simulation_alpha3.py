"""Transient regressions for transistor oscillators and capacitor startup."""
from copy import deepcopy
import unittest

from test_simulation_alpha2 import Bench
from app.simulation.engine import Circuit, SimulationError


def astable():
    """Same electrical topology/values as the reported two-LED PN2222 circuit.

    Build it locally so regression coverage never depends on a user's file
    path, private document or random UUIDs. Both sides have equal values;
    only the documented automatic startup charge breaks exact symmetry.
    """
    b = Bench()
    supply, ground = b.power()
    transistors = [b.add("Tranzystor NPN PN2222") for _ in range(2)]
    leds = [b.add("Dioda LED 5mm", color=color) for color in ("green", "red")]
    capacitors = [b.add("Kondensator Elektrolityczny", "10", "µF", voltage="50 V") for _ in range(2)]
    for i, c in enumerate(b.components):
        c.id = f"astable-{i}"
    for i in range(2):
        load = b.add("Rezystor", "330", "Ω")
        base = b.add("Rezystor", "100", "kΩ")
        b.connect(supply, 0, load, 0)
        b.connect(load, 1, leds[i], 0)
        b.connect(leds[i], 1, transistors[i], "C")
        b.connect(transistors[i], "E", ground, 0)
        b.connect(supply, 0, base, 0)
        b.connect(base, 1, transistors[i], "B")
        b.connect(capacitors[i], 0, transistors[i], "C")
        b.connect(capacitors[i], 1, transistors[1-i], "B")
    return b.circuit(), leds, capacitors


class Alpha3Tests(unittest.TestCase):
    def test_symmetric_astable_repeatedly_alternates_without_fault(self):
        circuit, leds, _ = astable()
        before = deepcopy(circuit.sheet)
        last = None
        transitions = []
        dark = [False, False]
        for _ in range(6000):
            r = circuit.step(.001)
            self.assertFalse(r.faults)
            levels = [r.brightness[c.id] for c in leds]
            for i in range(2):
                dark[i] |= levels[i] < .001
            if abs(levels[0]-levels[1]) > .1:
                state = levels[0] > levels[1]
                if state != last:
                    transitions.append(r.time)
                    last = state
        self.assertGreaterEqual(len(transitions), 6)
        self.assertTrue(all(dark), "Both LEDs must actually turn off between pulses")
        periods = [b-a for a, b in zip(transitions[-5:], transitions[-4:])]
        self.assertLess(max(periods)-min(periods), .01)
        self.assertEqual(circuit.sheet, before)

    def test_initial_charge_reproducible_and_explicit_zero_respected(self):
        first, _, caps = astable()
        second = Circuit(first.sheet)
        get = lambda c: [d.previous for d in c.devices if d.kind == "polar_capacitor"]
        self.assertEqual(get(first), get(second))
        self.assertNotEqual(*get(first))
        self.assertTrue(all(abs(v) <= .1 for v in get(first)))
        caps[0].properties["sim_initial_voltage"] = "0 V"
        caps[1].properties["sim_initial_voltage"] = "-10 mV"
        self.assertEqual(get(Circuit(first.sheet)), [0, -.01])
        caps[0].properties["sim_initial_voltage"] = "invalid"
        with self.assertRaises(SimulationError):
            Circuit(first.sheet)

    def test_beta_affects_current_and_cutoff_remains_off(self):
        currents = []
        for beta in (0, 20, 100):
            b = Bench()
            s, g = b.power()
            q = b.add("Tranzystor NPN PN2222", sim_gain=str(beta or 100))
            load = b.add("Rezystor", "100", "Ω", sim_max_power="1 W")
            base = b.add("Rezystor", "100", "kΩ")
            b.connect(s, 0, load, 0)
            b.connect(load, 1, q, "C")
            b.connect(q, "E", g, 0)
            b.connect(s if beta else g, 0, base, 0)
            b.connect(base, 1, q, "B")
            r = b.circuit().step()
            self.assertFalse(r.faults)
            currents.append(r.currents[load.id])
        self.assertLess(abs(currents[0]), 1e-8)
        self.assertGreater(currents[2], currents[1]*4.5)


if __name__ == "__main__":
    unittest.main()
