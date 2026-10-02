"""Sieci elektryczne: końce, piny i jawne węzły; skrzyżowanie nie jest węzłem."""
from dataclasses import dataclass
from math import cos, sin, radians
from app.libraries.built_in import get_definition
from app.libraries.emulator_catalog import profile_for, gpio_name


@dataclass
class Netlist:
    pins: dict
    wires: dict
    count: int
    definitions: dict


def build_netlist(sheet, custom=()):
    parent = {}
    def find(a):
        parent.setdefault(a, a)
        if parent[a] != a:
            parent[a] = find(parent[a])
        return parent[a]
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b
    def position(x, y):
        return ("xy", round(x, 5), round(y, 5))

    definitions, pin_keys = {}, {}
    for component in sheet.components:
        d = get_definition(component.library_id, custom)
        definitions[component.id] = d
        if not d:
            continue
        angle = radians(component.rotation)
        for index, pin in enumerate(d.pins):
            key = ("pin", component.id, pin.number)
            pin_keys[(component.id, index)] = key
            x = component.x + pin.x*cos(angle)-pin.y*sin(angle)
            y = component.y + pin.x*sin(angle)+pin.y*cos(angle)
            union(key, position(x, y))
            # Powtórzone wyprowadzenia tej samej szyny wewnątrz modułu
            # (np. dwa GND sterownika krokowego) są jednym węzłem.
            # NC i styki o innych nazwach pozostają niezależne.
            if pin.name in {"GND", "VCC", "VDD", "VSS", "3V3", "5V"}:
                union(key,("internal_supply",component.id,pin.name))
            if d.symbol == "ground": union(key, ("ground",))
            if d.symbol == "power": union(key, ("rail", d.id))
            profile = profile_for(d)
            if profile:
                from app.simulation.gpio_script import gpio_alias
                alias = (gpio_name(pin.name, profile.engine) if profile.ready else gpio_alias(pin.name)) or pin.name
                union(key, ("board", component.id, alias))
                if pin.name in {"GND", "AGND"}: union(key, ("internal_supply", component.id, "GND"))
    wire_keys = {}
    for wire in sheet.wires:
        key = ("wire", wire.id)
        wire_keys[wire.id] = key
        for side in ("start", "end"):
            # Edytor rozcina przewód przy tworzeniu T. Same przecięcia
            # odcinków, bez końca lub junction_id, pozostają odizolowane.
            union(key, position(getattr(wire, side+"_x"), getattr(wire, side+"_y")))
            cid = getattr(wire, side+"_component_id")
            number = getattr(wire, side+"_pin_number")
            index = getattr(wire, side+"_pin_index")
            if cid is not None and cid not in definitions:
                raise ValueError("Unknown component anchor: " + wire.id)
            if cid in definitions and definitions[cid]:
                pins = definitions[cid].pins
                if number is not None:
                    indices = [i for i, p in enumerate(pins) if p.number == str(number)]
                    if not indices:
                        raise ValueError("Invalid pin anchor: " + wire.id)
                    index = indices[0]
                if index is None or not 0 <= index < len(pins):
                    raise ValueError("Invalid pin anchor: " + wire.id)
                union(key, pin_keys[(cid, index)])
            junction = getattr(wire, side+"_junction_id")
            if junction: union(key, ("junction", junction))
    roots = {}
    def number(key):
        root = find(key)
        if root not in roots: roots[root] = len(roots)
        return roots[root]
    pins = {k: number(v) for k, v in pin_keys.items()}
    wires = {k: number(v) for k, v in wire_keys.items()}
    return Netlist(pins, wires, len(roots), definitions)
