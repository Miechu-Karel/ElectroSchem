"""Validated, shared terminal/editor cable attachments; no filesystem or code access."""
from app.libraries.built_in import get_instance_definition
from app.simulation.jumper import GENDERS,JUMPER_IDS,CABLE_IDS
from app.simulation.usb import socket_types

def attach(sheet,cable,side,target,pin=0,custom=()):
    if side not in {'A','B'} or cable.library_id not in CABLE_IDS or target.id==cable.id: raise ValueError('Invalid cable attachment')
    d=get_instance_definition(target,custom)
    if d is None: raise ValueError('Unknown cable target')
    jumper=cable.library_id in JUMPER_IDS
    prefix=('jumper_' if jumper else 'usb_')+side.lower()+'_'
    if jumper:
        gender=GENDERS[cable.library_id][0 if side=='A' else 1]
        if d.symbol=='goldpin':
            if pin!=0 or gender==('female' if d.name=='Goldpin żeński' else 'male'): raise ValueError('Incompatible goldpin contact')
        elif d.symbol=='breadboard':
            if gender!='male' or not 0<=pin<len(d.pins): raise ValueError('Incompatible breadboard contact')
        else: raise ValueError('A jumper requires a goldpin or breadboard hole')
    else:
        kind=cable.properties.get('sim_usb_'+side.lower()+'_type','A' if side=='A' else 'C')
        if pin!=0 or kind not in socket_types(d): raise ValueError('Incompatible USB socket')
    for other in sheet.components:
        for end in ('a','b'):
            op=('jumper_' if other.library_id in JUMPER_IDS else 'usb_')+end+'_'
            if other.id==cable.id and end==side.lower(): continue
            if other.properties.get(op+'target')==target.id and other.properties.get(op+'pin','0')==str(pin):
                if jumper or other.properties.get('sim_usb_'+end+'_type','A' if end=='a' else 'C')==kind: raise ValueError('Connector is occupied')
    cable.properties[prefix+'target']=target.id; cable.properties[prefix+'pin']=str(pin)
