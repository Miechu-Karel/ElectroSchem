"""Edycja definicji i usuwanie własnych elementów bez utraty geometrii kabli."""
from copy import deepcopy
from app.libraries.built_in import get_definition, validate_custom_definition


def existing_asset_pins_preserved(previous, updated):
    """Whether an asset edit only appends ports and leaves existing anchors stable.

    In-use assets may gain new pins, but moving/removing/reordering old pins
    would leave already-routed sheet wires anchored at their old coordinates.
    Pin names are intentionally not compared so existing ports remain
    renameable.
    """
    old_pins=previous.get("pins",[])
    new_pins=updated.get("pins",[])
    if len(new_pins)<len(old_pins): return False
    for old,new in zip(old_pins,new_pins):
        old_identity=old.get("identity",f"legacy:{old.get('number','')}")
        new_identity=new.get("identity",f"legacy:{new.get('number','')}")
        if (str(old.get("number"))!=str(new.get("number")) or
                old_identity!=new_identity or
                old.get("x")!=new.get("x") or old.get("y")!=new.get("y")):
            return False
    return True


def replace_custom(project, definition):
    definition = validate_custom_definition(definition)
    key = definition["id"]
    index = next(i for i, entry in enumerate(project.custom_components) if entry["id"] == key)
    old = get_definition(key, project.custom_components)
    new_numbers = {pin["number"]: i for i, pin in enumerate(definition["pins"])}
    old_raw=project.custom_components[index]
    old_raw_pins=old_raw.get('pins',[])
    new_identities={pin.get('identity',f"legacy:{pin['number']}"):i for i,pin in enumerate(definition['pins'])}
    new_by_name={}
    for i,pin in enumerate(definition['pins']): new_by_name.setdefault(pin['name'],[]).append(i)
    for sheet in project.sheets:
        ids = {component.id for component in sheet.components if component.library_id == key}
        for wire in sheet.wires:
            for side in ("start", "end"):
                if getattr(wire, side+"_component_id") not in ids:
                    continue
                number = getattr(wire, side+"_pin_number")
                old_index = getattr(wire, side+"_pin_index")
                old_pin=next((p for p in old_raw_pins if str(p.get('number'))==str(number)),None) if number is not None else None
                if old_pin is None and old_index is not None and 0<=old_index<len(old_raw_pins): old_pin=old_raw_pins[old_index]
                identity=(old_pin.get('identity') if old_pin else None) or (f"legacy:{old_pin['number']}" if old_pin else None)
                target=new_identities.get(identity) if identity else None
                if target is None and old_pin and len(new_by_name.get(old_pin['name'],[]))==1: target=new_by_name[old_pin['name']][0]
                if target is not None:
                    setattr(wire, side+"_pin_number", definition['pins'][target]['number'])
                    setattr(wire, side+"_pin_index", target)
                    continue
                if number is None and old_index is not None and 0 <= old_index < len(old.pins):
                    number = old.pins[old_index].number
                if number in new_numbers:
                    setattr(wire, side+"_pin_number", number)
                    setattr(wire, side+"_pin_index", new_numbers[number])
                else:
                    # Końcówka pozostaje tam, gdzie była. Nie przypisujemy jej
                    # do innego sygnału tylko dlatego, że zmienił się indeks.
                    for field in ("component_id", "pin_index", "pin_number"):
                        setattr(wire, side+"_"+field, None)
    project.custom_components[index] = deepcopy(definition)


def remove_custom(project, key):
    """Wywoływane po potwierdzeniu usunięcia definicji i wszystkich jej kopii."""
    for sheet in project.sheets:
        ids = {component.id for component in sheet.components if component.library_id == key}
        for wire in sheet.wires:
            for side in ("start", "end"):
                if getattr(wire, side+"_component_id") in ids:
                    for field in ("component_id", "pin_index", "pin_number"):
                        setattr(wire, side+"_"+field, None)
        sheet.components = [component for component in sheet.components if component.id not in ids]
    project.custom_components = [entry for entry in project.custom_components if entry["id"] != key]
