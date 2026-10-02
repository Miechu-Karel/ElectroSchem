"""Wyniki porównujemy z równaniami obwodów, nie tylko brakiem wyjątku."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from math import cos, sin, radians, sqrt
from copy import deepcopy
from app.core.models import ComponentInstance, Sheet, Wire, Project
from app.libraries.built_in import BUILT_IN_ITEMS, get_definition
from app.libraries.simulation_catalog import functionality_database
from app.libraries.emulator_catalog import PROFILES
from app.simulation.engine import Circuit, SimulationError, si_value
from app.simulation.netlist import build_netlist

BY_NAME = {d.name:d for d in BUILT_IN_ITEMS}


def component(name, x, y, value="", unit="", **properties):
    d = BY_NAME[name]
    return ComponentInstance(d.id,x,y,reference=f"C{x}_{y}",value=value,unit=unit or d.default_unit,properties=properties)


def pin(c, i):
    p = get_definition(c.library_id).pins[i]
    a = radians(c.rotation)
    return c.x+p.x*cos(a)-p.y*sin(a), c.y+p.x*sin(a)+p.y*cos(a)


def wire(a, ai, b, bi):
    start, end = pin(a,ai), pin(b,bi)
    return Wire(*start,*end,start_component_id=a.id,start_pin_index=ai,
                end_component_id=b.id,end_pin_index=bi,points=[list(start),list(end)])


def loop(*components):
    return Sheet(components=list(components), wires=[wire(a,1,b,0) for a,b in zip(components,components[1:]+components[:1])])


def led_circuit():
    battery=component("Bateria 9V",160,200,"5")
    resistor=component("Rezystor",400,120,"330")
    led=component("Dioda LED 3mm",620,240,color="red")
    sheet=Sheet(components=[battery,resistor,led],wires=[wire(battery,0,resistor,0),wire(resistor,1,led,0),wire(led,1,battery,1)])
    return sheet,battery,resistor,led


class SimulationTests(unittest.TestCase):
    def test_si_prefixes_and_invalid_units(self):
        for text,unit,expected in [("10 kΩ","Ω",10000),("100 nF","F",1e-7),("50 Hz","Hz",50),("20 mA","A",.02)]:
            self.assertAlmostEqual(si_value(text,unit),expected)
        for text,unit in [("","Ω"),("0","Ω"),("-3","V"),("nan","F"),("10 A","V")]:
            with self.assertRaises(ValueError):si_value(text,unit)

    def test_dc_ohms_law_and_source_current(self):
        source=component("Bateria 9V",100,100,"5")
        resistor=component("Rezystor",400,200,"1","kΩ")
        c=Circuit(loop(source,resistor))
        result=c.step()
        self.assertAlmostEqual(abs(result.currents[resistor.id]),.005)
        self.assertAlmostEqual(result.currents[source.id],-.005)
        self.assertFalse(result.faults)

    def test_led_current_is_physical_and_glows(self):
        sheet,source,resistor,led=led_circuit()
        c=Circuit(sheet)
        result=c.step()
        self.assertAlmostEqual(result.currents[led.id],3/340)
        self.assertGreater(result.brightness[led.id],.4)
        self.assertFalse(result.faults)

    def test_led_overcurrent_stops_next_step(self):
        sheet,_,resistor,led=led_circuit()
        resistor.value="1"
        c=Circuit(sheet)
        result=c.step()
        self.assertIn(led.id,result.faults)
        with self.assertRaises(SimulationError):c.step()

    def test_reverse_led_does_not_glow(self):
        sheet,source,_,led=led_circuit()
        source.value="3"
        for w in sheet.wires:
            if w.start_component_id==source.id:w.start_pin_index=1
            if w.end_component_id==source.id:w.end_pin_index=0
        # W tej próbie kotwice są celowo zmienione wraz ze współrzędnymi.
        for w in sheet.wires:
            if w.start_component_id==source.id:w.start_x,w.start_y=pin(source,w.start_pin_index)
            if w.end_component_id==source.id:w.end_x,w.end_y=pin(source,w.end_pin_index)
        result=Circuit(sheet).step()
        self.assertEqual(result.brightness[led.id],0)
        self.assertFalse(result.faults)

    def test_rc_charge_matches_backward_euler(self):
        source=component("Bateria 9V",100,100,"5")
        r=component("Rezystor",400,100,"1","kΩ")
        cap=component("Kondensator Ceramiczny",600,200,"1","µF",voltage="10 V")
        sheet=Sheet(components=[source,r,cap],wires=[wire(source,0,r,0),wire(r,1,cap,0),wire(cap,1,source,1)])
        c=Circuit(sheet)
        for _ in range(10):result=c.step(.0001)
        voltage=result.voltages[c.netlist.pins[cap.id,0]]-result.voltages[c.netlist.pins[cap.id,1]]
        self.assertAlmostEqual(voltage,5*(1-(1/1.1)**10),places=7)

    def test_capacitor_overvoltage_and_polarity(self):
        for name,reverse in [("Kondensator Ceramiczny",False),("Kondensator Elektrolityczny",True)]:
            source=component("Bateria 9V",100,100,"9")
            cap=component(name,400,200,"10","µF",voltage="6.3 V" if not reverse else "25 V")
            sheet=loop(source,cap)  # Pierwszy pin kondensatora otrzymuje minus źródła.
            circuit=Circuit(sheet)
            result=circuit.step()
            if reverse:
                self.assertIn(cap.id,result.warnings)
                self.assertFalse(result.faults)
                circuit.step()  # A risk warning must not latch a hard fault.
            else:
                self.assertIn(cap.id,result.faults)

    def test_inductor_ramp(self):
        source=component("Bateria 9V",100,100,"5")
        coil=component("Cewka Indukcyjna",400,100,"1","H")
        c=Circuit(loop(source,coil))
        for _ in range(10):result=c.step(.001)
        self.assertAlmostEqual(abs(result.currents[coil.id]),.05)

    def test_ac_rms_and_time_resolution_guard(self):
        source=component("Źródło napięcia przemiennego",100,100,"5",sim_frequency="50 Hz")
        r=component("Rezystor",400,200,"1","kΩ")
        c=Circuit(loop(source,r))
        for _ in range(50):result=c.step(.0001)
        self.assertAlmostEqual(abs(result.currents[r.id]),sqrt(2)*5/1000)
        with self.assertRaises(SimulationError):c.step(.01)

    def test_switch_on_off_and_lamp(self):
        source=component("Bateria 9V",100,100,"5")
        switch=component("Łącznik ON/OFF",400,100)
        lamp=component("Żarówka",600,200,"1",sim_rated_voltage="5 V")
        c=Circuit(loop(source,switch,lamp))
        self.assertLess(c.step().brightness[lamp.id],1e-10)
        next(d for d in c.devices if d.kind=="switch").closed=True
        for _ in range(300):result=c.step(.001)
        self.assertGreater(result.brightness[lamp.id],.99)

    def test_required_value_unsupported_and_float_errors(self):
        sheet,_,resistor,_=led_circuit()
        resistor.value=""
        with self.assertRaisesRegex(SimulationError,"parameters"):Circuit(sheet)
        resistor.value="330"
        sheet.components.append(component("Układ MCP2008 (niezweryfikowany)",900,400))
        self.assertIn(sheet.components[-1].id,Circuit(sheet).ignored_components)
        sheet.components[-1]=component("Rezystor",900,400,"100")
        self.assertIn(sheet.components[-1].id,Circuit(sheet).ignored_components)

    def test_short_and_conflicting_sources_fail_not_fabricate_result(self):
        source=component("Bateria 9V",100,100,"5")
        c=Circuit(Sheet(components=[source],wires=[wire(source,0,source,1)]))
        with self.assertRaises(SimulationError):c.step()

    def test_crossing_wires_remain_separate(self):
        sheet=Sheet(wires=[Wire(0,0,100,100),Wire(0,100,100,0)])
        net=build_netlist(sheet)
        self.assertNotEqual(*net.wires.values())
        sheet.wires[1].start_x=sheet.wires[1].start_y=0
        net=build_netlist(sheet)
        self.assertEqual(*net.wires.values())

    def test_rotation_and_stable_pin_numbers(self):
        r=component("Rezystor",100,100,"100")
        r.rotation=90
        w=Wire(*pin(r,0),200,200,start_component_id=r.id,start_pin_index=1,start_pin_number="1")
        net=build_netlist(Sheet(components=[r],wires=[w]))
        self.assertEqual(net.pins[r.id,0],net.wires[w.id])
        self.assertNotEqual(net.pins[r.id,1],net.wires[w.id])

    def test_every_component_and_board_has_explicit_status(self):
        self.assertEqual(len(functionality_database()),145)
        boards=[d.name for d in BUILT_IN_ITEMS if d.category=="Mikrokontrolery i SBC"]
        self.assertEqual(set(boards),set(PROFILES))
        self.assertFalse(PROFILES["Raspberry Pi 5"].ready)

    def test_model_does_not_modify_document_and_properties_roundtrip(self):
        sheet,_,_,_=led_circuit()
        project=Project(sheets=[sheet])
        before=deepcopy(project.to_dict())
        Circuit(sheet).step()
        self.assertEqual(before,project.to_dict())
        self.assertEqual(Project.from_dict(before).sheets[0].components[2].properties["color"],"red")


if __name__=="__main__":unittest.main()
