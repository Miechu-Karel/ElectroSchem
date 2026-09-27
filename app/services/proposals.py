"""Transakcyjne zastosowanie danych AI: cały schemat albo żadna zmiana.

Nie wykonujemy tekstu opisu zachowania jako kodu. Projekt roboczy jest kopią;
nieznane elementy, piny i błędna geometria powodują odrzucenie całej propozycji.
"""
from copy import deepcopy
from app.core.models import Project, Wire
from app.libraries.built_in import ITEM_BY_ID, get_definition
from app.services.gemini import validate_proposal
from PySide6.QtCore import QPointF, QRectF
from app.canvas.page import drawing_contains, route_allowed, title_block_rect, GRID_STEP


def apply_proposal(project: Project, sheet_index: int, payload: dict) -> Project:
    proposal = validate_proposal(dict(payload, summary=payload.get("summary", "")))
    result = Project.from_dict(deepcopy(project.to_dict()))
    sheet = result.sheets[sheet_index]
    existing_custom = {entry["id"] for entry in result.custom_components}
    for raw in proposal["custom_components"]:
        if raw["id"] in ITEM_BY_ID or raw["id"] in existing_custom:
            raise ValueError("Duplicate custom component definition")
        entry = deepcopy(raw)
        entry["category"], entry["symbol"] = "Własne", "module"
        # Lokalne współrzędne używają dokładnie tej samej skali co płótno.
        # Wymiary parzystej liczby kratek utrzymują obie krawędzie na siatce.
        if any(entry[k] % 40 for k in ("width", "height")):
            raise ValueError("Custom body must use whole grid squares")
        for pin in entry["pins"]:
            if pin["x"] % 20 or pin["y"] % 20:
                raise ValueError("Pin is not on the grid")
            if abs(pin["x"]) > entry["width"]/2 or abs(pin["y"]) > entry["height"]/2:
                raise ValueError("Pin outside component selection area")
            if abs(pin["x"]) != entry["width"]/2 and abs(pin["y"]) != entry["height"]/2:
                raise ValueError("Pins must be on a body edge")
        result.custom_components.append(entry)
        existing_custom.add(entry["id"])
    by_key = {c.id: c for c in sheet.components}
    by_key.update({c.reference: c for c in sheet.components})
    # Wspólna geometria z edytorem: także obszar po lewej od tabliczki.
    for raw in proposal["components"]:
        if raw["key"] in by_key:
            raise ValueError("Duplicate component key")
        definition = get_definition(raw["library_id"], result.custom_components)
        if definition is None:
            raise ValueError("Unknown library ID")
        x, y = round(raw["x"]/20)*20, round(raw["y"]/20)*20
        if not drawing_contains(sheet, QRectF(x-definition.width/2, y-definition.height/2,
                                              definition.width, definition.height)):
            raise ValueError("Component outside the drawing area / Element poza obszarem rysowania: " + raw["key"])
        component = result.new_component(raw["library_id"], x, y)
        for field in ("display_name", "value", "unit"):
            if field in raw:
                setattr(component, field, raw[field])
        sheet.components.append(component)
        by_key[raw["key"]] = component

    def endpoint(key, index):
        component = by_key.get(key)
        if component is None:
            raise ValueError("Unknown connection target")
        definition = get_definition(component.library_id, result.custom_components)
        if definition is None or index >= len(definition.pins):
            raise ValueError("Unknown pin")
        pin = definition.pins[index]
        x, y = pin.x, pin.y
        # Ćwierćobroty liczymy bez błędów trygonometrii, identycznie jak Qt.
        for _ in range(component.rotation // 90):
            x, y = -y, x
        return component, component.x+x, component.y+y, pin.number

    for raw in proposal["wires"]:
        start, x1, y1, number1 = endpoint(raw["from"], raw["from_pin"])
        end, x2, y2, number2 = endpoint(raw["to"], raw["to_pin"])
        if not all(drawing_contains(sheet, QPointF(x, y)) for x, y in ((x1, y1), (x2, y2))):
            raise ValueError("Wire endpoint is outside the drawing area")
        def route(a, b):
            dx, dy = b.x()-a.x(), b.y()-a.y()
            if abs(dx) < .001 or abs(dy) < .001 or abs(abs(dx)-abs(dy)) < .001:
                return [a, b]
            middle = QPointF(a.x()+(abs(dy) if dx > 0 else -abs(dy)), b.y()) if abs(dx) > abs(dy) else QPointF(b.x(), a.y()+(abs(dx) if dy > 0 else -abs(dx)))
            return [a, middle, b]
        a, b = QPointF(x1, y1), QPointF(x2, y2)
        block = title_block_rect(sheet)
        corner = QPointF(block.left()-GRID_STEP, block.top()-GRID_STEP)
        routes = [route(a, b), list(reversed(route(b, a))), route(a, corner)[:-1]+route(corner, b)]
        points = next((p for p in routes if route_allowed(sheet, p)), None)
        if points is None:
            raise ValueError("Wire crosses title block / Przewód przecina tabliczkę rysunkową")
        sheet.wires.append(Wire(x1, y1, x2, y2, points=[[p.x(), p.y()] for p in points], start_component_id=start.id,
                               start_pin_index=raw["from_pin"], end_component_id=end.id,
                               end_pin_index=raw["to_pin"], start_pin_number=number1,
                               end_pin_number=number2))
    return result
