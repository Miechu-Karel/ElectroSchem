"""Małe przykłady sandboxu; nie zastępują ani nie zapisują projektu użytkownika."""
from app.core.models import ComponentInstance, Sheet, Wire
from app.libraries.built_in import AVAILABLE_ITEMS


def example(name):
    items = {d.name:d for d in AVAILABLE_ITEMS}
    by_id = {d.id:d for d in AVAILABLE_ITEMS}
    def c(label,x,y,ref,value="",unit="",**props):
        d=items[label]
        return ComponentInstance(d.id,x,y,reference=ref,value=value,unit=unit or d.default_unit,properties=props)
    source=c("Źródło napięcia przemiennego" if name=="ac" else "Bateria 9V",160,240,"V1","5")
    if name in {"rails", "transistor"}:
        source=c("Szyna Zasilania +5V",160,140,"VCC1")
        ground=c("Masa GND",660,400,"GND1")
        source.display_name="+5 V"
        ground.display_name="GND"
        resistor=c("Rezystor",360,140,"R1","330")
        load=c("Dioda LED 3mm",660,160,"LED1",color="red")
        devices=[source,ground,resistor,load]
        connections=[(source,0,resistor,0),(resistor,1,load,0)]
        if name=="transistor":
            transistor=c("Tranzystor NPN PN2222",660,300,"Q1")
            transistor.display_name="PN2222"
            base=c("Rezystor",360,300,"R2","10","kΩ")
            switch=c("Łącznik",160,300,"SW1",sim_closed="true")
            devices.extend([transistor,base,switch])
            connections.extend([(load,1,transistor,2),(transistor,0,ground,0),(source,0,switch,0),(switch,1,base,0),(base,1,transistor,1)])
        else: connections.append((load,1,ground,0))
    elif name == "led":
        load=c("Dioda LED 3mm",660,240,"LED1",color="red")
        resistor=c("Rezystor",440,140,"R1","330")
        switch=c("Łącznik",440,360,"SW1",sim_closed="true")
        devices=[source,resistor,load,switch]
        connections=[(source,0,resistor,0),(resistor,1,load,0),(load,1,switch,1),(switch,0,source,1)]
    elif name == "ac":
        load=c("Żarówka",560,240,"L1","1",sim_rated_voltage="5 V")
        devices=[source,load]
        connections=[(source,0,load,0),(source,1,load,1)]
    else:
        source.value="9"
        resistor=c("Rezystor",420,140,"R1","1","kΩ")
        load=c("Kondensator Elektrolityczny",620,260,"C1","100","µF",voltage="6.3 V")
        devices=[source,resistor,load]
        connections=[(source,0,resistor,0),(resistor,1,load,0),(load,1,source,1)]
    wires=[]
    for index,(a,ai,b,bi) in enumerate(connections):
        ap,bp=by_id[a.library_id].pins[ai],by_id[b.library_id].pins[bi]
        start,end=(a.x+ap.x,a.y+ap.y),(b.x+bp.x,b.y+bp.y)
        # Oddzielny zewnętrzny tor powrotny nie przecina symbolu źródła.
        if name in {"rails","transistor"}:
            # Prosty tor pomiędzy kolektorem/emiterem nie może nakładać się
            # na sąsiedni odcinek i sugerować wizualnego zwarcia tranzystora.
            midpoint=(start[0]+end[0])/2
            middle=[] if start[0]==end[0] or start[1]==end[1] else [[midpoint,start[1]],[midpoint,end[1]]]
        elif index==len(connections)-1:
            middle=[[start[0]+80,start[1]],[start[0]+80,440],[end[0],440]]
        else: middle=[[start[0],min(start[1],end[1])-60],[end[0],min(start[1],end[1])-60]]
        wires.append(Wire(*start,*end,points=[list(start),*middle,list(end)],
            start_component_id=a.id,start_pin_index=ai,end_component_id=b.id,end_pin_index=bi))
    return Sheet(name="Demo: "+name,components=devices,wires=wires)
