"""Edycja definicji i usuwanie własnych elementów bez utraty geometrii kabli."""
from copy import deepcopy
from app.libraries.built_in import get_definition, validate_custom_definition


def replace_custom(project, definition):
    definition = validate_custom_definition(definition)
    key = definition["id"]
    index = next(i for i, entry in enumerate(project.custom_components) if entry["id"] == key)
    old = get_definition(key, project.custom_components)
    new_numbers = {pin["number"]: i for i, pin in enumerate(definition["pins"])}
    for sheet in project.sheets:
        ids = {component.id for component in sheet.components if component.library_id == key}
        for wire in sheet.wires:
            for side in ("start", "end"):
                if getattr(wire, side+"_component_id") not in ids:
                    continue
                number = getattr(wire, side+"_pin_number")
                old_index = getattr(wire, side+"_pin_index")
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
