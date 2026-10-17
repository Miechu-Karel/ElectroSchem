"""Passive educational USB wiring. No enumeration or negotiated USB-PD."""
TYPES=("A","B","Mini-B","Micro-B","C","Lightning")

def socket_types(definition):
    name=definition.name
    if name.startswith("Port USB") or name=="Port Lightning": return (name.split()[-1],)
    if name=="Kostka zasilająca USB": return ("A",)
    if name=="Klawiatura USB": return ("C",)
    if "Raspberry Pi" in name and "Pico" not in name: return ("C","A")
    if "Arduino" in name: return ("B" if "Uno" in name or "Mega" in name else "Micro-B",)
    if "Pico" in name: return ("Micro-B",)
    return ()

def links(cable,side,target,definition):
    kind=cable.properties.get("sim_usb_"+side.lower()+"_type","A" if side=="A" else "C")
    if kind not in socket_types(definition): return []
    board="Arduino" in definition.name or "Raspberry Pi" in definition.name
    aliases={"VBUS":{"VBUS","POWER","5V","VBUS OUT"},"GND":{"GND","AGND"},"D−":{"D−","D-"},"D+":{"D+"}}
    result=[]
    for i,pin in enumerate(definition.pins):
        name=pin.name.split(".",1)[0]
        for signal,names in aliases.items():
            if name in names and (not board or signal in {"VBUS","GND"}): result.append((signal,i))
    return result
