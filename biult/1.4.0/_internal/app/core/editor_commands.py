"""Whitelisted editor commands. Batches run on a copy, never in a shell."""
from copy import deepcopy
import math
import shlex

from PySide6.QtCore import QPointF
from PySide6.QtGui import QTransform
from app.core.editor_operations import add_component, remove_component, set_position, set_rotation, set_property
from app.core.models import Project
from app.libraries.built_in import get_definition
from app.canvas.page import drawing_contains, route_allowed

FIELDS = {
    "HELP": (set(), set()),
    "ADD_COMPONENT": ({"type", "id", "x", "y", "value", "unit", "display_name"}, {"type", "id", "x", "y"}),
    "DELETE_COMPONENT": ({"id"}, {"id"}),
    "MOVE_COMPONENT": ({"id", "x", "y"}, {"id", "x", "y"}),
    "ROTATE_COMPONENT": ({"id", "angle"}, {"id", "angle"}),
    "SET_PROPERTY": ({"id", "property", "value"}, {"id", "property", "value"}),
    "CONNECT": ({"from", "to", "from_pin", "to_pin"}, {"from", "to", "from_pin", "to_pin"}),
    "DISCONNECT": ({"id"}, {"id"}),
    "PLUG_CABLE": ({"id","side","target","pin"},{"id","side","target"}),
}


def parse_commands(text):
    if not isinstance(text, str) or len(text) > 200000:
        raise ValueError("Invalid command input")
    commands = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        tokens = shlex.split(line, comments=False)
        operation = tokens.pop(0).upper()
        if operation not in FIELDS:
            raise ValueError(f"Line {number}: unknown command {operation}")
        args = {}
        for token in tokens:
            key, separator, value = token.partition("=")
            if not separator or key in args:
                raise ValueError(f"Line {number}: invalid or duplicate argument")
            args[key] = value
        allowed, required = FIELDS[operation]
        if set(args) - allowed or required - set(args):
            extra=", ".join(sorted(set(args)-allowed)); missing=", ".join(sorted(required-set(args)))
            raise ValueError(f"Line {number}: invalid arguments for {operation}; unexpected: {extra or '-'}; missing: {missing or '-'}")
        commands.append((operation, args))
        if len(commands) > 1000:
            raise ValueError("Too many commands")
    return commands


def _coordinate(raw):
    value = float(raw)
    if not math.isfinite(value) or abs(value) > 100000:
        raise ValueError("Invalid coordinate")
    return round(value / 20) * 20


def _component(sheet, key):
    matches = [c for c in sheet.components if key in (c.id, c.reference)]
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous component: " + key)
    return matches[0]


def _geometry(project, sheet, component):
    from app.libraries.built_in import get_instance_definition
    definition = get_instance_definition(component, project.custom_components)
    from app.canvas.component_item import ComponentItem
    rect = ComponentItem.selection_rect(definition, show_name=component.show_name)
    transformed = QTransform().rotate(component.rotation).mapRect(rect).translated(component.x, component.y)
    if not drawing_contains(sheet, transformed):
        raise ValueError("Component outside drawing area: " + component.reference)


def _validate_value(project, component):
    definition = get_definition(component.library_id, project.custom_components)
    if definition.default_unit and component.value:
        from app.core.units import parse_value, split_unit
        number, unit = parse_value(component.value, component.unit or definition.default_unit)
        if split_unit(unit)[1] != split_unit(definition.default_unit)[1]:
            raise ValueError("Wrong component unit")
        set_property(component, "value", number)
        set_property(component, "unit", unit)


