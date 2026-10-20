"""Reusable circuit assets are bounded document data, never plugins or code."""
from copy import deepcopy
from dataclasses import asdict
from math import ceil, cos, sin, radians
from uuid import uuid5, NAMESPACE_URL
import json
from app.core.models import Project, Sheet, new_id

def _asset_member_allowed(component, custom):
    from app.libraries.built_in import get_instance_definition
    definition=get_instance_definition(component,custom)
    if definition is None: return False
    if definition.category=='Własne':
        nested=next((d for d in custom if isinstance(d,dict) and d.get('id')==component.library_id and 'asset' in d),None)
        if not nested: return False
        asset=nested['asset']; sheet=nested.get('asset',{}).get('sheet',{})
        return not asset.get('boxed',False) or len(sheet.get('components',[]))<=3
    if definition.category in {'Elementy pasywne','Półprzewodniki'}: return True
    from app.libraries.menu_groups import subgroup
    _,group=subgroup(definition)
    if group in {'Światło i podczerwień','Buzzery'}: return True
    if group=='Przyciski i przełączniki':
        name=(definition.name+' '+definition.name_en).casefold()
        return 'keypad' not in name and 'klawiatura' not in name and 'keyboard' not in name
    if definition.category=='Układy i sterowniki':
        _,group=subgroup(definition)
        return group not in {'Zegary RTC','Układy zarządzania zasilaniem','Scaliki czujników','Sterowniki silników'}
    return False

def make_asset(project, sheet, name, boxed=False, selected=None, grouped=True):
    from app.simulation.netlist import build_netlist
    source=deepcopy(sheet)
    if selected:
        source.components=[c for c in source.components if c.id in selected]
        allowed=[w for w in source.wires if all(cid is None or cid in selected for cid in (w.start_component_id,w.end_component_id))]
        kept=set(); junctions=set()
        while True:
            fresh=[w for w in allowed if w.id not in kept and (w.start_component_id in selected or w.end_component_id in selected or w.start_junction_id in junctions or w.end_junction_id in junctions)]
            if not fresh: break
            for wire in fresh:
                kept.add(wire.id); junctions.update(j for j in (wire.start_junction_id,wire.end_junction_id) if j)
        source.wires=[w for w in allowed if w.id in kept]
        source.comments=[]
    if not source.components: raise ValueError("Empty asset / Pusty asset")
    if len(source.components)>100: raise ValueError("Asset limit: 100 components / Limit assetu: 100 elementów")
    rejected=[c.reference for c in source.components if not _asset_member_allowed(c,project.custom_components)]
    if rejected: raise ValueError('These components are not allowed in an Asset: '+', '.join(rejected[:8]))
    source=expand_assets(source,project.custom_components)
    if len(source.components)>100: raise ValueError("Asset limit: 100 components / Limit assetu: 100 elementów")
    cx=round(sum(c.x for c in source.components)/len(source.components)/20)*20
    cy=round(sum(c.y for c in source.components)/len(source.components)/20)*20
    for c in source.components: c.x-=cx; c.y-=cy
    for w in source.wires:
        w.start_x-=cx; w.end_x-=cx; w.start_y-=cy; w.end_y-=cy
        w.points=[[x-cx,y-cy] for x,y in w.points]
    for note in source.comments: note.x-=cx; note.y-=cy
    netlist=build_netlist(source,project.custom_components); seen=set(); exports=[]
    for c in source.components:
        for i,pin in enumerate(netlist.definitions[c.id].pins):
            node=netlist.pins[c.id,i]
            if node in seen: continue
            seen.add(node); exports.append({"component":c.id,"pin":i,"name":c.reference+"."+pin.name})
    if len(exports)>128: raise ValueError("Asset limit: 128 exposed nets / Limit assetu: 128 wyprowadzonych sieci")
    exports=exports or [{"component":None,"pin":None,"name":"NC"}]
    count=len(exports); width=320; height=max(120,ceil((ceil(count/2)*20+60)/40)*40)
    pins=[]
    for i,port in enumerate(exports):
        half=ceil(count/2); row=i if i<half else count-1-i
        pins.append({"number":str(i+1),"name":port["name"],"x":-width/2 if i<half else width/2,"y":-height/2+40+row*20})
    used={c.library_id for c in source.components}
    custom=[deepcopy(d) for d in project.custom_components if d["id"] in used and "asset" not in d]
    return {"id":"asset_"+new_id(),"name":name.strip()[:200],"name_en":name.strip()[:200],
        "reference_prefix":"Asset","symbol":"module","width":width,"height":height,"pins":pins,
        "asset":{"schema":1,"boxed":bool(boxed),"grouped":bool(grouped),"editable_properties":[],"sheet":asdict(source),"custom":custom,"exports":exports}}

