"""Model operations shared by mouse-driven editing and command proposals."""
import math
from app.core.component_defaults import apply_defaults


def add_component(project, sheet, library_id, x, y, settings=None):
    component = project.new_component(library_id, x, y)
    if settings is not None: apply_defaults(component, settings)
    sheet.components.append(component)
    return component


def remove_component(sheet, component_id):
    if not any(c.id == component_id for c in sheet.components):
        raise ValueError("Unknown component")
    # Deleting a body leaves its wires as free cable ends, exactly as in GUI.
    for wire in sheet.wires:
        for side in ("start", "end"):
            if getattr(wire, side+"_component_id") == component_id:
                for name in ("component_id", "pin_index", "pin_number"):
                    setattr(wire, side+"_"+name, None)
    sheet.components[:] = [c for c in sheet.components if c.id != component_id]


def set_position(component, x, y):
    if not all(math.isfinite(float(v)) for v in (x, y)):
        raise ValueError("Invalid position")
    component.x, component.y = x, y


def set_rotation(component, angle):
    if not isinstance(angle, int) or angle % 90:
        raise ValueError("Rotation must be a multiple of 90")
    component.rotation = angle % 360


def set_property(component, name, value):
    if name in {"display_name", "value", "unit", "show_name", "show_value"}:
        setattr(component, name, value)
    else:
        component.properties[name] = value
