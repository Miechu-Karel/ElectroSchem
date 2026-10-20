"""Sieci elektryczne: końce, piny i jawne węzły; skrzyżowanie nie jest węzłem."""
from dataclasses import dataclass
from math import cos, sin, radians
from app.libraries.built_in import get_definition,get_instance_definition
from app.libraries.emulator_catalog import profile_for, gpio_name
from app.simulation.jumper import JUMPER_IDS,GENDERS


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
        d = get_instance_definition(component, custom)
        definitions[component.id] = d
        if not d:
            continue
        angle = radians(component.rotation)
        for index, pin in enumerate(d.pins):
            key = ("pin", component.id, pin.number)
            pin_keys[(component.id, index)] = key
            x = component.x + pin.x*cos(angle)-pin.y*sin(angle)
            y = component.y + pin.x*sin(angle)+pin.y*cos(angle)
            if d.name in {"Kabel USB","Kostka zasilająca USB","Klawiatura USB"} or component.library_id in JUMPER_IDS or d.symbol=='breadboard' or (d.symbol=='goldpin' and index==0):
                find(key)  # Internal contacts: only plugged connectors or legacy explicit anchors connect them.
            else:
                union(key, position(x, y))
            if d.name.startswith(("Port USB", "Port Lightning")):
                if pin.name.startswith("VBUS") or pin.name == "POWER": union(key, ("port_power", component.id))
                if pin.name.startswith("GND"): union(key, ("port_ground", component.id))
            if d.symbol=='goldpin': union(key, ("goldpin", component.id))
            if d.symbol=='breadboard': union(key,('breadboard',component.id,pin.name.split('.')[0]))
            if component.library_id in JUMPER_IDS: union(key,('jumper',component.id))
            if d.name == "Kabel USB": union(key, ("usb_cable", component.id, pin.name.split(".", 1)[1]))
            # Powtórzone wyprowadzenia tej samej szyny wewnątrz modułu
            # (np. dwa GND sterownika krokowego) są jednym węzłem.
            # NC i styki o innych nazwach pozostają niezależne.
            if pin.name in {"GND", "VCC", "VDD", "VSS", "3V3", "5V"}:
                union(key,("internal_supply",component.id,pin.name))
            if d.name.startswith('Układ Scalony ') and pin.name in {'OUT','SW','PGND','VOUT'}:
                union(key,('internal_ic',component.id,pin.name))
            if d.name=='Układ Scalony TPS61030' and pin.name in {'GND','PGND'}:
                union(key,('internal_ic',component.id,'PGND'))
            if d.symbol == "ground": union(key, ("ground",))
            if d.symbol == "power": union(key, ("rail", d.id))
            profile = profile_for(d)
            if profile:
                from app.simulation.gpio_script import gpio_alias
                alias = (gpio_name(pin.name, profile.engine) if profile.ready else gpio_alias(pin.name)) or pin.name
                union(key, ("board", component.id, alias))
                if pin.name in {"GND", "AGND"}: union(key, ("internal_supply", component.id, "GND"))
    from app.simulation.usb import links
    components={c.id:c for c in sheet.components}
    for cable in sheet.components:
        definition=definitions.get(cable.id)
        if definition and cable.library_id in JUMPER_IDS:
            for side,index in (('a',0),('b',1)):
                target=components.get(cable.properties.get('jumper_'+side+'_target'))
                if target and (td:=definitions.get(target.id)) and td.symbol=='goldpin':
                    gender='female' if td.name=='Goldpin żeński' else 'male'
                    if GENDERS.get(cable.library_id,('',''))[index]!=gender: union(('jumper',cable.id),pin_keys[target.id,0])
                elif target and (td:=definitions.get(target.id)) and td.symbol=='breadboard' and GENDERS.get(cable.library_id,('',''))[index]=='male':
                    try: hole=int(cable.properties.get('jumper_'+side+'_pin','0'))
                    except (ValueError,TypeError): continue
                    if 0<=hole<len(td.pins): union(('jumper',cable.id),pin_keys[target.id,hole])
        if definitions.get(cable.id) and definitions[cable.id].name=="Kabel USB":
            for side in ("A","B"):
                target=components.get(cable.properties.get("usb_"+side.lower()+"_target"))
                if target and definitions.get(target.id):
                    for signal,index in links(cable,side,target,definitions[target.id]):
                        union(("usb_cable",cable.id,signal),pin_keys[target.id,index])
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
                # Old ELS files may already contain explicit TOP anchors. Keep
                # those links; the editor/command validator rejects NEW ones.
                if definitions[cid].symbol=='breadboard':
                    raise ValueError('Jumper contact accepts cables only: '+wire.id)
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
