"""Wielokońcówkowe modele i ich liniowe odpowiedniki dla MNA.

Gałąź opisuje prąd a→b: g*(Va−Vb) + offset + Σ(k*Vcontrol).
To pozwala zachować prawa Kirchhoffa także dla tranzystora: prąd kolektora
wraca emiterem, a obciążenie wyjścia bramki jest pobierane z jej zasilania.
Stan trwały zapisujemy WYŁĄCZNIE po zbieżnym kroku, nie przy każdej iteracji.
"""
from dataclasses import dataclass, field
from math import exp, pi
from app.simulation.spi_devices import mcp3008, mcp41010


@dataclass
class Branch:
    a: int
    b: int
    g: float
    offset: float = 0.0
    controls: dict = field(default_factory=dict)

    def current(self, volts):
        return self.g*(volts.get(self.a, 0)-volts.get(self.b, 0))+self.offset+sum(k*volts.get(n, 0) for n, k in self.controls.items())


def logic(function, bits):
    base = function.removeprefix("n") if function in {"nand", "nor"} else function
    if base == "and": value = all(bits)
    elif base == "or": value = any(bits)
    elif base in {"xor", "xnor"}: value = sum(bits) % 2 == 1
    elif base == "not": return not bits[0]
    else: raise ValueError("Unknown logic function: " + function)
    return not value if function in {"nand", "nor", "xnor"} else value