def _pin(project, component, index):
    from app.libraries.built_in import get_instance_definition
    definition = get_instance_definition(component, project.custom_components)
    index = int(index)
    if not 0 <= index < len(definition.pins):
        raise ValueError("Unknown pin")
    pin = definition.pins[index]
    x, y = pin.x, pin.y
    for _ in range(component.rotation // 90):
        x, y = -y, x
    return QPointF(component.x+x, component.y+y)


def _refresh_wires(project, sheet):
    # The same checked router is used for newly connected and moved pins.
    from app.services.proposals import apply_proposal
    anchored = [w for w in sheet.wires if w.start_component_id and w.end_component_id]
    for wire in anchored:
        start = _component(sheet, wire.start_component_id)
        end = _component(sheet, wire.end_component_id)
        a, b = _pin(project, start, wire.start_pin_index), _pin(project, end, wire.end_pin_index)
        if abs(a.x()-wire.start_x)<.001 and abs(a.y()-wire.start_y)<.001 and abs(b.x()-wire.end_x)<.001 and abs(b.y()-wire.end_y)<.001:
            continue
        staging=deepcopy(project); staging.sheets[project.sheets.index(sheet)].wires=[w for w in staging.sheets[project.sheets.index(sheet)].wires if w.id!=wire.id]
        routed = apply_proposal(staging, project.sheets.index(sheet), {
            "components": [], "custom_components": [], "wires": [{"from": start.id, "to": end.id,
            "from_pin": wire.start_pin_index, "to_pin": wire.end_pin_index}]})
        replacement = routed.sheets[project.sheets.index(sheet)].wires[-1]
        for name in ("start_x", "start_y", "end_x", "end_y", "points"):
            setattr(wire, name, deepcopy(getattr(replacement, name)))
    # Single-ended wires retain their free end and track the attached pin.
    for wire in sheet.wires:
        if wire in anchored:
            continue
        points = deepcopy(wire.points) or [[wire.start_x, wire.start_y], [wire.end_x, wire.end_y]]
        for side, position in (("start", 0), ("end", -1)):
            key = getattr(wire, side+"_component_id")
            if key:
                p = _pin(project, _component(sheet, key), getattr(wire, side+"_pin_index"))
                setattr(wire, side+"_x", p.x()); setattr(wire, side+"_y", p.y())
                points[position] = [p.x(), p.y()]
        if not route_allowed(sheet, [QPointF(*p) for p in points]):
            raise ValueError("Wire outside drawing area")
        wire.points = points


def execute_batch(project, sheet_index, text):
    commands = parse_commands(text)
    result = Project.from_dict(deepcopy(project.to_dict()))
    sheet = result.sheets[sheet_index]
    for operation, args in commands:
        if operation == "HELP":
            continue
        if operation == "ADD_COMPONENT":
            if any(args["id"] in (c.id, c.reference) for s in result.sheets for c in s.components):
                raise ValueError("Duplicate component ID")
            key = args["id"]
            if not key or len(key)>160 or any(c.isspace() for c in key):
                raise ValueError("Invalid component ID")
            component = add_component(result, sheet, args["type"], _coordinate(args["x"]), _coordinate(args["y"]))
            component.reference = key
            for field in ("value", "unit", "display_name"):
                if field in args:
                    set_property(component, field, args[field])
            _geometry(result, sheet, component)
            _validate_value(result, component)
        elif operation == "CONNECT":
            from app.services.proposals import apply_proposal
            result = apply_proposal(result, sheet_index, {"components": [], "custom_components": [],
                "wires": [dict(args, from_pin=int(args["from_pin"]), to_pin=int(args["to_pin"]))]})
            sheet = result.sheets[sheet_index]
        elif operation == "DISCONNECT":
            wire = next((w for w in sheet.wires if w.id == args["id"]), None)
            if wire is None:
                raise ValueError("Unknown wire")
            sheet.wires.remove(wire)
        elif operation == 'PLUG_CABLE':
            from app.core.cable_connections import attach
            attach(sheet,_component(sheet,args['id']),args['side'],_component(sheet,args['target']),int(args.get('pin','0')),result.custom_components)
        else:
            component = _component(sheet, args["id"])
            if operation == "DELETE_COMPONENT":
                remove_component(sheet, component.id)
            elif operation == "MOVE_COMPONENT":
                set_position(component, _coordinate(args["x"]), _coordinate(args["y"]))
            elif operation == "ROTATE_COMPONENT":
                angle = int(args["angle"])
                if angle % 90:
                    raise ValueError("Rotation must be a multiple of 90")
                set_rotation(component, angle)
            elif operation == "SET_PROPERTY":
                name, value = args["property"], args["value"]
                if len(value) > 1000:
                    raise ValueError("Property too long")
                if name in {"value", "unit", "display_name"}:
                    set_property(component, name, value)
                elif name == "color" and get_definition(component.library_id, result.custom_components).symbol == "led":
                    from app.core.led_colors import color_key
                    if not color_key(value): raise ValueError("Invalid LED colour")
                    set_property(component, name, color_key(value))
                elif name == "voltage" and get_definition(component.library_id, result.custom_components).symbol in {"capacitor", "polar_capacitor"}:
                    from app.simulation.engine import si_value
                    si_value(value, "V")
                    set_property(component, name, value)
                else:
                    from app.libraries.simulation_catalog import behavior_for
                    model = behavior_for(get_definition(component.library_id, result.custom_components))
                    parameter = next((p for p in model.parameters if p.key == name), None) if model else None
                    if parameter is None or name in {"sim_source", "sim_firmware", "sim_code_folder", "sim_bootrom"}:
                        raise ValueError("Property is not editable by commands")
                    if parameter.choices and value not in {choice[0] for choice in parameter.choices}:
                        raise ValueError("Invalid parameter choice")
                    if name == "rfid_id":
                        if len(value)!=8 or any(c not in "0123456789abcdefABCDEF" for c in value): raise ValueError("Invalid RFID ID")
                    elif not parameter.choices and not (name == "sim_initial_voltage" and value == "auto"):
                        from app.simulation.engine import si_value
                        numeric = si_value(value, parameter.unit, parameter.minimum, parameter.maximum)
                        if not parameter.minimum <= numeric <= parameter.maximum:
                            raise ValueError("Parameter outside range")
                    set_property(component, name, value)
            if operation != "DELETE_COMPONENT":
                _geometry(result, sheet, component)
                _validate_value(result, component)
            _refresh_wires(result, sheet)
    return Project.from_dict(result.to_dict())


class CommandSession:
    """Working proposal, transaction boundary and optimistic conflict check."""
    def __init__(self, project, sheet_index):
        self.base = deepcopy(project.to_dict())
        self.sheet_index = sheet_index
        self.working = Project.from_dict(deepcopy(self.base))

    def execute(self, text):
        self.working = execute_batch(self.working, self.sheet_index, text)
        return self.working

    def accept(self, current):
        if current.to_dict() != self.base:
            raise ValueError("Project changed; start a new proposal before accepting")
        return Project.from_dict(deepcopy(self.working.to_dict()))

    def reject(self):
        self.working = Project.from_dict(deepcopy(self.base))