def validate_asset(payload):
    if not isinstance(payload,dict) or payload.get("schema")!=1 or type(payload.get("boxed")) is not bool: raise ValueError("Invalid asset")
    custom=payload.get("custom",[])
    if not isinstance(custom,list) or any(not isinstance(d,dict) or "asset" in d for d in custom): raise ValueError("Nested asset definitions are not allowed")
    project=Project.from_dict({"format_version":3,"sheets":[payload.get("sheet")],"custom_components":custom})
    sheet=project.sheets[0]
    if not 1<=len(sheet.components)<=100 or len(sheet.wires)>300: raise ValueError("Asset too large")
    exports=payload.get("exports")
    if not isinstance(exports,list) or not 1<=len(exports)<=128: raise ValueError("Invalid asset exports")
    if 'case' in payload:
        from math import isfinite
        case=payload['case']
        if not isinstance(case,dict): raise ValueError('Invalid asset case')
        selection=case.get('selection_rect')
        if selection is not None:
            if not isinstance(selection,list) or len(selection)!=4 or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>2000 for v in selection) or selection[2]<=0 or selection[3]<=0: raise ValueError('Invalid selection rectangle')
        if 'free_pins' in case and type(case['free_pins']) is not bool: raise ValueError('Invalid free-pin flag')
        if 'show_pin_names' in case and type(case['show_pin_names']) is not bool: raise ValueError('Invalid pin-name display flag')
        regions=case.get('regions',[])
        if not isinstance(regions,list) or len(regions)>100: raise ValueError('Invalid case regions')
        for region in regions:
            if not isinstance(region,dict) or region.get('kind') not in ('light','interaction') or region.get('component') not in {c.id for c in sheet.components}: raise ValueError('Invalid case region target')
            rect=region.get('rect')
            if not isinstance(rect,list) or len(rect)!=4 or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>2000 for v in rect) or rect[2]<=0 or rect[3]<=0: raise ValueError('Invalid case region geometry')
        # Legacy assets may still contain the retired miniature scale. It is
        # ignored; all inner parts now render at their original dimensions.
        if 'scale' in case and (type(case['scale']) not in (int,float) or not .05<=case['scale']<=1): raise ValueError('Invalid miniature scale')
        shapes=case.get('shapes')
        if not isinstance(shapes,list) or not 1<=len(shapes)<=200: raise ValueError('Invalid case shapes')
        for shape in shapes:
            if not isinstance(shape,dict) or shape.get('kind') not in ('rect','circle','path'): raise ValueError('Invalid case shape')
            if shape['kind']=='path':
                points=shape.get('points')
                if not isinstance(points,list) or not 2<=len(points)<=2000 or type(shape.get('closed',False)) is not bool: raise ValueError('Invalid case path')
                if any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>2000 for v in p) for p in points): raise ValueError('Invalid case path point')
                continue
            rect=shape.get('rect')
            if not isinstance(rect,list) or len(rect)!=4 or any(type(v) not in (int,float) or not isfinite(v) or abs(v)>2000 for v in rect) or rect[2]<=0 or rect[3]<=0: raise ValueError('Invalid case rectangle')
    from app.libraries.built_in import get_definition,get_instance_definition
    components={c.id:c for c in sheet.components}
    for port in exports:
        if not isinstance(port,dict) or not isinstance(port.get("name"),str): raise ValueError("Invalid asset port")
        if port.get("component") is None and port.get("pin") is None: continue
        c=components.get(port.get("component")); d=get_instance_definition(c,custom) if c else None
        if not d or type(port.get("pin")) is not int or not 0<=port["pin"]<len(d.pins): raise ValueError("Invalid asset pin")
    return deepcopy(payload)