def linearize(d, volts, ground, time, dt):
    """Buduje gałęzie według przybliżenia napięć, bez zmieniania dokumentu."""
    p, n, kind = d.parameters, d.parameters["pins"], d.kind
    branches = []
    trial = dict(d.state)
    def v(a, b=ground): return volts.get(a, 0)-volts.get(b, 0)
    def branch(a, b, g, offset=0, controls=None):
        item = Branch(a, b, g, offset, controls or {})
        branches.append(item)
        return item
    def resistor(a, b, resistance): return branch(a, b, 1/max(resistance, .001))
    def contact(a, b, closed): return branch(a, b, 1000 if closed else 1e-12)
    def diode(a, b, threshold):
        return branch(a, b, .1, -.1*threshold) if v(a,b) > threshold else branch(a,b,1e-12)
    def drive(out, low, high, state, enabled=True):
        # Połączenie z odpowiednią szyną zamiast niezależnego źródła energii.
        return branch(out, high if state else low, .04 if enabled else 1e-12)
    def powered(supply, low, load=10000):
        resistor(supply, low, load)
        return v(supply,low) > 1
    def inputs(pins, low):
        for pin in pins: branch(pin, low, 1e-12)

    if kind in {"ldr", "thermistor"}:
        resistance = p["value"] / p["sim_light"] if kind == "ldr" else p["value"]*exp(max(-60,min(60,p["sim_beta"]*(1/p["sim_temperature"]-1/298.15))))
        resistor(*d.nodes, resistance)
    elif kind == "potentiometer":
        resistor(n["1"], n["W"], p["value"]*p["sim_position"])
        resistor(n["W"], n["3"], p["value"]*(1-p["sim_position"]))
    elif kind == "zener":
        a,b=d.nodes
        if v(a,b) < -p["sim_breakdown"]: branch(a,b,.1,.1*p["sim_breakdown"])
        else: diode(a,b,p["sim_forward_voltage"])
    elif kind == "rgb":
        for channel in ("R", "G", "B"):
            diode(n["A"],n[channel],p["sim_forward_voltage"]) if "A" in n else diode(n[channel],n["K"],p["sim_forward_voltage"])
    elif kind in {"npn", "pnp"}:
        c,b,e=n["C"],n["B"],n["E"]
        sign = 1 if kind == "npn" else -1
        vb,vc = sign*v(b,e),sign*v(c,e)
        # Złącze BE ma 100 Ω rezystancji dynamicznej. Kolektor jest źródłem
        # zależnym beta*Ib, ograniczonym gałęzią nasycenia 1 Ω.
        ib = max(0,(vb-p["sim_vbe"])/100)
        if vc <= 0 or ib <= 0: branch(c,e,1e-12)
        else:
            # Continuous transition from beta-controlled current to a 1-ohm
            # saturation channel. Stamp both partial derivatives, so Newton
            # sees the same current law when evaluating and updating a step.
            target = p["sim_gain"]*ib
            denominator = vc+target
            current = target*vc/denominator
            gc = (target/denominator)**2
            gb = p["sim_gain"]/100*(vc/denominator)**2
            offset = sign*(current-gc*vc-gb*vb)
            branch(c,e,gc,offset,{b:gb,e:-gb})
        diode(b,e,p["sim_vbe"]) if sign == 1 else diode(e,b,p["sim_vbe"])
        # Ujednolicamy rezystancję BE z równaniem sterującym kolektorem.
        if branches[-1].g == .1:
            branches[-1].g=.01
            branches[-1].offset *= .1
    elif kind in {"nmos", "pmos"}:
        g,dr,s=n["G"],n["D"],n["S"]
        sign=1 if kind == "nmos" else -1
        # Płynne narastanie kanału na odcinku 1 V ogranicza oscylacje Newtona
        # w pobliżu progu; powyżej tego odcinka osiągamy zadane Rds(on).
        over=sign*v(g,s)-p["sim_threshold"]
        conductance=max(0,min(1,over))/p["sim_on_resistance"]
        controls={}
        offset=0
        if 0 < over < 1:
            derivative=sign*v(dr,s)/p["sim_on_resistance"]
            controls={g:derivative,s:-derivative}
            offset=-derivative*v(g,s)
        branch(dr,s,max(1e-12,conductance),offset,controls)
        inputs([g],s)
        diode(s,dr,.7) if sign == 1 else diode(dr,s,.7)
    elif kind in {"thyristor", "triac"}:
        a,b,g = d.nodes
        # SCR: bramka względem K. Triak: bramka względem MT1.
        reference = b if kind == "thyristor" else a
        gate=v(g,reference)
        triggered=(gate > p["sim_trigger"]) if kind == "thyristor" else abs(gate)>p["sim_trigger"]
        held=d.state.get("latched",False) and abs(d.state.get("main_current",0)) >= p["sim_holding"]
        on=(triggered or held) and (v(a,b)>0 if kind == "thyristor" else True)
        contact(a,b,on)
        resistor(g,reference,1000)
        trial["latched"]=on
    elif kind == "tactile":
        contact(d.nodes[0],d.nodes[2],True)
        contact(d.nodes[1],d.nodes[3],True)
        contact(d.nodes[0],d.nodes[1],d.closed)
    elif kind == "spdt":
        contact(n["COM"],n["A"],not d.closed)
        contact(n["COM"],n["B"],d.closed)
    elif kind == "relay":
        resistor(n["COIL+"],n["COIL−"],p["sim_coil_resistance"])
        threshold=p["sim_pickup"]*(.5 if d.state.get("on") else 1)
        on=abs(v(n["COIL+"],n["COIL−"])) >= threshold
        contact(n["COM"],n["NC"],not on)
        contact(n["COM"],n["NO"],on)
        trial["on"]=on
    elif kind == "opto":
        diode(n["A"],n["K"],p["sim_forward_voltage"])
        gain=.1*p["sim_ctr"]
        desired=max(0,gain*(v(n["A"],n["K"])-p["sim_forward_voltage"]))
        if "B" in n:
            # Exposed base: optical current feeds BE and can be shunted by
            # an external B-E resistor. Optical input remains galvanically isolated.
            c,b,e=n["C"],n["B"],n["E"]
            branch(c,b,1e-12,desired/101)
            diode(b,e,.7)
            branches[-1].g*=.1; branches[-1].offset*=.1
            vc=max(0,v(c,e)); ib=max(0,(v(b,e)-.7)/100); target=100*ib
            if vc>0 and target>0:
                denominator=vc+target; gc=(target/denominator)**2; gb=(vc/denominator)**2
                branch(c,e,gc,target*vc/denominator-gc*vc-gb*v(b,e),{b:gb,e:-gb})
            else: branch(c,e,1e-12)
            branch(n["NC"],e,1e-12)
        elif desired <= 0 or v(n["C"],n["E"]) <= 0: branch(n["C"],n["E"],1e-12)
        elif v(n["C"],n["E"])/10 < desired: branch(n["C"],n["E"],.1)
        else: branch(n["C"],n["E"],1e-12,-gain*p["sim_forward_voltage"],{n["A"]:gain,n["K"]:-gain})
    elif kind == "buzzer":
        resistor(*d.nodes,p["sim_resistance"])
    elif kind == "crystal":
        # W szeregowej gałęzi RLC eliminujemy wewnętrzne węzły algebraicznie.
        cm=p["sim_motional_capacitance"]
        inductance=1/((2*pi*p["value"])**2*cm)
        impedance=p["sim_series_resistance"]+inductance/dt+dt/cm
        memory=d.state.get("crystal_v",0)-inductance/dt*d.state.get("crystal_i",0)
        branch(*d.nodes,1/impedance,-memory/impedance)
        g=p["sim_parallel_capacitance"]/dt
        branch(*d.nodes,g,-g*d.state.get("terminal_v",0))
    elif kind == "logic_gate":
        inp=d.nodes[:-1]
        inputs(inp,ground)
        level=logic(p["symbol"][5:],[v(node)>p["sim_logic_voltage"]*.5 for node in inp])
        branch(d.nodes[-1],ground,.04,-.04*p["sim_logic_voltage"]*level)
    elif kind == "logic_package":
        low=n["GND"]
        high=n.get("VCC",n.get("VDD"))
        enabled=powered(high,low)
        name=p["name"]
        func=next((f for code,f in (("74HC00","nand"),("74HC02","nor"),("74HC04","not"),("74HC08","and"),("74HC14","not"),("74HC32","or"),("74HC86","xor"),("CD4093","nand")) if code in name))
        for i in range(1,7 if func == "not" else 5):
            pins=[n[f"{i}A"]] + ([] if func == "not" else [n[f"{i}B"]])
            inputs(pins,low)
            bits=[]
            for j,node in enumerate(pins):
                key=f"schmitt_{i}_{j}"
                fraction=(.3 if d.state.get(key) else .7) if ("74HC14" in name or "CD4093" in name) else .5
                bit=v(node,low)>v(high,low)*fraction
                bits.append(bit)
                trial[key]=bit
            drive(n[f"{i}Y"],low,high,logic(func,bits),enabled)
    elif kind == "regulator":
        high,low,out=n["IN"],n["GND"],n["OUT"]
        target=3.3 if "1117" in p["name"] else 12 if "7812" in p["name"] else 5
        vin=v(high,low)
        level=max(0,min(target,vin-p["sim_dropout"]))
        g=10
        if 0 < vin-p["sim_dropout"] < target:
            output=branch(out,low,g,g*p["sim_dropout"],{high:-g,low:g})
        else: output=branch(out,low,g,-g*level)
        # Prąd wyjścia pobieramy z wejścia (model stabilizatora liniowego).
        controls={out:-g,low:g}
        for node,k in output.controls.items(): controls[node]=controls.get(node,0)-k
        branch(high,low,0,-output.offset,controls)
        resistor(high,low,10000)
    elif kind == "timer555":
        low,high=n["GND"],n["VCC"]
        enabled=powered(high,low)
        resistor(high,n["CONT"],5000)
        resistor(n["CONT"],low,10000)
        inputs([n["TRIG"],n["THRES"],n["RESET"]],low)
        on=d.state.get("on",False)
        # Zdarzenie komparatora próbkujemy z końca poprzedniego kroku.
        # Przełączanie DISCH w środku Newtona cofałoby przekroczenie progu
        # i dawało naprzemienne ON/OFF bez punktu stałego przy przejściu.
        sampled=d.state.get("timer_inputs", {"CONT":v(high,low)*2/3,"TRIG":0,"THRES":0,"RESET":v(n["RESET"],low)})
        control=sampled["CONT"]
        if not enabled or sampled["RESET"]<.7: on=False
        elif sampled["TRIG"]<control*.5: on=True
        elif sampled["THRES"]>control: on=False
        drive(n["OUT"],low,high,on,enabled)
        contact(n["DISCH"],low,not on and enabled)
        trial["on"]=on
    elif kind == "opamp":
        low,high=n["V−"],n["V+"]
        enabled=powered(high,low)
        for i in (1,2):
            plus,minus,out=n[f"IN{i}+"],n[f"IN{i}−"],n[f"OUT{i}"]
            inputs([plus,minus],low)
            target=p["sim_gain"]*v(plus,minus)
            if not enabled or target<=0: drive(out,low,high,False,enabled)
            elif target>=v(high,low): drive(out,low,high,True)
            else: branch(out,low,.04,0,{plus:-.04*p["sim_gain"],minus:.04*p["sim_gain"]})
    elif kind in {"flipflop","shift_register"}:
        low,high=n["GND"],n["VCC"]
        enabled=powered(high,low)
        def bit(label): return v(n[label],low)>v(high,low)*.5
        def rising(label): return bit(label) and not d.state.get("edge_"+label,False)
        if kind == "flipflop":
            for i in (1,2):
                clr,pre=f"{i}CLR",f"{i}PRE"
                clock=f"{i}CLK"
                inputs([n[clr],n[pre],n[clock],n[f"{i}D"]],low)
                q=d.state.get(f"q{i}",False)
                if not bit(clr): q=False
                elif not bit(pre): q=True
                elif rising(clock): q=bit(f"{i}D")
                trial[f"invalid{i}"]=enabled and not bit(clr) and not bit(pre)
                drive(n[f"{i}Q"],low,high,q,enabled)
                drive(n[f"{i}/Q"],low,high,not q,enabled)
                trial[f"q{i}"]=q
                trial["edge_"+clock]=bit(clock)
        else:
            inputs([n[k] for k in ("SRCLR","SRCLK","RCLK","OE","SER")],low)
            shift=d.state.get("shift",0)
            if not bit("SRCLR"): shift=0
            elif rising("SRCLK"): shift=((shift<<1)|int(bit("SER")))&255
            # Jednoczesne zbocza: latch widzi poprzedni rejestr przesuwny.
            latch=d.state.get("shift",0) if rising("RCLK") else d.state.get("latch",0)
            for i,label in enumerate(("QA","QB","QC","QD","QE","QF","QG","QH")):
                drive(n[label],low,high,bool(latch&(1<<i)),enabled and not bit("OE"))
            drive(n["QH′"],low,high,bool(shift&128),enabled)
            trial.update(shift=shift,latch=latch,edge_SRCLK=bit("SRCLK"),edge_RCLK=bit("RCLK"))
    elif kind == "encoder":
        phase=int(time*p["sim_frequency"]*4)%4
        a,b=((False,False),(True,False),(True,True),(False,True))[phase]
        contact(n["A"],n["C"],a)
        contact(n["B"],n["C"],b)
        contact(n["SW1"],n["SW2"],d.closed)
    elif kind in {"adc_spi","digital_pot"}:
        low=n["DGND" if kind=="adc_spi" else "VSS"]
        high=n["VDD"]
        enabled=powered(high,low)
        cs_label,clock_label,data_label=("CS/SHDN","CLK","DIN") if kind=="adc_spi" else ("CS","SCK","SI")
        inputs([n[k] for k in (cs_label,clock_label,data_label)],low)
        cs=v(n[cs_label],low)>.5*v(high,low)
        clock=v(n[clock_label],low)>.5*v(high,low)
        data=v(n[data_label],low)>.5*v(high,low)
        if kind=="adc_spi":
            agnd=n["AGND"]
            inputs([n[f"CH{i}"] for i in range(8)]+[n["VREF"]],agnd)
            branch(agnd,low,1e-12)
            trial=mcp3008(d.state,cs or not enabled,clock,data,[v(n[f"CH{i}"],agnd) for i in range(8)],v(n["VREF"],agnd))
            state=trial.get("spi_out")
            drive(n["DOUT"],low,high,bool(state),enabled and not cs and state is not None)
        else:
            trial=mcp41010(d.state,cs or not enabled,clock,data)
            fraction=trial["wiper"]/256
            shutdown=trial.get("shutdown",False) or not enabled
            branch(n["PA0"],n["PW0"],1e-12 if shutdown else 1/max(.001,p["value"]*(1-fraction)))
            resistor(n["PB0"],n["PW0"],.001 if shutdown else p["value"]*fraction)
    elif kind == "hbridge":
        low,high=n["GND"],n["VS"]
        enabled=powered(n["VSS"],low)
        inputs([n[k] for k in ("IN1","IN2","IN3","IN4","ENA","ENB")],low)
        for channel,first in (("A",1),("B",3)):
            active=enabled and v(n["EN"+channel],low)>2
            for i in (first,first+1):
                state=v(n[f"IN{i}"],low)>2
                branch(n[f"OUT{i}"],high if state else n["SENSE_"+channel],.5 if active else 1e-12)
            branch(n["SENSE_"+channel],low,1e-12)
        branch(high,low,1e-12)
    elif kind == "stepper_driver":
        a4988="A4988" in p["name"]
        low=n["GND"]
        high=n["VMOT" if a4988 else "VM"]
        supply=n["VDD" if a4988 else "VIO"]
        enable=n["ENABLE" if a4988 else "EN"]
        enabled=powered(supply,low) and v(enable,low)<.5*v(supply,low)
        controls=[label for label in n if label not in {"GND","VMOT","VM","VDD","VIO","1A","1B","2A","2B","OA1","OA2","OB1","OB2"}]
        inputs([n[k] for k in controls],low)
        step=v(n["STEP"],low)>v(supply,low)*.5
        phase=d.state.get("phase",0)
        if a4988 and (v(n["RESET"],low)<1 or v(n["SLEEP"],low)<1):
            enabled=False
            phase=0
        elif step and not d.state.get("step",False):
            phase=(phase+(1 if v(n["DIR"],low)>v(supply,low)*.5 else -1))%4
        signs=((True,True),(False,True),(False,False),(True,False))[phase]
        for winding,positive in zip((("1A","1B"),("2A","2B")) if a4988 else (("OA1","OA2"),("OB1","OB2")),signs):
            for label,state in zip(winding,(positive,not positive)):
                branch(n[label],high if state else low,1 if enabled else 1e-12)
        branch(high,low,1e-12)
        trial.update(phase=phase,step=step)
        trial["unsupported_mode"]=any(v(n[label],low)>v(supply,low)*.5 for label in ("MS1","MS2","MS3") if label in n)
    elif kind == "converter":
        high,low,out,return_pin=n["IN+"],n["IN−"],n["OUT+"],n["OUT−"]
        contact(low,return_pin,True)
        vin=v(high,low)
        target=p["sim_output_voltage"]
        if "LM2596" in p["name"]: target=min(target,max(0,vin))
        elif vin>0: target=max(target,vin)
        else: target=0
        g=10 if vin>1 else 1e-12
        output=branch(out,return_pin,g,-g*target)
        # Zachowujemy moc wejściową w punkcie pracy. Pochodne są po
        # napięciu wyjścia, wejścia i prądzie obciążenia (Jacobian Newtona).
        current=max(0,-output.current(volts))
        if vin>1 and current>0:
            vo=v(out,return_pin)
            efficiency=p["sim_efficiency"]
            power=vo*current
            desired=power/(vin*efficiency)
            dout=(current-vo*g)/(vin*efficiency)
            din=-desired/vin
            branch(high,low,0,desired-dout*vo-din*vin,{out:dout,return_pin:-dout,high:din,low:-din})
        else: branch(high,low,1e-12)
        trial["output_current"]=current
    elif kind == "level_converter":
        low=d.nodes[1]
        contact(low,d.nodes[7],True)
        lv,hv=n["LV/3.3V"],n["HV/5V"]
        branch(lv,low,1e-12); branch(hv,low,1e-12)
        for i in (1,2):
            # Typowa gałąź RX modułu jest pasywnym dzielnikiem 10k/20k.
            resistor(n[f"RXI{i}"],n[f"RXO{i}"],10000)
            resistor(n[f"RXO{i}"],low,20000)
            txl,txh=n[f"TXI{i}"],n[f"TXO{i}"]
            resistor(lv,txl,10000); resistor(hv,txh,10000)
            # Kanał przewodzi, gdy co najmniej jedna strona wymusza LOW.
            contact(txl,txh,min(v(txl,low),v(txh,low))<v(lv,low)-1)
    elif kind == "keypad":
        key=p["sim_key"]
        for i in range(16): contact(n[f"R{i//4+1}"],n[f"C{i%4+1}"],key==str(i))
    elif kind == "relay_module":
        low=n["GND"]
        high=n.get("VCC",n.get("VCC/5V"))
        enabled=powered(high,low,1000)
        if "JD-VCC" in n:
            enabled=powered(n["JD-VCC"],low,1000) and enabled
        for suffix in (["1","2","3","4"] if "IN1" in n else [""]):
            signal=n["IN"+suffix]
            resistor(high,signal,10000)
            on=enabled and v(signal,low)<v(high,low)*.3
            contact(n["COM"+suffix],n["NC"+suffix],not on)
            contact(n["COM"+suffix],n["NO"+suffix],on)
            trial["on"+suffix]=on
    elif kind in {"digital_sensor","analog_sensor","ultrasonic"}:
        low=n["GND"]
        high=n.get("VCC",n.get("VDD",n.get("VCC/5V")))
        enabled=powered(high,low)
        if kind == "digital_sensor":
            active=p["sim_active"] == "true"
            state=not active if "Podczerwieni" in p["name"] else active
            drive(n["OUT"],low,high,state,enabled)
        elif kind == "analog_sensor":
            fraction=p["sim_signal"]
            output=n.get("AO",n.get("OUT"))
            branch(output,low,.04,0,{high:-.04*fraction,low:.04*fraction})
            if "DO" in n: drive(n["DO"],low,high,fraction<p["sim_trip"],enabled)
            # GAIN/AR są konfiguracyjne; zapisujemy jawnie słabe obciążenie.
            inputs([n[k] for k in ("GAIN","AR") if k in n],low)
        else:
            inputs([n["TRIG"]],low)
            triggered=v(n["TRIG"],low)>v(high,low)*.5
            start=d.state.get("echo_start",-1)
            end=d.state.get("echo_end",-1)
            if triggered and not d.state.get("triggered",False):
                start=time+.0002
                end=start+2*p["sim_distance"]/343
            drive(n["ECHO"],low,high,start<=time<end,enabled)
            trial.update(echo_start=start,echo_end=end,triggered=triggered)
    elif kind == "stepper_motor":
        for i,(a,b) in enumerate(((n["A+"],n["A−"]),(n["B+"],n["B−"]))):
            impedance=p["sim_resistance"]+p["sim_inductance"]/dt
            branch(a,b,1/impedance,p["sim_inductance"]/dt*d.state.get(f"phase{i}",0)/impedance)
    elif kind == "servo":
        low,high=n["GND"],n["VCC"]
        enabled=powered(high,low,100)
        inputs([n["PWM"]],low)
        signal=v(n["PWM"],low)>2
        if signal and not d.state.get("pwm",False): trial["rise"]=time
        if not signal and d.state.get("pwm",False) and "rise" in d.state:
            pulse=time-d.state["rise"]
            if .0005<=pulse<=.0025:
                position=max(0,min(1,(pulse-.001)/.001))
                trial["command"]=2*position-1 if "EF90D" in p["name"] else 180*position
        trial["pwm"]=signal
        trial["powered"]=enabled
    else:
        from app.simulation import peripherals
        if kind in peripherals.KINDS: return peripherals.linearize(d,volts,ground,time,dt)
        raise ValueError("Missing implementation for model: "+kind)
    return branches,trial


