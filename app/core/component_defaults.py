"""Nominal catalogue values and opt-in user defaults for new instances."""
from copy import deepcopy


def nominal_value(definition):
    # A specifically named 9 V battery should be usable without typing 9 V.
    # Existing explicit values are never replaced (e.g. a discharged battery).
    if definition and definition.name=="Zasilacz Raspberry Pi USB-C 27 W": return "5.1","V"
    return ("9", "V") if definition and definition.name == "Bateria 9V" else ("", getattr(definition,"default_unit", ""))


def value_defaults(component):
    from app.libraries.built_in import get_definition
    from app.libraries.simulation_catalog import behavior_for
    model=behavior_for(get_definition(component.library_id))
    keys={"voltage","color","show_voltage","show_color"}
    if model: keys.update(p.key for p in model.parameters)
    return {"value":component.value,"unit":component.unit,"show_value":component.show_value,
            "properties":{k:deepcopy(v) for k,v in component.properties.items() if k in keys}}


def apply_defaults(component, settings):
    saved=getattr(settings,"default_component_values",{}).get(component.library_id,{})
    for key in ("value","unit","show_value"):
        if key in saved: setattr(component,key,saved[key])
    component.properties.update(deepcopy(saved.get("properties",{})))


def validate_defaults(raw):
    """Reject malformed preferences, without preventing application startup."""
    if not isinstance(raw,dict): return {}
    result={}
    for key,entry in list(raw.items())[:2000]:
        if not isinstance(key,str) or not isinstance(entry,dict): continue
        clean={k:v for k,v in entry.items() if k in {"value","unit"} and isinstance(v,str) and len(v)<=100}
        if type(entry.get("show_value")) is bool: clean["show_value"]=entry["show_value"]
        props=entry.get("properties",{})
        if isinstance(props,dict):
            clean["properties"]={k:v for k,v in props.items() if isinstance(k,str)
                and (k in {"color","voltage","show_color","show_voltage"} or k.startswith("sim_"))
                and k not in {"sim_source","sim_firmware","sim_bootrom","sim_mode","sim_code_folder"}
                and (type(v) is bool or isinstance(v,str) and len(v)<=100)}
        result[key]=clean
    return result
