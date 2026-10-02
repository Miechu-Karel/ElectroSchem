"""Regresje zasilania oraz liczbowe/stanowe testy nowych rodzin modeli."""
import unittest
from copy import deepcopy
from dataclasses import asdict
from app.core.models import Sheet
from app.libraries.built_in import get_definition
from app.simulation.engine import Circuit, SimulationError
from test_simulation import component, wire


class Bench:
    def __init__(self): self.components=[]; self.wires=[]
    def add(self,name,value="",unit="",**props):
        c=component(name,300+len(self.components)*500,300,value,unit,**props)
        self.components.append(c)
        return c
    def connect(self,a,ap,b,bp):
        def index(c,p):
            return p if isinstance(p,int) else next(i for i,pin in enumerate(get_definition(c.library_id).pins) if pin.name==p)
        self.wires.append(wire(a,index(a,ap),b,index(b,bp)))
    def circuit(self): return Circuit(Sheet(components=self.components,wires=self.wires))
    def power(self): return self.add("Szyna Zasilania +5V"),self.add("Masa GND")


class Alpha2Tests(unittest.TestCase):
    def test_rails_supply_correct_voltage_and_common_ground(self):
        for name,voltage in (("+5V",5),("+3.3V",3.3),("+12V",12),("VCC",7)):
            b=Bench(); supply=b.add("Szyna Zasilania "+name,sim_voltage="7 V"); ground=b.add("Masa GND")
            r=b.add("Rezystor","1","kΩ"); ground2=b.add("Masa GND")
            b.connect(supply,0,r,0); b.connect(r,1,ground2,0)
            c=b.circuit(); result=c.step()
            self.assertAlmostEqual(result.currents[r.id],voltage/1000)
            self.assertEqual(c.netlist.pins[ground.id,0],c.netlist.pins[ground2.id,0])
            self.assertFalse(result.faults)

    def test_duplicate_rails_share_source_and_conflicts_are_reported(self):
        b=Bench(); s,g=b.power(); second=b.add("Szyna Zasilania +5V"); r=b.add("Rezystor","1","kΩ")
        b.connect(second,0,r,0); b.connect(r,1,g,0)
        c=b.circuit(); self.assertEqual(len(c.sources),1)
        self.assertAlmostEqual(c.step().currents[r.id],.005)
        other=b.add("Szyna Zasilania +12V"); b.connect(other,0,s,0)
        with self.assertRaisesRegex(SimulationError,"Conflicting"): b.circuit()

    def test_rail_requires_ground_and_no_short_is_hidden(self):
        b=Bench(); s=b.add("Szyna Zasilania +5V")
        with self.assertRaisesRegex(SimulationError,"GND"): b.circuit()
        g=b.add("Masa GND"); b.connect(s,0,g,0)
        with self.assertRaises(SimulationError): b.circuit().step()

    def test_potentiometer_divider_and_end_positions(self):
        for position in (0,.25,.75,1):
            b=Bench(); s,g=b.power(); pot=b.add("Potencjometr Obrotowy","10","kΩ",sim_position=str(position))
            b.connect(s,0,pot,"1"); b.connect(g,0,pot,"3")
            c=b.circuit(); result=c.step()
            node=c.netlist.pins[pot.id,2]
            self.assertAlmostEqual(result.voltages[node],5*(1-position),places=5)
        pot.properties["sim_position"]="1.2"
        with self.assertRaisesRegex(SimulationError,"parameters"): b.circuit()

    def test_npn_correct_pin_mapping_switches_load_and_draws_base_current(self):
        for name in ("Tranzystor NPN PN2222","Tranzystor NPN BC547"):
            b=Bench(); s,g=b.power(); q=b.add(name); load=b.add("Rezystor","1","kΩ"); base=b.add("Rezystor","10","kΩ")
            for a,ap,z,zp in ((s,0,load,0),(load,1,q,"C"),(q,"E",g,0),(s,0,base,0),(base,1,q,"B")): b.connect(a,ap,z,zp)
            c=b.circuit(); result=c.step()
            self.assertGreater(result.currents[load.id],.0049)
            self.assertGreater(result.currents[base.id],.0004)
            self.assertAlmostEqual(-result.currents[s.id],result.currents[load.id]+result.currents[base.id],places=7)
            self.assertFalse(result.faults)

    def test_pnp_and_mosfets_switch(self):
        for name,symbol in (("Tranzystor PNP BC557","pnp"),("Tranzystor N-MOSFET IRF540N","nmos"),("Tranzystor P-MOSFET","pmos")):
            b=Bench(); s,g=b.power(); q=b.add(name); load=b.add("Rezystor","1","kΩ")
            if symbol == "pnp":
                rb=b.add("Rezystor","10","kΩ"); b.connect(rb,0,g,0); b.connect(rb,1,q,"B")
                b.connect(q,"E",s,0); b.connect(q,"C",load,0); b.connect(load,1,g,0)
            else:
                high=symbol=="pmos"
                b.connect(q,"S",s if high else g,0); b.connect(q,"G",g if high else s,0)
                b.connect(q,"D",load,0); b.connect(load,1,g if high else s,0)
            result=b.circuit().step()
            self.assertGreater(abs(result.currents[load.id]),.0049)

    def test_zener_clamps_in_reverse(self):
        b=Bench(); s=b.add("Szyna Zasilania +12V"); g=b.add("Masa GND")
        r=b.add("Rezystor","1","kΩ"); z=b.add("Dioda Zenera")
        b.connect(s,0,r,0); b.connect(r,1,z,"K"); b.connect(z,"A",g,0)
        c=b.circuit(); result=c.step()
        self.assertAlmostEqual(result.currents[r.id],(12-5.1)/1010,places=7)
        self.assertFalse(result.faults)

    def test_rgb_independent_channels(self):
        b=Bench(); s,g=b.power(); led=b.add("Dioda RGB")
        b.connect(led,"K",g,0); b.connect(led,"G",g,0); b.connect(led,"B",g,0)
        r=b.add("Rezystor","330"); b.connect(s,0,r,0); b.connect(r,1,led,"R")
        result=b.circuit().step()
        self.assertGreater(result.rgb[led.id][0],.4)
        self.assertEqual(result.rgb[led.id][1:],(0,0))

    def test_all_gate_truth_tables(self):
        tables={"AND":[0,0,0,1],"OR":[0,1,1,1],"NAND":[1,1,1,0],"NOR":[1,0,0,0],"XOR":[0,1,1,0],"XNOR":[1,0,0,1]}
        for gate,expected in tables.items():
            for combination,value in enumerate(expected):
                b=Bench(); s,g=b.power(); q=b.add("Bramka "+gate)
                b.connect(q,"A",s if combination&2 else g,0); b.connect(q,"B",s if combination&1 else g,0)
                c=b.circuit(); result=c.step()
                self.assertAlmostEqual(result.voltages[c.netlist.pins[q.id,2]],5*value,places=6)

    def test_tactile_internal_pairs_and_click_state(self):
        b=Bench(); s,g=b.power(); sw=b.add("Przycisk Tact Switch"); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,sw,2); b.connect(sw,3,r,0); b.connect(r,1,g,0)
        c=b.circuit(); self.assertLess(c.step().currents[r.id],1e-8)
        next(d for d in c.devices if d.component.id==sw.id).closed=True
        self.assertAlmostEqual(c.step().currents[r.id],.005,places=6)

    def test_regulator_output_voltage_and_input_load(self):
        b=Bench(); s=b.add("Szyna Zasilania +12V"); g=b.add("Masa GND")
        reg=b.add("Stabilizator Liniowy LM7805"); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,reg,"IN"); b.connect(g,0,reg,"GND"); b.connect(reg,"OUT",r,0); b.connect(r,1,g,0)
        result=b.circuit().step()
        self.assertAlmostEqual(result.currents[r.id],5/1000.1,places=7)
        self.assertAlmostEqual(-result.currents[s.id],result.currents[r.id]+12/10000,places=7)

    def test_relay_pickup_and_release(self):
        b=Bench(); s,g=b.power(); rel=b.add("Przekaźnik Elektromechaniczny 5V"); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,rel,"COIL+"); b.connect(g,0,rel,"COIL−"); b.connect(s,0,rel,"COM"); b.connect(rel,"NO",r,0); b.connect(r,1,g,0)
        c=b.circuit(); result=c.step()
        self.assertGreater(result.currents[r.id],.0049)
        self.assertIn("ON",result.readings[rel.id])

    def test_sensor_stimulus_changes_output(self):
        b=Bench(); s,g=b.power(); sensor=b.add("Czujnik Ruchu PIR HC-SR501",sim_active="true")
        b.connect(s,0,sensor,"VCC"); b.connect(g,0,sensor,"GND")
        c=b.circuit(); result=c.step()
        self.assertAlmostEqual(result.voltages[c.netlist.pins[sensor.id,1]],5)

    def test_no_unimplemented_module_is_silently_accepted(self):
        b=Bench(); b.power(); b.add("Układ MCP2008 (niezweryfikowany)")
        with self.assertRaisesRegex(SimulationError,"no simulation model"): b.circuit()

    def test_timer555_astable_uses_external_rc(self):
        b=Bench(); s,g=b.power(); timer=b.add("Układ Scalony NE555")
        ra=b.add("Rezystor","1","kΩ"); rb=b.add("Rezystor","10","kΩ")
        cap=b.add("Kondensator Ceramiczny","1","µF",voltage="10 V")
        for a,ap,z,zp in ((s,0,timer,"VCC"),(s,0,timer,"RESET"),(g,0,timer,"GND"),(s,0,ra,0),(ra,1,timer,"DISCH"),(timer,"DISCH",rb,0),(rb,1,cap,0),(cap,0,timer,"TRIG"),(cap,0,timer,"THRES"),(cap,1,g,0)): b.connect(a,ap,z,zp)
        c=b.circuit(); timer_device=next(d for d in c.devices if d.kind=="timer555")
        transitions=[]; previous=False
        for _ in range(600):
            result=c.step(.0001); state=timer_device.state["on"]
            if state and not previous: transitions.append(result.time)
            previous=state
        self.assertGreaterEqual(len(transitions),3)
        self.assertAlmostEqual(transitions[-1]-transitions[-2],.693*(1000+2*10000)*1e-6,delta=.0006)
        self.assertFalse(result.faults)

    def test_opamp_follower_and_feedback(self):
        b=Bench(); s,g=b.power(); op=b.add("Układ Scalony LM358")
        a=b.add("Rezystor","10","kΩ"); z=b.add("Rezystor","10","kΩ")
        for first,fp,second,sp in ((s,0,op,"V+"),(g,0,op,"V−"),(s,0,a,0),(a,1,z,0),(z,1,g,0),(a,1,op,"IN1+"),(op,"OUT1",op,"IN1−"),(g,0,op,"IN2+"),(op,"OUT2",op,"IN2−")): b.connect(first,fp,second,sp)
        c=b.circuit(); result=c.step()
        out=next(d for d in c.devices if d.kind=="opamp").parameters["pins"]["OUT1"]
        self.assertAlmostEqual(result.voltages[out],2.5,places=4)

    def test_all_logic_packages_have_working_pin_maps(self):
        for code in ("74HC00","74HC02","74HC04","74HC08","74HC14","74HC32","74HC86"):
            b=Bench(); s,g=b.power(); chip=b.add("Bramka Logiczna "+code)
            b.connect(s,0,chip,"VCC"); b.connect(g,0,chip,"GND")
            definition=get_definition(chip.library_id)
            for pin in definition.pins:
                if pin.name.endswith(("A","B")): b.connect(g,0,chip,pin.name)
            c=b.circuit(); result=c.step()
            output=next(d for d in c.devices if d.kind=="logic_package").parameters["pins"]["1Y"]
            self.assertAlmostEqual(result.voltages[output],5 if code in {"74HC00","74HC02","74HC04","74HC14"} else 0,places=5)

    def test_dc_converter_balances_power(self):
        b=Bench(); s=b.add("Szyna Zasilania +12V"); g=b.add("Masa GND")
        converter=b.add("Przetwornik DC-DC Step-Down LM2596"); r=b.add("Rezystor","1","kΩ")
        b.connect(s,0,converter,"IN+"); b.connect(g,0,converter,"IN−"); b.connect(converter,"OUT+",r,0); b.connect(converter,"OUT−",r,1)
        c=b.circuit(); result=c.step()
        self.assertAlmostEqual(result.currents[r.id],5/1000.1,places=6)
        self.assertAlmostEqual(-12*result.currents[s.id]*.9,result.currents[r.id]**2*1000,places=6)

    def test_ldr_and_thermistor_resistance_responds_to_stimuli(self):
        for name,props,expected in (("Fotorezystor LDR",{"sim_light":"2"},.01),("Termistor NTC",{"sim_temperature":"298.15"},.005)):
            b=Bench(); s,g=b.power(); load=b.add(name,"1","kΩ",**props)
            b.connect(s,0,load,0); b.connect(g,0,load,1)
            self.assertAlmostEqual(b.circuit().step().currents[load.id],expected,places=7)

    def test_spi_mcp3008_reads_real_analog_node(self):
        b=Bench(); s,g=b.power(); adc=b.add("Przetwornik ADC MCP3008")
        analog=b.add("Bateria 9V","2.5")
        b.connect(analog,1,g,0); b.connect(analog,0,adc,"CH0")
        for pin in ("VDD","VREF"): b.connect(adc,pin,s,0)
        for pin in ("DGND","AGND",*[f"CH{i}" for i in range(1,8)]): b.connect(adc,pin,g,0)
        stimuli={}
        for pin in ("CLK","DIN","CS/SHDN"):
            source=b.add("Bateria 9V","5" if pin=="CS/SHDN" else "0.000001")
            b.connect(source,0,adc,pin); b.connect(source,1,g,0); stimuli[pin]=source.id
        c=b.circuit(); c.step()
        def set_pin(pin,high): next(d for d in c.devices if d.component.id==stimuli[pin]).parameters["value"]=5 if high else 0
        set_pin("CS/SHDN",False); c.step()
        out=next(d for d in c.devices if d.kind=="adc_spi").parameters["pins"]["DOUT"]
        received=0
        for byte in (1,128,0):
            for index in range(7,-1,-1):
                set_pin("DIN",bool(byte&(1<<index))); c.step()
                set_pin("CLK",True); result=c.step()
                received=(received<<1)|int(result.voltages[out]>2.5)
                set_pin("CLK",False); c.step()
        self.assertEqual(received&1023,512)

    def test_spi_pot_write_changes_divider_and_ignores_partial_word(self):
        from app.simulation.spi_devices import mcp41010
        state={}
        for byte in (0x11,64):
            for i in range(7,-1,-1):
                state=mcp41010(state,False,False,bool(byte&(1<<i)))
                state=mcp41010(state,False,True,bool(byte&(1<<i)))
        state=mcp41010(state,True,False,False)
        self.assertEqual(state["wiper"],64)
        for clock in (False,True): state=mcp41010(state,False,clock,True)
        state=mcp41010(state,True,False,False)
        self.assertEqual(state["wiper"],64)
        b=Bench(); s,g=b.power(); pot=b.add("Potencjometr Cyfrowy MCP41010","10","kΩ")
        for pin in ("VDD","PA0","CS"): b.connect(s,0,pot,pin)
        for pin in ("VSS","PB0","SCK","SI"): b.connect(g,0,pot,pin)
        c=b.circuit(); device=next(d for d in c.devices if d.kind=="digital_pot"); device.state=state
        result=c.step()
        self.assertAlmostEqual(result.voltages[device.parameters["pins"]["PW0"]],1.25,places=6)

    def test_clocked_flipflop_keeps_state_between_edges(self):
        b=Bench(); s,g=b.power(); chip=b.add("Przerzutnik 74HC74"); clock=b.add("Bateria 9V","0.000001")
        b.connect(clock,1,g,0); b.connect(clock,0,chip,"1CLK")
        for pin in ("VCC","1D","1PRE","1CLR","2PRE","2CLR"): b.connect(s,0,chip,pin)
        for pin in ("GND","2D","2CLK"): b.connect(g,0,chip,pin)
        c=b.circuit(); d=next(d for d in c.devices if d.kind=="flipflop")
        self.assertAlmostEqual(c.step().voltages[d.parameters["pins"]["1Q"]],0)
        source=next(d for d in c.sources if d.component.id==clock.id); source.parameters["value"]=5
        self.assertAlmostEqual(c.step().voltages[d.parameters["pins"]["1Q"]],5)
        source.parameters["value"]=0
        self.assertAlmostEqual(c.step().voltages[d.parameters["pins"]["1Q"]],5)

    def test_hbridge_drives_load_from_motor_supply(self):
        b=Bench(); s,g=b.power(); driver=b.add("Mostek H L298N"); load=b.add("Rezystor","1","kΩ")
        for pin in ("VS","VSS","ENA","IN1"): b.connect(s,0,driver,pin)
        for pin in ("GND","IN2","IN3","IN4","ENB","SENSE_A","SENSE_B"): b.connect(g,0,driver,pin)
        b.connect(driver,"OUT1",load,0); b.connect(driver,"OUT2",load,1)
        result=b.circuit().step()
        self.assertAlmostEqual(result.currents[load.id],5/1004,places=7)

    def test_stepper_driver_current_flows_through_both_windings(self):
        b=Bench(); s,g=b.power(); driver=b.add("Sterownik Silników Krokowych A4988"); motor=b.add("Silnik Krokowy NEMA 17")
        for pin in ("VMOT","VDD","RESET","SLEEP"): b.connect(s,0,driver,pin)
        for pin in ("GND","ENABLE","MS1","MS2","MS3","STEP","DIR"): b.connect(g,0,driver,pin)
        for a,z in (("1A","A+"),("1B","A−"),("2A","B+"),("2B","B−")): b.connect(driver,a,motor,z)
        c=b.circuit()
        for _ in range(100): result=c.step(.0001)
        d=next(d for d in c.devices if d.kind=="stepper_motor")
        self.assertAlmostEqual(d.state["phase0"],5/12,places=5)
        self.assertAlmostEqual(d.state["phase1"],5/12,places=5)
        self.assertFalse(result.faults)

    def test_scr_latches_until_main_current_stops(self):
        b=Bench(); s,g=b.power(); scr=b.add("Tyrystor"); load=b.add("Rezystor","330")
        trigger=b.add("Bateria 9V","2")
        b.connect(s,0,load,0); b.connect(load,1,scr,"A"); b.connect(scr,"K",g,0)
        b.connect(trigger,0,scr,"G"); b.connect(trigger,1,g,0)
        c=b.circuit(); c.step()
        gate=next(d for d in c.sources if d.component.id==trigger.id); gate.parameters["value"]=0
        self.assertGreater(c.step().currents[load.id],.01)
        power=next(d for d in c.sources if d.component.id==s.id); power.parameters["value"]=0
        c.step(); c.step(); power.parameters["value"]=5
        self.assertLess(c.step().currents[load.id],1e-8)

    def test_opto_input_current_switches_output(self):
        b=Bench(); s,g=b.power(); opt=b.add("Optoizolator PC817")
        r=b.add("Rezystor","330"); load=b.add("Rezystor","1","kΩ")
        for a,ap,z,zp in ((s,0,r,0),(r,1,opt,"A"),(opt,"K",g,0),(opt,"E",g,0),(opt,"C",load,1),(load,0,s,0)): b.connect(a,ap,z,zp)
        result=b.circuit().step()
        self.assertAlmostEqual(result.currents[r.id],3.8/340,places=6)
        self.assertAlmostEqual(result.currents[load.id],5/1010,places=6)

    def test_crystal_motional_branch_and_time_resolution(self):
        b=Bench(); s=b.add("Bateria 9V","1"); crystal=b.add("Kwarc Rezonator 8MHz","8","MHz")
        b.connect(s,0,crystal,0); b.connect(s,1,crystal,1)
        c=b.circuit()
        with self.assertRaisesRegex(SimulationError,"50"): c.step(.0001)
        result=c.step(1e-9)
        from math import pi
        inductance=1/((2*pi*8e6)**2*20e-15)
        expected=5e-12/1e-9+1/(30+inductance/1e-9+1e-9/20e-15)
        self.assertAlmostEqual(result.currents[crystal.id],expected,places=8)
        self.assertAlmostEqual(-result.currents[s.id],expected,places=8)

    def test_servo_decodes_pulse_width(self):
        b=Bench(); s,g=b.power(); servo=b.add("Serwomechanizm SG90"); pwm=b.add("Bateria 9V","0.000001")
        b.connect(s,0,servo,"VCC"); b.connect(g,0,servo,"GND"); b.connect(pwm,0,servo,"PWM"); b.connect(pwm,1,g,0)
        c=b.circuit(); c.step()
        stimulus=next(d for d in c.sources if d.component.id==pwm.id)
        stimulus.parameters["value"]=5
        for _ in range(15): c.step(.0001)
        stimulus.parameters["value"]=0; result=c.step(.0001)
        model=next(d for d in c.devices if d.kind=="servo")
        self.assertAlmostEqual(model.state["command"],90,places=5)
        self.assertIn("90",result.readings[servo.id])

    def test_models_do_not_mutate_source_document(self):
        b=Bench(); s,g=b.power(); pot=b.add("Potencjometr Suwakowy","1","kΩ")
        b.connect(s,0,pot,0); b.connect(g,0,pot,1)
        sheet=Sheet(components=b.components,wires=b.wires); before=deepcopy(asdict(sheet))
        Circuit(sheet).step()
        self.assertEqual(before,asdict(sheet))
