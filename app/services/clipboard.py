"""Schowek schematu: dane, nie kod; nowe ID i izolowane połączenia.

Kopiujemy tylko zaznaczone obiekty. Przewód zachowuje przypisanie do pinu
tylko wtedy, gdy jego komponent też znajduje się w kopiowanym fragmencie.
Definicje customowe wędrują razem z fragmentem również między projektami.
"""
from copy import deepcopy
import json

from app.core.models import Project, Sheet, new_id

MIME_TYPE = "application/x-electroschem-fragment+json"
MAX_BYTES = 8 * 1024 * 1024


def encode_selection(project, sheet, selected):
    fragment = Sheet(name="Clipboard", paper_size=sheet.paper_size,
                     orientation=sheet.orientation, standard=sheet.standard)
    for field in ("components", "wires", "comments"):
        setattr(fragment, field, deepcopy([obj for obj in getattr(sheet, field) if obj.id in selected]))
    if not any((fragment.components, fragment.wires, fragment.comments)):
        return None
    component_ids = {c.id for c in fragment.components}
    for wire in fragment.wires:
        for side in ("start", "end"):
            if getattr(wire, side + "_component_id") not in component_ids:
                for suffix in ("component_id", "pin_index", "pin_number"):
                    setattr(wire, side + "_" + suffix, None)
    used = {c.library_id for c in fragment.components}
    custom = [deepcopy(d) for d in project.custom_components if d["id"] in used]
    payload = {"type": "ElectroSchem selection", "version": 1,
               "project": Project(sheets=[fragment], custom_components=custom).to_dict()}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("Selection is too large / Zaznaczenie jest zbyt duże")
    return encoded


def decode_selection(data):
    if len(data) > MAX_BYTES:
        raise ValueError("Clipboard is too large")
    value = json.loads(data)
    if not isinstance(value, dict) or value.get("type") != "ElectroSchem selection" or value.get("version") != 1:
        raise ValueError("Invalid clipboard format")
    project = Project.from_dict(value["project"])
    if len(project.sheets) != 1:
        raise ValueError("Expected one fragment")
    # Schowek systemowy jest niezaufany tak samo jak plik ELS.
    sheet = project.sheets[0]
    ids = {c.id for c in sheet.components}
    for wire in sheet.wires:
        if wire.points and (wire.points[0] != [wire.start_x, wire.start_y]
                            or wire.points[-1] != [wire.end_x, wire.end_y]):
            raise ValueError("Inconsistent wire endpoints in clipboard")
        for side in ("start", "end"):
            if getattr(wire, side + "_component_id") not in ids:
                for suffix in ("component_id", "pin_index", "pin_number"):
                    setattr(wire, side + "_" + suffix, None)
    return project


def prepare_paste(project, fragment, dx, dy):
    """Przygotuj całą transakcję na kopii, zanim widok zatwierdzi geometrię."""
    staged = deepcopy(project)
    sheet = deepcopy(fragment.sheets[0])
    definitions = {d["id"]: d for d in staged.custom_components}
    library_map = {}
    for definition in fragment.custom_components:
        definition = deepcopy(definition)
        old_id = definition["id"]
        if old_id in definitions and definitions[old_id] != definition:
            definition["id"] = "custom-" + new_id()
        library_map[old_id] = definition["id"]
        if definition["id"] not in definitions:
            staged.custom_components.append(definition)
            definitions[definition["id"]] = definition
    ids = {obj.id: new_id() for field in ("components", "wires", "comments") for obj in getattr(sheet, field)}
    junctions = {}
    for component in sheet.components:
        component.id = ids[component.id]
        component.library_id = library_map.get(component.library_id, component.library_id)
        component.reference = staged.allocate_reference(component.library_id)
        component.x += dx
        component.y += dy
    for comment in sheet.comments:
        comment.id = ids[comment.id]
        comment.x += dx
        comment.y += dy
    for wire in sheet.wires:
        wire.id = ids[wire.id]
        wire.points = [[x + dx, y + dy] for x, y in wire.points]
        for side in ("start", "end"):
            setattr(wire, side + "_x", getattr(wire, side + "_x") + dx)
            setattr(wire, side + "_y", getattr(wire, side + "_y") + dy)
            setattr(wire, side + "_component_id", ids.get(getattr(wire, side + "_component_id")))
            junction = getattr(wire, side + "_junction_id")
            if junction:
                setattr(wire, side + "_junction_id", junctions.setdefault(junction, new_id()))
    return staged, sheet
