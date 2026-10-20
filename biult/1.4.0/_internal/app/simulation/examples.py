"""Małe przykłady sandboxu; nie zastępują ani nie zapisują projektu użytkownika."""
from app.core.models import ComponentInstance, Sheet, Wire
from app.libraries.built_in import AVAILABLE_ITEMS
from app.canvas.routing import safe_route
from PySide6.QtCore import QPointF


def example(name):
    items = {d.name:d for d in AVAILABLE_ITEMS}
    by_id = {d.id:d for d in AVAILABLE_ITEMS}
    def c(label,x,y,ref,value="",unit="",**props):
        d=items[label]
        return ComponentInstance(d.id,x,y,reference=ref,value=value,unit=unit or d.default_unit,properties=props)
    source=c("Źródło napięcia przemiennego" if name in {"ac","meter_ac"} else "Bateria",160,240,"V1","5")
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
    elif name == "usb_c_led":
        brick=c("Kostka zasilająca USB",180,260,"USBPS1","5","V")
        port=c("Port USB C",440,240,"USBC1")
        cable=c("Kabel USB",300,340,"CABLE1",sim_usb_a_type="A",sim_usb_b_type="C",usb_a_target=brick.id,usb_b_target=port.id)
        load=c("Dioda LED 3mm",800,280,"LED1",color="red")
        resistor=c("Rezystor",660,140,"R1","330","Ω")
        pins={p.name:i for i,p in enumerate(by_id[port.library_id].pins)}
        power=next(i for label,i in pins.items() if label.startswith("VBUS"))
        ground=next(i for label,i in pins.items() if label.startswith("GND"))
        devices=[brick,port,cable,resistor,load]
        connections=[(port,power,resistor,0),(resistor,1,load,0),(load,1,port,ground)]
    elif name in {"fault_led", "fault_resistor", "fault_gpio"}:
        if name == "fault_gpio":
            board=c("Raspberry Pi 5",280,300,"PI1",sim_mode="gpio",sim_builtin_example="blink")
            source.x,source.y=750,240
            pins={p.name:i for i,p in enumerate(by_id[board.library_id].pins)}
            devices=[board,source]
            connections=[(source,0,board,pins["GPIO17"]),(source,1,board,pins["GND"])]
        else:
            resistor=c("Rezystor",440,140,"R1","47" if name=="fault_led" else "100",sim_max_power="0.25 W")
            devices=[source,resistor]
            connections=[(source,0,resistor,0)]
            if name=="fault_led":
                load=c("Dioda LED 3mm",660,240,"LED1",color="red")
                devices.append(load); connections.extend([(resistor,1,load,0),(load,1,source,1)])
            else:
                source.value="9"; connections.append((resistor,1,source,1))
    elif name == "led":
        load=c("Dioda LED 3mm",660,240,"LED1",color="red")
        resistor=c("Rezystor",440,140,"R1","330")
        switch=c("Łącznik",440,360,"SW1",sim_closed="true")
        devices=[source,resistor,load,switch]
        connections=[(source,0,resistor,0),(resistor,1,load,0),(load,1,switch,1),(switch,0,source,1)]
    elif name in {"ac","meter_ac"}:
        load=c("Żarówka",560,240,"L1","1",sim_rated_voltage="5 V")
        devices=[source,load]
        connections=[(source,0,load,0),(source,1,load,1)]
        if name=="meter_ac":
            meter=c("Oscyloskop",800,240,"OSC1"); devices.append(meter)
            connections.extend([(load,0,meter,0),(load,1,meter,1)])
    elif name=="meter_ohm":
        load=c("Żarówka",400,260,"L1","1",sim_rated_voltage="5 V")
        switch=c("Łącznik",600,260,"SW1",sim_closed="true")
        meter=c("Omomierz",400,420,"OHM1")
        devices=[load,switch,meter]; connections=[(meter,0,load,0),(load,1,switch,0),(switch,1,meter,1)]
    elif name=="pi_blink":
        board=c("Raspberry Pi 5",280,300,"PI1",sim_mode="gpio",sim_builtin_example="blink",sim_console="true")
        resistor=c("Rezystor",650,200,"R1","330")
        load=c("Dioda LED 3mm",850,300,"LED1",color="red")
        devices=[board,resistor,load]
        pin={p.name:i for i,p in enumerate(by_id[board.library_id].pins)}
        connections=[(board,pin["GPIO17"],resistor,0),(resistor,1,load,0),(load,1,board,pin["GND"])]
    else:
        source.value="9"
        resistor=c("Rezystor",420,140,"R1","1","kΩ")
        load=c("Kondensator Elektrolityczny",620,260,"C1","100","µF",voltage="6.3 V")
        devices=[source,resistor,load]
        connections=[(source,0,resistor,0),(resistor,1,load,0),(load,1,source,1)]
    # Supply contacts are above/below, avoiding an overlapping return path.
    for device in devices:
        if by_id[device.library_id].symbol in {"battery", "ac_source"}:
            device.rotation=90
    sheet=Sheet(name="Demo: "+name,components=devices,wires=[])
    for index,(a,ai,b,bi) in enumerate(connections):
        ap,bp=by_id[a.library_id].pins[ai],by_id[b.library_id].pins[bi]
        def endpoint(device,pin):
            x,y=pin.x,pin.y
            for _ in range((device.rotation//90)%4): x,y=-y,x
            return device.x+x,device.y+y
        start,end=endpoint(a,ap),endpoint(b,bp)
        route=safe_route(sheet,QPointF(*start),QPointF(*end))
        if route is None: raise ValueError("No readable route for demo: "+name)
        sheet.wires.append(Wire(*start,*end,points=[[p.x(),p.y()] for p in route],
            start_component_id=a.id,start_pin_index=ai,end_component_id=b.id,end_pin_index=bi))
    return sheet