def instantiate(payload, instance, project=None):
    payload=validate_asset(payload)
    sheet=Project.from_dict({"format_version":3,"sheets":[payload["sheet"]],"custom_components":payload["custom"]}).sheets[0]
    mapping={c.id:(new_id() if project else str(uuid5(NAMESPACE_URL,instance.id+":"+c.id))) for c in sheet.components}
    group=new_id() if project and payload.get('grouped',True) else None
    angle=radians(instance.rotation)
    def point(x,y): return [instance.x+x*cos(angle)-y*sin(angle),instance.y+x*sin(angle)+y*cos(angle)]
    for c in sheet.components:
        if group: c.properties["asset_group"]=group
        old=c.id
        if old in payload.get('editable_properties',[]): c.properties['_asset_properties_editable']='true'
        elif 'editable_properties' in payload: c.properties['_asset_properties_editable']='false'
        c.id=mapping[old]; c.x,c.y=point(c.x,c.y); c.rotation=(c.rotation+instance.rotation)%360
        for key in ("usb_a_target","usb_b_target",'jumper_a_target','jumper_b_target'):
            if key in c.properties:
                target=mapping.get(c.properties[key])
                if target: c.properties[key]=target
                else: c.properties.pop(key)
        c.reference=project.allocate_reference(c.library_id) if project else instance.reference+"."+c.reference
    junctions={}
    for w in sheet.wires:
        if group: w.group_id=group
        w.id=new_id(); w.start_x,w.start_y=point(w.start_x,w.start_y); w.end_x,w.end_y=point(w.end_x,w.end_y)
        w.points=[point(x,y) for x,y in w.points]
        for side in ("start","end"):
            cid=getattr(w,side+"_component_id")
            if cid: setattr(w,side+"_component_id",mapping[cid])
            junction=getattr(w,side+"_junction_id")
            if junction: setattr(w,side+"_junction_id",junctions.setdefault(junction,new_id()))
    for note in sheet.comments:
        note.id=new_id(); note.x,note.y=point(note.x,note.y)
        if group: note.group_id=group
    exports=[(mapping.get(port["component"]),port["pin"]) for port in payload["exports"]]
    return sheet,exports

def expand_assets(sheet, custom):
    definitions={d["id"]:d for d in custom if isinstance(d,dict) and "asset" in d}
    if not any(c.library_id in definitions for c in sheet.components): return sheet
    result=deepcopy(sheet)
    from app.libraries.built_in import get_definition,get_instance_definition
    for instance in list(result.components):
        definition=definitions.get(instance.library_id)
        if not definition: continue
        contents,exports=instantiate(definition["asset"],instance)
        instances={c.id:c for c in contents.components}
        for w in result.wires:
            for side in ("start","end"):
                if getattr(w,side+"_component_id")!=instance.id: continue
                index=getattr(w,side+"_pin_index")
                number=getattr(w,side+"_pin_number")
                if number: index=next((i for i,p in enumerate(definition["pins"]) if p["number"]==number),None)
                if index is None or index>=len(exports): raise ValueError("Invalid asset wire")
                cid,pin=exports[index]
                setattr(w,side+"_component_id",cid); setattr(w,side+"_pin_index",pin)
                if cid:
                    c=instances[cid]; spec=get_instance_definition(c,custom+definition["asset"]["custom"]).pins[pin]
                    setattr(w,side+"_pin_number",spec.number)
                    angle=radians(c.rotation); x=c.x+spec.x*cos(angle)-spec.y*sin(angle); y=c.y+spec.x*sin(angle)+spec.y*cos(angle)
                    setattr(w,side+"_x",x); setattr(w,side+"_y",y)
                    if w.points: w.points[0 if side=="start" else -1]=[x,y]
                else: setattr(w,side+"_pin_number",None)
        result.components.remove(instance); result.components.extend(contents.components)
        result.wires.extend(contents.wires); result.comments.extend(contents.comments)
        if len(result.components)>2000: raise ValueError("Expanded asset limit exceeded")
    return result

def with_asset_dependencies(custom):
    result=list(custom); seen={d["id"] for d in result}
    for definition in list(result):
        for dependency in definition.get("asset",{}).get("custom",[]):
            if dependency["id"] not in seen:
                result.append(deepcopy(dependency)); seen.add(dependency["id"])
    return result

def asset_path():
    from app.core.settings import appdata_directory
    return appdata_directory()/"assets.json"

def load_assets(path=None):
    from app.libraries.built_in import validate_custom_definition
    path=path or asset_path()
    if not path.is_file(): return []
    if path.stat().st_size>5000000: raise ValueError("Asset library too large")
    entries=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries,list) or len(entries)>200: raise ValueError("Invalid asset library")
    return [validate_custom_definition(d) for d in entries]

def save_asset(definition,path=None):
    from app.libraries.built_in import validate_custom_definition
    definition=validate_custom_definition(definition); path=path or asset_path()
    entries=load_assets(path); entries=[d for d in entries if d["id"]!=definition["id"]]+[definition]
    _write_assets(entries,path)


def remove_asset(identity,path=None):
    """Remove only the chosen reusable definition after UI confirmation."""
    path=path or asset_path()
    entries=load_assets(path)
    _write_assets([d for d in entries if d["id"]!=identity],path)


def _write_assets(entries,path):
    from PySide6.QtCore import QSaveFile, QIODevice
    if len(entries)>200: raise ValueError("Asset library limit: 200")
    raw=json.dumps(entries,ensure_ascii=False).encode("utf-8")
    if len(raw)>5000000: raise ValueError("Asset library too large")
    file=QSaveFile(str(path))
    if not file.open(QIODevice.OpenModeFlag.WriteOnly): raise OSError(file.errorString())
    if file.write(raw)!=len(raw) or not file.commit(): raise OSError(file.errorString())