def finish(d, branches, trial, volts, result, dt, translate):
    """Wylicza pomiary z zaakceptowanej sieci, zatwierdza pamięć modelu."""
    p,kind,cid=d.parameters,d.kind,d.component.id
    currents=[b.current(volts) for b in branches]
    result.currents[cid]=currents[0] if currents else 0
    fault=""
    if kind in {"npn","pnp","nmos","pmos"} and abs(currents[0])>p["sim_max_current"]:
        fault=translate("Transistor current limit exceeded", "Przekroczony limit prądu tranzystora")
    if kind == "zener":
        voltage=volts[d.nodes[0]]-volts[d.nodes[1]]
        if voltage*currents[0]>p["sim_max_power"]: fault=translate("Zener power limit exceeded","Przekroczona moc diody Zenera")
    if kind == "rgb":
        levels=[max(0,min(1,i/p["sim_max_current"])) for i in currents]
        result.rgb[cid]=tuple(levels)
        result.brightness[cid]=max(levels)
        result.currents[cid]=sum(currents)
        if max(currents)>p["sim_max_current"]: fault=translate("RGB channel overcurrent","Przeciążenie kanału RGB")
    if kind in {"thyristor","triac"}: trial["main_current"]=currents[0]
    if kind == "crystal":
        result.currents[cid]=sum(currents)
        trial["crystal_i"]=currents[0]
        trial["crystal_v"]=d.state.get("crystal_v",0)+dt*currents[0]/p["sim_motional_capacitance"]
        trial["terminal_v"]=volts[d.nodes[0]]-volts[d.nodes[1]]
    if kind == "timer555":
        pins=p["pins"]
        trial["timer_inputs"]={name:volts[pins[name]]-volts[pins["GND"]] for name in ("CONT","TRIG","THRES","RESET")}
    if kind == "buzzer":
        time=result.time
        voltage=volts[d.nodes[0]]-volts[d.nodes[1]]
        activity=max(0,min(1,voltage/p["sim_rated_voltage"]))
        frequency=p.get("sim_tone_frequency",2000)
        if "Pasywny" in p["name"]:
            high=voltage>p["sim_rated_voltage"]*.5
            if high and not d.state.get("high",False):
                last=d.state.get("last_rise")
                if last is not None and time>last:
                    trial["frequency"]=1/(time-last)
                trial["last_rise"]=time
            trial["high"]=high
            frequency=trial.get("frequency",0)
            recent=frequency>0 and time-trial.get("last_rise",-1)<=max(.02,2.5/frequency)
            trial["amplitude"]=max(abs(voltage),d.state.get("amplitude",0) if recent else 0)
            activity=min(1,trial["amplitude"]/p["sim_rated_voltage"]) if recent and 20<=frequency<=10000 else 0
            if abs(voltage)>p["sim_rated_voltage"]*.1 and not recent:
                since=d.state.get("dc_since",time)
                trial["dc_since"]=since
                if time-since>=.03:
                    result.warnings[cid]=translate(
                        "Passive buzzer: DC alone does not produce a continuous tone. Use PWM or an alternating signal, or choose an active buzzer.",
                        "Buzzer pasywny: samo napięcie stałe nie daje ciągłego tonu. Użyj PWM lub sygnału zmiennego, albo wybierz buzzer aktywny.")
            else: trial.pop("dc_since",None)
        result.sounds[cid]={"level":activity,"frequency":frequency}
        result.readings[cid]=translate("Tone","Ton")+f": {frequency:.4g} Hz" if activity else translate("Silent","Cisza")
        trial["voltage"]=voltage
        if abs(voltage)>p["sim_rated_voltage"]*1.5: fault=translate("Buzzer overvoltage","Przepięcie buzzera")
    if kind == "stepper_motor":
        for i,current in enumerate(currents): trial[f"phase{i}"]=current
        result.readings[cid]=" / ".join(f"{i:.4g} A" for i in currents)
    if kind == "servo":
        unit="speed" if "EF90D" in p["name"] else "°"
        result.readings[cid]=f"{trial.get('command',0):.4g} {unit}" if trial["powered"] else translate("Unpowered","Brak zasilania")
    if kind in {"relay","relay_module"}:
        result.readings[cid]=" / ".join(f"{key}: {'ON' if value else 'OFF'}" for key,value in trial.items() if key.startswith("on"))
    if kind == "regulator" and abs(currents[0])>p["sim_max_current"]:
        fault=translate("Regulator output overcurrent","Przeciążenie wyjścia stabilizatora")
    if kind=="adc_spi" and "spi_code" in trial: result.readings[cid]=f"ADC: {trial['spi_code']} / 1023"
    if kind=="digital_pot": result.readings[cid]=f"W: {trial['wiper']} / 256"
    if kind == "converter" and trial.get("output_current",0)>p["sim_max_current"]:
        fault=translate("Converter output overcurrent","Przeciążenie wyjścia przetwornicy")
    if kind == "stepper_driver":
        if trial.get("unsupported_mode"):
            fault=translate("Only full-step mode is modelled; set MS inputs LOW", "Model obsługuje pełny krok; ustaw wejścia MS na LOW")
        elif any(abs(current)>p["sim_max_current"] for current,branch in zip(currents,branches) if branch.g==1):
            fault=translate("Driver phase current limit exceeded","Przekroczony limit prądu fazy sterownika")
    if kind == "flipflop" and any(trial.get(f"invalid{i}") for i in (1,2)):
        fault=translate("PRE and CLR are both active","PRE i CLR są jednocześnie aktywne")
    if fault: result.faults[cid]=f"{d.component.reference}: {fault}"
    from app.simulation import peripherals
    if kind in peripherals.KINDS: peripherals.finish(d,trial,result,translate)
    d.state=trial
