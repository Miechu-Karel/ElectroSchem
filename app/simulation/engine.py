"""Przejściowy solver MNA, bez Qt i bez wykonywania kodu użytkownika.

Kondensator: backward Euler, cewka: model Nortona. Diody: model odcinkowo
liniowy z iteracją punktu pracy. Wynik opisuje model, nie certyfikat układu.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from hashlib import sha256
from math import isfinite, sin, pi, sqrt, exp
from app.core.units import parse_value, split_unit
from app.core.led_colors import color_key
from app.libraries.simulation_catalog import behavior_for
from app.simulation.netlist import build_netlist
from app.libraries.emulator_catalog import profile_for, gpio_name
from app.simulation.extended import linearize, finish


class SimulationError(ValueError):
    pass


def si_value(text, unit, minimum=1e-15, maximum=1e15):
    number, normalized = parse_value(str(text), unit)
    power, base = split_unit(normalized)
    if base != unit or not number:
        raise ValueError("Expected " + unit)
    result = float(number)*10.0**power
    if not isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"Expected {minimum:g} … {maximum:g} SI")
    return result


@dataclass
class Device:
    component: object
    kind: str
    nodes: tuple
    parameters: dict
    previous: float = 0.0
    conducting: bool = False
    closed: bool = False
    state: dict = field(default_factory=dict)


@dataclass
class Result:
    time: float = 0
    voltages: dict = field(default_factory=dict)
    currents: dict = field(default_factory=dict)
    brightness: dict = field(default_factory=dict)
    faults: dict = field(default_factory=dict)
    rgb: dict = field(default_factory=dict)
    readings: dict = field(default_factory=dict)
    warnings: dict = field(default_factory=dict)
    displays: dict = field(default_factory=dict)
    sounds: dict = field(default_factory=dict)


def solve(matrix, rhs):
    """Gauss z pivotem. Bez ukrytych rezystorów maskujących pływające węzły."""
    size = len(rhs)
    a = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-18:
            raise SimulationError("Singular circuit / Obwód osobliwy: floating nodes or conflicting voltage sources")
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(col+1, size):
            factor = a[row][col]/a[col][col]
            if factor:
                for k in range(col+1, size+1): a[row][k] -= factor*a[col][k]
    x = [0.0]*size
    for row in range(size-1, -1, -1):
        x[row] = (a[row][size]-sum(a[row][c]*x[c] for c in range(row+1, size)))/a[row][row]
    if not all(isfinite(v) and abs(v) < 1e12 for v in x):
        raise SimulationError("Unstable solution / Niestabilne rozwiązanie")
    return x


class _Circuit:
    def __init__(self, sheet, custom=(), language="en"):
        self.sheet, self.language = sheet, language
        self.netlist = build_netlist(sheet, custom)
        self.devices, errors = [], []
        board_sources = []
        self.scripts = {}
        self.ground = None
        if not sheet.components: errors.append(self.t("The sheet is empty.", "Arkusz jest pusty."))
        for c in sheet.components:
            d = self.netlist.definitions[c.id]
            model = behavior_for(d)
            if model and model.kind == "mcu" and (c.properties.get("sim_mode")=="gpio" or (Path(c.properties.get("sim_source","")).suffix.lower()==".py" and not c.properties.get("sim_firmware"))):
                model = replace(model, kind="mcu_gpio")
            label = c.reference or c.library_id
            if model is None:
                errors.append(label+": "+self.t("no simulation model", "brak modelu symulacji"))
                continue
            nodes = tuple(self.netlist.pins[c.id, i] for i in range(len(d.pins)))
            if model.kind == "ground":
                self.ground = nodes[0]
                continue
            # Złącze nie jest zwarciem ani obciążeniem. Jego piny już należą
            # do sieci przewodów; nie dodajemy fikcyjnych równań do solvera.
            if model.kind == "connector": continue
            params = {"pins": {pin.name: nodes[i] for i,pin in enumerate(d.pins)}, "name": d.name, "symbol": d.symbol}
            try:
                if model.kind == "mcu_gpio":
                    from app.simulation.python_board import PythonBoard
                    from app.simulation.gpio_script import gpio_alias
                    source=Path(c.properties.get("sim_source", ""))
                    if not source.is_file():
                        raise ValueError(self.t("use Edit code in component properties first", "najpierw użyj Edytuj kod we właściwościach elementu"))
                    if source.stat().st_size > 100000: raise ValueError("GPIO source too large")
                    self.scripts[c.id]=PythonBoard(source.read_text(encoding="utf-8-sig"),d,source)
                    names=params["pins"]
                    if "GND" not in names: raise ValueError("Board has no GND pin")
                    params["ground"]=names["GND"]
                    self.ground=names["GND"]
                    params["gpio"]={alias:nodes[i] for i,pin in enumerate(d.pins) if (alias:=gpio_alias(pin.name))}
                    params["logic_voltage"]=5.0 if "Arduino" in d.name else 3.0 if "Microbit" in d.name else 3.3
                    params["power"]=next((names[n] for n in ("5V","VSYS","3V3","3V","VDD") if n in names),self.ground)
                    active={self.ground,*params["gpio"].values()}
                    # USB/board power is explicit in this educational mode.
                    # Each labelled supply pin is referenced to this board's
                    # ground; GPIO is never silently shorted to a supply.
                    for name,voltage in (("5V",5.),("VSYS",5.),("3V3",3.3),("3V",3.),("VDD",3.3),("AVDD",3.3)):
                        if name in names:
                            node=names[name]; active.add(node)
                            source_component=SimpleNamespace(id=c.id+":"+name,reference=c.reference+":"+name)
                            board_sources.append(Device(source_component,"rail_source",(node,self.ground),{"value":voltage}))
                    wired=set(self.netlist.wires.values())
                    for i,pin in enumerate(d.pins):
                        if nodes[i] not in active and nodes[i] in wired:
                            raise ValueError(self.t("pin not modelled: ","pin bez modelu: ")+pin.name)
                    nodes=tuple(sorted(active))
                if model.kind == "mcu":
                    profile = profile_for(d)
                    if not str(c.properties.get("sim_firmware", "")).strip():
                        raise ValueError(self.t("assign firmware in the Emulators tab", "przypisz firmware w zakładce Emulatorów"))
                    params["profile"] = profile
                    params["gpio"] = {gpio_name(p.name, profile.engine): nodes[i] for i,p in enumerate(d.pins) if gpio_name(p.name, profile.engine)}
                    names = {p.name: nodes[i] for i,p in enumerate(d.pins)}
                    params["power"] = names["5V" if profile.engine == "avr8js" else "VSYS"]
                    params["ground"] = names["GND"]
                    self.ground = names["GND"]
                    allowed = set(params["gpio"].values()) | {params["power"],params["ground"]}
                    if c.properties.get("sim_usb_power")=="true":
                        for name,voltage in (("5V",5.),("3V3",3.3)):
                            if name in names:
                                node=names[name]; allowed.add(node)
                                source_component=SimpleNamespace(id=c.id+":"+name,reference=c.reference+":"+name)
                                board_sources.append(Device(source_component,"rail_source",(node,self.ground),{"value":voltage}))
                    wired = set(self.netlist.wires.values())
                    for i,pin in enumerate(d.pins):
                        if nodes[i] not in allowed and nodes[i] in wired:
                            raise ValueError(self.t("pin not modelled: ", "pin bez modelu: ")+pin.name)
                    nodes = tuple(sorted(allowed))
                if model.primary_unit:
                    from app.core.component_defaults import nominal_value
                    number, unit = parse_value(c.value or nominal_value(d)[0], c.unit or model.primary_unit)
                    params["value"] = si_value(number + " " + unit, model.primary_unit)
                for p in model.parameters:
                    raw = str(c.properties.get(p.key, p.default))
                    if p.key == "sim_initial_voltage" and model.kind == "polar_capacitor" and raw.strip().lower() == "auto":
                        # Repeatable startup aid breaks ideal oscillator
                        # symmetry without waiting seconds for numerical noise.
                        # This is an explicit auto precharge, not component
                        # physics. Store only in solver state;
                        # explicit zero is respected, and ELS stays unchanged.
                        fraction = int.from_bytes(sha256(c.id.encode()).digest()[:4], "big") / 0xffffffff
                        params[p.key] = (2*fraction-1)*.1
                        continue
                    if p.choices:
                        if raw not in {v[0] for v in p.choices}: raise ValueError(self.t(p.en,p.pl))
                        params[p.key] = raw
                    else:
                        try: params[p.key] = si_value(raw, p.unit, p.minimum, p.maximum)
                        except ValueError as exc:
                            raise ValueError(self.t(p.en,p.pl)+": "+str(exc)) from exc
                if model.kind in {"capacitor", "polar_capacitor"}:
                    params["voltage"] = si_value(c.properties.get("voltage", ""), "V")
                if model.kind == "led" and not color_key(c.properties.get("color", "")):
                    raise ValueError(self.t("choose LED colour", "wybierz kolor LED"))
                if model.kind == "rail_source":
                    params["value"] = params.get("sim_voltage", 3.3 if "+3.3V" in d.name else 12.0 if "+12V" in d.name else 5.0)
                if model.kind == "logic_input":
                    params["logic_input"] = True
                    params["value"] = 5.0 if params["sim_closed"] == "true" else 0.0
                    model = replace(model, kind="rail_source")
            except (ValueError, OverflowError, OSError, SyntaxError) as exc:
                errors.append(label+": "+self.t("missing/invalid parameters", "brak lub błędne parametry")+f" ({exc})")
                continue
            initial = params.get("sim_initial_voltage", 0.0)
            self.devices.append(Device(c, model.kind, nodes, params, previous=initial, closed=params.get("sim_closed") == "true"))
        self.devices.extend(board_sources)
        self.sources = [d for d in self.devices if d.kind in {"dc", "ac", "rail_source"}]
        logical = any(d.kind in {"logic_gate", "logic_output"} or d.parameters.get("logic_input") for d in self.devices)
        if self.ground is None and logical: self.ground = -1
        for device in self.devices:
            if device.kind == "logic_output": device.nodes = (device.nodes[0],self.ground)
        if not self.sources and not logical:
            errors.append(self.t("Add a supply rail, battery or AC source.", "Dodaj szynę zasilania, baterię lub źródło AC."))
        if self.ground is None:
            physical_sources=[d for d in self.sources if len(d.nodes)==2]
            if physical_sources: self.ground=physical_sources[0].nodes[1]
            elif self.sources:
                errors.append(self.t("Supply rails require a GND symbol connected to the return path.", "Szyny zasilania wymagają symbolu GND połączonego z torem powrotnym."))
        # Wiele symboli +5V to jedna idealna szyna, a nie równoległe źródła,
        # których nieokreślony podział prądu tworzyłby osobliwą macierz MNA.
        rails={}
        aliases=[]
        for device in self.sources:
            if device.kind != "rail_source": continue
            device.nodes=(device.nodes[0],self.ground)
            node=device.nodes[0]
            if node in rails:
                if abs(rails[node].parameters["value"]-device.parameters["value"])>1e-9:
                    errors.append(self.t("Conflicting supply rail voltages.", "Sprzeczne napięcia połączonych szyn zasilania."))
                aliases.append(device)
            else: rails[node]=device
        self.devices=[d for d in self.devices if d not in aliases]
        self.sources=[d for d in self.sources if d not in aliases]
        # Unconnected board pins do not need electrical unknowns. Keep every
        # wired pin and every pin used by another device, including supply rails.
        board_kinds={"mcu","mcu_gpio"}
        connected={n for d in self.devices if d.kind not in board_kinds for n in d.nodes}
        connected.update(self.netlist.wires.values())
        used=set()
        for d in self.devices:
            if d.kind in board_kinds:
                used.update(n for n in d.nodes if n in connected)
                used.update((d.parameters["ground"],d.parameters["power"]))
            else: used.update(d.nodes)
        reached = {self.ground}
        while True:
            previous = len(reached)
            for d in self.devices:
                if set(d.nodes) & reached: reached.update(d.nodes)
            if len(reached) == previous: break
        if used - reached:
            errors.append(self.t("Disconnected circuit islands. Connect a common ground.",
                                 "Niepołączone wyspy obwodu. Połącz wspólną masę."))
        self.index = {n: i for i, n in enumerate(sorted(used - {self.ground, None}))}
        if len(self.index)+len(self.sources) > 80:
            errors.append(self.t("Alpha limit: 80 unknowns per sheet.", "Limit alfy: 80 niewiadomych na arkusz."))
        if errors: raise SimulationError("\n".join(errors))
        self.time, self.result = 0.0, Result()
        self._solved_system=None
        self.gpio_states = {}
        self.i2c_pending=[]
        for cid,script in self.scripts.items():
            script.bus_write=lambda bus,address,value,key=cid:self.write_i2c(key,bus,address,value)

    def i2c_targets(self,cid,bus=1):
        device=next(d for d in self.devices if d.component.id==cid)
        p=device.parameters; gpio=p.get("gpio",{})
        pairs=(("GPIO2","GPIO3"),("A4","A5"),("GP4","GP5"),("GPIO21","GPIO22")) if bus==1 else (("GPIO0","GPIO1"),("A4","A5"))
        pair=next(((gpio[a],gpio[b]) for a,b in pairs if a in gpio and b in gpio),None)
        if pair is None: return []
        return [d for d in self.devices if d.kind=="lcd_i2c" and
                (d.parameters["pins"]["SDA"],d.parameters["pins"]["SCL"])==pair and
                d.parameters["pins"]["GND"]==p["ground"]]

    def write_i2c(self,cid,bus,address,value):
        targets=[d for d in self.i2c_targets(cid,bus) if int(d.parameters["sim_address"])==address]
        if len(targets)!=1:
            raise ValueError(self.t("I2C device not found or address conflict; check SDA, SCL, GND and address.","Nie znaleziono urządzenia I2C lub konflikt adresów; sprawdź SDA, SCL, GND i adres.")+f" (0x{address:02X})")
        if len(self.i2c_pending)>=4096: raise ValueError("I2C transaction limit exceeded")
        self.i2c_pending.append((targets[0],value))

    def commit_i2c(self,result):
        from app.simulation.peripherals import lcd_byte,finish as peripheral_finish
        pending=self.i2c_pending; self.i2c_pending=[]
        for device,value in pending:
            if not device.state.get("powered"):
                raise SimulationError(self.t("I2C device has no power.","Urządzenie I2C nie ma zasilania."))
            device.state["lcd"]=lcd_byte(device.state.get("lcd",{}),value,device.parameters.get("sim_text_encoding","utf-8"))
        for device in {id(d):d for d,_ in pending}.values():
            peripheral_finish(device,device.state,result,self.t)

    def digital_inputs(self, device):
        p = device.parameters
        ground = self.result.voltages.get(p["ground"], 0)
        return {name: self.result.voltages.get(node, ground)-ground > p["profile"].voltage*.6
                for name,node in p["gpio"].items()}

    def t(self, en, pl): return pl if self.language == "pl" else en

    def validate_time_step(self, dt):
        if not isfinite(dt) or not 1e-10 <= dt <= .01:
            raise SimulationError("Time step must be 0.1 ns … 10 ms")
        for d in self.sources:
            if d.kind == "ac" and dt*d.parameters["sim_frequency"] > .02:
                raise SimulationError(self.t("AC needs 50+ time steps per period; lower the time step.",
                                             "AC wymaga min. 50 kroków na okres; zmniejsz krok czasowy."))
        for d in self.devices:
            if d.kind == "crystal" and dt*d.parameters["value"] > .02:
                raise SimulationError(self.t("Crystal model needs at least 50 steps per period.", "Model kwarcu wymaga co najmniej 50 kroków na okres."))

    def step(self, dt=0.0001):
        self.validate_time_step(dt)
        if self.result.faults: raise SimulationError(self.t("Reset after a fault.", "Zresetuj po awarii."))
        count = len(self.index)
        size = count+len(self.sources)
        new_time = self.time+dt
        for d in self.devices:
            if d.kind == "mcu_gpio":
                try:
                    p=d.parameters
                    low=self.result.voltages.get(p["ground"],0)
                    inputs={name:self.result.voltages.get(node,low)-low > p["logic_voltage"]*.6 for name,node in p["gpio"].items()}
                    self.gpio_states[d.component.id]=self.scripts[d.component.id].advance(dt,inputs)
                except (ValueError, TypeError, IndexError,KeyError,AttributeError,RecursionError) as exc:
                    raise SimulationError(d.component.reference+": "+str(exc)) from exc
        basic = {"dc", "ac", "rail_source", "mcu", "mcu_gpio", "resistor", "lamp", "switch", "capacitor", "polar_capacitor", "inductor", "led", "diode", "logic_output"}
        def assemble(guess, continuation=0.0):
            volts_guess={self.ground:0, **{n:guess[i] for n,i in self.index.items()}}
            matrix, rhs = [[0.0]*size for _ in range(size)], [0.0]*size
            def inject(a, b, g, offset=0):
                # I(a→b) = g*(Va-Vb)+offset. Źródło prądowe trafia do RHS.
                for node, other, sign in ((a,b,1), (b,a,-1)):
                    if node in self.index:
                        i = self.index[node]
                        matrix[i][i] += g
                        if other in self.index: matrix[i][self.index[other]] -= g
                        rhs[i] -= sign*offset
            stamps, extended_stamps = {}, {}
            for d in self.devices:
                p = d.parameters
                if d.kind in {"dc", "ac", "rail_source"}: continue
                if d.kind not in basic:
                    branches,trial=linearize(d,volts_guess,self.ground,new_time,dt)
                    extended_stamps[d.component.id]=(branches,trial)
                    for branch in branches:
                        inject(branch.a,branch.b,branch.g,branch.offset)
                        # Źródło zależne: jego prąd musi być odejmowany od
                        # jednego węzła i dodawany do drugiego, wraz z Jacobianem.
                        for node,sign in ((branch.a,1),(branch.b,-1)):
                            if node not in self.index: continue
                            for control,gain in branch.controls.items():
                                if control in self.index: matrix[self.index[node]][self.index[control]]+=sign*gain
                    continue
                if d.kind in {"mcu", "mcu_gpio"}:
                    # Jawny model obciążenia zasilania: 1 kΩ. Wyjście GPIO
                    # to źródło Thévenina 25 Ω; wejście ma 1 TΩ do GND.
                    inject(p["power"],p["ground"],.001)
                    states = self.gpio_states.get(d.component.id,{})
                    for name,node in p["gpio"].items():
                        if node not in self.index: continue
                        state = states.get(name,2)
                        g = 1/25 if state in {0,1} else 1/50000 if state == 3 else 1e-12
                        level = (p["logic_voltage"] if d.kind=="mcu_gpio" else p["profile"].voltage) if state in {1,3} else 0
                        inject(node,p["ground"],g,-g*level)
                    continue
                g, offset = 0.0, 0.0
                if d.kind == "resistor": g = 1/p["value"]
                elif d.kind == "logic_output": g = 1e-9
                elif d.kind == "lamp": g = p["value"]/p["sim_rated_voltage"]**2
                elif d.kind == "switch": g = 1000.0 if d.closed else 1e-12
                elif d.kind in {"capacitor", "polar_capacitor"}:
                    g = p["value"]/dt
                    offset = -g*d.previous
                elif d.kind == "inductor": g, offset = dt/p["value"], d.previous
                elif d.kind in {"led", "diode"}:
                    conducting=volts_guess[d.nodes[0]]-volts_guess[d.nodes[1]]>p["sim_forward_voltage"]
                    g = .1 if conducting else 1e-12
                    offset = -g*p["sim_forward_voltage"] if conducting else 0
                stamps[d.component.id] = g, offset
                inject(*d.nodes, g, offset)
            for j, d in enumerate(self.sources):
                row = count+j
                for node, sign in zip(d.nodes, (1, -1)):
                    if node in self.index:
                        i = self.index[node]
                        matrix[row][i] += sign
                        matrix[i][row] += sign
                value = d.parameters["value"]
                rhs[row] = value if d.kind in {"dc", "rail_source"} else sqrt(2)*value*sin(2*pi*d.parameters["sim_frequency"]*new_time)
            # Gmin jest WYŁĄCZNIE metodą szukania punktu pracy. Każdy
            # zaakceptowany wynik musi ponownie spełnić oryginalne równania
            # z continuation=0, bez sztucznego obciążania obwodu.
            for i in range(count): matrix[i][i]+=continuation
            return matrix,rhs,stamps,extended_stamps

        # Newton z wyszukiwaniem kroku. Oceniamy faktyczny błąd Kirchhoffa
        # przy NOWYCH napięciach. Sam brak zmiany flagi diody nie wystarcza
        # dla tranzystorów, wzmacniaczy i kilku zależnych bramek.
        def residual(candidate, matrix, rhs):
            return max((abs(sum(a*x for a,x in zip(row,candidate))-b) for row,b in zip(matrix,rhs)),default=0)
        guess=[self.result.voltages.get(n,0) for n in self.index]+[0.0]*len(self.sources)
        # Zgadnięcie punktu pracy musi już spełniać znane idealne zasilania.
        # Inaczej tłumienie Newtona utkwi na progu włączania zasilanego IC.
        known={self.ground:0.0}
        for _ in self.sources:
            for d in self.sources:
                a,b=d.nodes
                value=d.parameters["value"]
                if d.kind=="ac": value*=sqrt(2)*sin(2*pi*d.parameters["sim_frequency"]*new_time)
                if b in known: known[a]=known[b]+value
                elif a in known: known[b]=known[a]-value
        for node,value in known.items():
            if node in self.index: guess[self.index[node]]=value
        def newton(initial, continuation=0.0):
            guess=initial
            for iteration in range(100):
                matrix,rhs,_,_=assemble(guess,continuation)
                cached=self._solved_system
                if cached is not None and matrix==cached[0] and rhs==cached[1]:
                    solution=cached[2]
                else:
                    solution=solve(matrix,rhs)
                    self._solved_system=(matrix,rhs,solution)
                next_matrix,next_rhs,next_stamps,next_extended=assemble(solution,continuation)
                error=residual(solution,next_matrix,next_rhs)
                if error < 1e-9:
                    return solution,next_stamps,next_extended
                old_error=residual(guess,matrix,rhs)
                if error >= old_error:
                    best,error_best=solution,error
                    for power in range(1,31):
                        factor=2.0**(-power)
                        candidate=[a+factor*(b-a) for a,b in zip(guess,solution)]
                        a,b,_,_=assemble(candidate,continuation)
                        candidate_error=residual(candidate,a,b)
                        if candidate_error < error_best: best,error_best=candidate,candidate_error
                        if candidate_error < old_error: break
                    guess=best
                else: guess=solution
            return None

        converged=newton(guess)
        if converged is None:
            # Przełączenie dodatniego sprzężenia zwrotnego może wymagać
            # przejścia do innego obszaru pracy tranzystorów. Samo skracanie
            # kroku Newtona potrafi utknąć na granicy odcięcia. Kontynuacja
            # prowadzi rozwiązanie od obwodu silnie tłumionego do właściwego.
            seed=guess
            for conductance in (1.0,.1,.01,.001,.0001,.00001,.000001,.0000001,0.0):
                stage=newton(seed,conductance)
                if stage is None: break
                seed=stage[0]
                if conductance==0: converged=stage
        if converged is None:
            raise SimulationError(self.t("Nonlinear circuit did not converge. Check feedback and the time step.", "Obwód nieliniowy nie osiągnął zbieżności. Sprawdź sprzężenia i krok czasowy."))
        solution,stamps,extended_stamps=converged
        volts={self.ground:0.0, **{n:solution[i] for n,i in self.index.items()}}
        for d in self.devices:
            if d.kind not in {"mcu","mcu_gpio"}: continue
            p=d.parameters
            high=p["logic_voltage"] if d.kind=="mcu_gpio" else p["profile"].voltage
            low=volts[p["ground"]]
            for name,node in p["gpio"].items():
                # Floating outputs have their unloaded logic voltage, no load
                # current; floating inputs retain the model's ground default.
                volts.setdefault(node,low+(high if self.gpio_states.get(d.component.id,{}).get(name,2) in {1,3} else 0))
        result = Result(new_time, volts)
        for d in self.devices:
            cid, p = d.component.id, d.parameters
            if cid in extended_stamps:
                branches,trial=extended_stamps[cid]
                finish(d,branches,trial,volts,result,dt,self.t)
                continue
            if d.kind in {"mcu", "mcu_gpio"}:
                supply = volts[p["power"]]-volts[p["ground"]]
                result.currents[cid] = supply*.001
                low,high = (4.5,5.5) if d.kind=="mcu" and p["profile"].engine == "avr8js" else (1.8,5.5)
                if not low <= supply <= high:
                    result.faults[cid] = f"{d.component.reference}: "+self.t("invalid board supply", "błędne zasilanie płytki")+f" ({supply:.4g} V; {low}–{high} V)"
                for name,node in p["gpio"].items():
                    if node not in self.index and node != p["ground"]: continue
                    state = self.gpio_states.get(cid,{}).get(name,2)
                    voltage = volts[node]-volts[p["ground"]]
                    maximum = p["logic_voltage"] if d.kind=="mcu_gpio" else p["profile"].voltage
                    if voltage < -.3 or voltage > maximum+.3:
                        result.faults[cid] = f"{d.component.reference} / {name}: "+self.t("GPIO voltage outside model limits","Napięcie GPIO poza granicami modelu")+f" ({voltage:.4g} V)"
                    if state in {0,1} and abs((voltage-(maximum if state == 1 else 0))/25) > .04:
                        result.faults[cid] = f"{d.component.reference} / {name}: "+self.t("GPIO overload (>40 mA model limit)","Przeciążenie GPIO (limit modelu 40 mA)")
                continue
            v = volts[d.nodes[0]]-volts[d.nodes[1]]
            if d in self.sources: current = solution[count+self.sources.index(d)]
            else:
                g, offset = stamps[cid]
                current = g*v+offset
            result.currents[cid] = current
            if d.kind == "logic_output":
                result.brightness[cid] = 1.0 if v >= 2.5 else 0.0
                result.readings[cid] = "HIGH (1)" if v >= 2.5 else "LOW (0)"
            fault = ""
            if d.kind=="dc" and "sim_max_current" in p and abs(current)>p["sim_max_current"]:
                fault=self.t("Power supply overcurrent","Przeciążenie zasilacza")
            if d.kind == "resistor" and v*current > p["sim_max_power"]*(1+1e-6):
                fault = self.t("Resistor power rating exceeded", "Przekroczona moc rezystora")
            if d.kind in {"capacitor", "polar_capacitor"}:
                d.previous = v
                if abs(v) > p["voltage"]*(1+1e-6):
                    fault = self.t("Capacitor overvoltage — damage risk", "Przepięcie kondensatora — ryzyko uszkodzenia")
                if d.kind == "polar_capacitor" and v < -.5:
                    # Nie mamy modelu chemicznego ani czasu do uszkodzenia.
                    # Napięcie wsteczne jest ostrzeżeniem o ryzyku, nie
                    # dowodem natychmiastowej awarii. Przepięcie nadal blokuje.
                    result.warnings[cid] = f"{d.component.reference}: "+self.t("Reverse voltage on a polarized capacitor; check the component rating", "Napięcie wsteczne na kondensatorze polaryzowanym; sprawdź parametry elementu")+f" ({v:.4g} V)"
            if d.kind == "inductor": d.previous = current
            if d.kind in {"led", "diode"}:
                if current > p["sim_max_current"]*(1+1e-6): fault = self.t("Diode overcurrent", "Przeciążenie prądowe diody")
                if d.kind == "led":
                    result.brightness[cid] = max(0, min(1, current/p["sim_max_current"]))
                    if -v > p["sim_reverse_voltage"]: fault = self.t("LED reverse-voltage limit exceeded", "Przekroczone napięcie wsteczne LED")
            if d.kind == "lamp":
                # Dla AC nie porównujemy szczytu sinusoidy z wartością RMS.
                # Średnia wykładnicza mocy (50 ms) służy wskaźnikowi blasku
                # i umownemu progowi awarii; nie zmienia rezystancji włókna.
                d.previous += (v*current-d.previous)*(1-exp(-dt/.05))
                result.brightness[cid] = min(1, d.previous/p["value"])
                if d.previous > p["value"]*1.44 or abs(v) > p["sim_rated_voltage"]*2:
                    fault = self.t("Lamp overload (simplified threshold)", "Przeciążenie żarówki (próg uproszczony)")
            if fault: result.faults[cid] = f"{d.component.reference}: {fault} ({v:.4g} V, {current:.4g} A)"
        self.commit_i2c(result)
        self.time, self.result = new_time, result
        return result


def loose_component_ids(sheet,custom=(),netlist=None):
    """Unwired actors, excluding references; preserve stand-alone documents."""
    netlist=netlist if netlist is not None else build_netlist(sheet,custom)
    components={c.id:c for c in sheet.components}
    members={}
    for (cid,_),net in netlist.pins.items(): members.setdefault(net,set()).add(cid)
    wired=set(netlist.wires.values())
    touched={cid for w in sheet.wires for cid in (w.start_component_id,w.end_component_id) if cid in components}
    for (cid,_),net in netlist.pins.items():
        if net in wired or len(members[net])>1: touched.add(cid)
    ignored=set()
    if touched:
        for cid in components:
            definition=netlist.definitions[cid]
            if cid not in touched and (definition is None or definition.symbol not in {"power","ground"}):
                ignored.add(cid)
    return ignored


class Circuit:
    """Independent electrical islands share a clock, not a reference node.

    Explicit GND/rail symbols still describe common nets. Disconnected battery
    or USB-powered circuits can have their own reference and fault state.
    """
    def __init__(self, sheet, custom=(), language="en"):
        self.sheet, self.language = sheet, language
        self.netlist = build_netlist(sheet, custom)
        components={c.id:c for c in sheet.components}
        # Ignore completely loose components only when an actual connected
        # circuit exists. Preserve deliberate stand-alone board simulations,
        # named supply/reference symbols, and validation of all wired devices.
        self.ignored_components=loose_component_ids(sheet,custom,self.netlist)
        self.ignored_warnings={cid:("Luźny element pominięty w symulacji." if language=="pl" else "Loose component excluded from simulation.") for cid in self.ignored_components}
        self.result=Result(warnings=dict(self.ignored_warnings))
        components={cid:c for cid,c in components.items() if cid not in self.ignored_components}
        parents={cid:cid for cid in components}
        def root(cid):
            while parents[cid]!=cid:
                parents[cid]=parents[parents[cid]]; cid=parents[cid]
            return cid
        owners={}
        for (cid,_),net in self.netlist.pins.items():
            if cid not in components: continue
            if net in owners: parents[root(cid)]=root(owners[net])
            owners[net]=cid
        implicit=[]
        for c in sheet.components:
            if c.id not in components: continue
            definition=self.netlist.definitions[c.id]
            if behavior_for(definition) is None:
                raise SimulationError(c.reference+": "+("brak modelu symulacji" if language=="pl" else "no simulation model"))
            # Named rails and ideal gate symbols already refer to the common
            # GND by definition even without a wire drawn to that reference.
            if definition.symbol in {"power","ground","logic_input","logic_output"} or definition.symbol.startswith("gate_"):
                implicit.append(c.id)
        for cid in implicit[1:]: parents[root(cid)]=root(implicit[0])
        groups={}
        for cid in components: groups.setdefault(root(cid),set()).add(cid)
        if not groups: raise SimulationError("Arkusz jest pusty" if language=="pl" else "The sheet is empty")
        self.parts=[]; self.maps=[]; self.disabled=set()
        self.gpio_states={}; self.time=0.; self.result=Result(warnings=dict(self.ignored_warnings))
        for ids in groups.values():
            nets={net for (cid,_),net in self.netlist.pins.items() if cid in ids}
            subset=replace(sheet,components=[c for c in sheet.components if c.id in ids],
                           wires=[w for w in sheet.wires if self.netlist.wires[w.id] in nets])
            try: part=_Circuit(subset,custom,language)
            except SimulationError as exc:
                from app.core.messages import localize
                raise SimulationError(("Obwód: " if language=="pl" else "Circuit: ")+localize(str(exc),language)) from exc
            mapping={local:self.netlist.pins[key] for key,local in part.netlist.pins.items()}
            mapping.update({local:self.netlist.wires[key] for key,local in part.netlist.wires.items()})
            part.gpio_states=self.gpio_states
            self.parts.append(part); self.maps.append(mapping)
        self.devices=[d for part in self.parts for d in part.devices]
        self.sources=[d for part in self.parts for d in part.sources]

    def __getattr__(self, name):
        # Keep the single-circuit inspection interface used by the editor.
        if name.startswith("__"): raise AttributeError(name)
        return getattr(self.parts[0],name)

    @property
    def can_resume(self):
        return any(i not in self.disabled and not p.result.faults for i,p in enumerate(self.parts))

    def acknowledge_faults(self):
        for i,part in enumerate(self.parts):
            if part.result.faults: self.disabled.add(i)
        self.result.faults={}

    def digital_inputs(self, device):
        return next(part.digital_inputs(device) for part in self.parts if device in part.devices)

    def i2c_addresses(self,device):
        part=next(part for part in self.parts if device in part.devices)
        return [int(d.parameters["sim_address"]) for d in part.i2c_targets(device.component.id,1)]

    def receive_i2c(self,device,events):
        part=next(part for part in self.parts if device in part.devices)
        for address,value in events: part.write_i2c(device.component.id,1,int(address),int(value))

    def active_devices(self):
        return [d for i,part in enumerate(self.parts) if i not in self.disabled for d in part.devices]

    def maximum_time_step(self):
        """Sampling-safe limit with headroom for the UI's decimal rounding."""
        limit=.01
        for device in self.active_devices():
            if device.kind=="ac": limit=min(limit,.019/device.parameters["sim_frequency"])
            elif device.kind=="crystal": limit=min(limit,.019/device.parameters["value"])
        return limit

    def step(self, dt=.0001):
        if self.result.faults: raise SimulationError("Zresetuj lub wznów sprawne obwody" if self.language=="pl" else "Reset or resume healthy circuits")
        # Sampling configuration errors must never become component explosions,
        # and no island may advance before all active islands pass this check.
        for i,part in enumerate(self.parts):
            if i not in self.disabled: part.validate_time_step(dt)
        merged=Result(self.time+dt,warnings=dict(self.ignored_warnings))
        for i,(part,mapping) in enumerate(zip(self.parts,self.maps)):
            if i in self.disabled:
                result=part.result
            else:
                try: result=part.step(dt)
                except SimulationError as exc:
                    if len(self.parts)==1: raise
                    # A numerical failure is local to this island too. Pause
                    # and report it, then permit other islands to resume.
                    cid=part.sheet.components[0].id
                    part.result.faults[cid]=str(exc)
                    result=part.result
            merged.voltages.update({mapping.get(n,n):v for n,v in result.voltages.items()})
            for attr in ("currents","brightness","rgb","readings","warnings","displays","sounds"):
                getattr(merged,attr).update(getattr(result,attr))
            if i not in self.disabled: merged.faults.update(result.faults)
        self.time=merged.time; self.result=merged
        return merged
