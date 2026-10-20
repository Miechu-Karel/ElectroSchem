"""Read-only passive DC resistance measurement with sources disconnected.

No injection into a running circuit. Diodes use a 1 mA / 3 V virtual meter;
their apparent resistance depends on polarity. Active devices are rejected.
Floating remote islands are ignored.
"""
from math import inf
from app.libraries.built_in import get_definition
from app.libraries.simulation_catalog import behavior_for
from app.simulation.engine import si_value, solve

def resistance(sheet, custom, netlist, a, b, devices=()):
    if a == b: return 0.
    states={d.component.id:d for d in devices}; edges=[]; diodes=[]; unsupported=[]
    for c in sheet.components:
        definition=netlist.definitions[c.id]; model=behavior_for(definition)
        if not model: continue
        nodes=[netlist.pins[c.id,i] for i in range(len(definition.pins))]
        pins={p.name:nodes[i] for i,p in enumerate(definition.pins)}
        state=states.get(c.id); params=state.parameters if state else c.properties
        def add(x,y,r): edges.append((x,y,max(.001,r)))
        if model.kind == "resistor": add(*nodes[:2],si_value(c.value+" "+c.unit,"Ω"))
        elif model.kind == "variable_resistor":
            low=float(params.get("sim_min_resistance",0)); high=float(params.get("sim_max_resistance",10000))
            if high < low: low,high=high,low
            add(*nodes[:2],low+(high-low)*float(params.get("sim_position",.5)))
        elif model.kind == "lamp":
            power=si_value(c.value+" "+c.unit,"W")
            voltage=params.get("sim_rated_voltage", "")
            voltage=float(voltage) if isinstance(voltage,(int,float)) else si_value(voltage,"V")
            if power<=0 or voltage<=0: raise ValueError("missing_lamp_rating")
            add(*nodes[:2],voltage**2/power)
        elif model.kind in {"dc_motor","buzzer"}:
            raw=params.get("sim_resistance", "20 Ω" if model.kind=="dc_motor" else "1 kΩ")
            add(*nodes[:2],float(raw) if isinstance(raw,(int,float)) else si_value(raw,"Ω"))
        elif model.kind == "potentiometer":
            r=si_value(c.value+" "+c.unit,"Ω"); pos=float(params.get("sim_position",.5))
            add(pins["1"],pins["W"],r*pos); add(pins["W"],pins["3"],r*(1-pos))
        elif model.kind == "ammeter": add(*nodes[:2],.001)
        elif model.kind in {"led","diode"}:
            raw=params.get("sim_forward_voltage","2 V" if model.kind=="led" else "0.7 V")
            forward=float(raw) if isinstance(raw,(int,float)) else si_value(raw,"V")
            diodes.append((*nodes[:2],forward))
        elif model.kind == "switch":
            if state.closed if state else c.properties.get("sim_closed")=="true": add(*nodes[:2],.001)
        elif model.kind == "tactile":
            add(nodes[0],nodes[2],.001); add(nodes[1],nodes[3],.001)
            if state.closed if state else c.properties.get('sim_closed')=='true': add(nodes[0],nodes[1],.001)
        elif model.kind == "spdt": add(pins["COM"],pins["B" if state and state.closed else "A"],.001)
        elif model.kind == "multi_switch":
            pos=int(params.get("sim_position",1))
            if pos==0 and params.get('sim_allow_off','true')=='false': pos=1
            if pos: add(pins["COM"],pins[str(pos)],.001)
        elif model.kind == "inductor": add(*nodes[:2],.001)
        elif model.kind not in {"dc","ac","rail_source","solar","lab_source","ground","connector","meter","capacitor","polar_capacitor"}:
            unsupported.append(set(nodes))
    adjacent={}
    for x,y,r in edges+diodes:
        adjacent.setdefault(x,set()).add(y); adjacent.setdefault(y,set()).add(x)
    reachable={a}; pending=[a]
    while pending:
        for n in adjacent.get(pending.pop(),()):
            if n not in reachable: reachable.add(n); pending.append(n)
    if any(nodes & reachable for nodes in unsupported):
        raise ValueError("active_or_nonlinear")
    if b not in reachable: return inf
    diodes=[edge for edge in diodes if edge[0] in reachable]
    unknown=sorted(reachable-{b}); indices={n:i for i,n in enumerate(unknown)}
    current=.001 if diodes else 1.; guess={n:0. for n in reachable}
    for _ in range(40):
        matrix=[[0.]*len(unknown) for _ in unknown]; rhs=[0.]*len(unknown); rhs[indices[a]]=current
        conducting=[guess.get(x,0)-guess.get(y,0)>v for x,y,v in diodes]
        stamps=[(x,y,1/r,0.) for x,y,r in edges]+[(x,y,.1 if on else 1e-12,v if on else 0.) for (x,y,v),on in zip(diodes,conducting)]
        for x,y,g,forward in stamps:
            if x not in reachable or x==y: continue
            for n,other,sign in ((x,y,1),(y,x,-1)):
                if n in indices:
                    matrix[indices[n]][indices[n]]+=g; rhs[indices[n]]+=sign*g*forward
                    if other in indices: matrix[indices[n]][indices[other]]-=g
        solution=solve(matrix,rhs); guess.update({n:solution[i] for n,i in indices.items()})
        if conducting==[guess.get(x,0)-guess.get(y,0)>v for x,y,v in diodes]: break
    else: raise ValueError("measurement_did_not_converge")
    voltage=max(0.,solution[indices[a]])
    return inf if diodes and voltage>3.000001 else voltage/current


def live_network(sheet,netlist,a,b,devices,result):
    """Trace conducting paths, never jump across an open switch or meter."""
    states={d.component.id:d for d in devices}; edges=[]; sources=[]
    for c in sheet.components:
        definition=netlist.definitions[c.id]; model=behavior_for(definition)
        if not model: continue
        nodes=[netlist.pins[c.id,i] for i in range(len(definition.pins))]
        pins={p.name:nodes[i] for i,p in enumerate(definition.pins)}
        state=states.get(c.id); p=state.parameters if state else c.properties
        closed=state.closed if state else c.properties.get('sim_closed')=='true'
        if model.kind in {'dc','ac','rail_source','solar','lab_source'}:
            if state and abs(p.get('value',p.get('sim_voltage',0)))>1e-9: sources.append(set(nodes))
            continue
        if model.kind in {'ground','connector','meter','capacitor','polar_capacitor'}: continue
        if model.kind=='switch':
            if closed: edges.append(set(nodes[:2]))
        elif model.kind=='tactile':
            edges.extend(({nodes[0],nodes[2]},{nodes[1],nodes[3]}))
            if closed: edges.append({nodes[0],nodes[1]})
        elif model.kind=='spdt': edges.append({pins['COM'],pins['B' if closed else 'A']})
        elif model.kind=='multi_switch':
            pos=int(p.get('sim_position',1))
            if not pos and p.get('sim_allow_off','true')=='false': pos=1
            if pos: edges.append({pins['COM'],pins[str(pos)]})
        else: edges.append(set(nodes))
    reachable={a,b}
    while True:
        previous=len(reachable)
        for edge in edges:
            if edge & reachable: reachable.update(edge)
        if len(reachable)==previous: break
    if any(edge <= reachable for edge in sources): return True
    if any(abs(result.voltages.get(n,0)-result.voltages.get(a,0))>1e-6 for n in reachable): return True
    for d in devices:
        if set(d.nodes)<=reachable and abs(result.currents.get(d.component.id,0))>1e-7: return True
    return False
