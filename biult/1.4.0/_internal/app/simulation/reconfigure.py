"""Rebuild topology while preserving device state and Python execution objects."""
from copy import deepcopy
from app.simulation.engine import Circuit,Result

def reconfigure(previous,sheet,custom=(),language='en'):
    circuit=Circuit(sheet,custom,language)
    if previous is None: return circuit
    old={d.component.id:d for d in previous.devices}
    faults={cid:message for part in previous.parts for cid,message in part.result.faults.items()}
    disabled_ids={d.component.id for i,part in enumerate(previous.parts) if i in previous.disabled for d in part.devices}
    scripts={cid:script for part in previous.parts for cid,script in part.scripts.items()}
    circuit.time=previous.time; circuit.gpio_states=deepcopy(previous.gpio_states)
    volts={}
    for key,node in circuit.netlist.pins.items():
        original=previous.netlist.pins.get(key)
        if original is not None: volts[node]=previous.result.voltages.get(original,0.)
    circuit.result=Result(time=previous.time,voltages=volts,
                          faults=deepcopy(previous.result.faults),warnings=dict(circuit.ignored_warnings))
    for i,(part,mapping) in enumerate(zip(circuit.parts,circuit.maps)):
        part.time=previous.time; part.gpio_states=circuit.gpio_states
        part.result=Result(time=previous.time,voltages={local:volts.get(global_node,0.) for local,global_node in mapping.items()})
        for cid in part.scripts:
            if cid in scripts: part.scripts[cid]=scripts[cid]
        for device in part.devices:
            before=old.get(device.component.id)
            if before is not None and before.kind==device.kind:
                device.state=deepcopy(before.state)
                device.previous=before.previous; device.conducting=before.conducting; device.closed=before.closed
                if device.component.id in faults:
                    part.result.faults[device.component.id]=faults[device.component.id]
                if device.component.id in disabled_ids: circuit.disabled.add(i)
    return circuit
