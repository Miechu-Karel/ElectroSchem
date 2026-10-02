"""Explicit, limited educational peripherals. No host hardware or network I/O."""
import re
from app.libraries.display_profiles import DISPLAY_PROFILES

KINDS={"joystick","ir_receiver","ir_transmitter","gpio_manual","peripheral_envelope","lcd_i2c"}


def i2c_write(previous, scl, sda, address):
    s=dict(previous); value=None
    old_clock=s.get("scl",True); old_data=s.get("sda",True)
    if scl and old_clock and old_data and not sda:
        s.update(active=True,phase="receive",bits=0,byte=0,address=True,matched=False,ack=False)
    elif scl and old_clock and not old_data and sda:
        s.update(active=False,ack=False)
    elif s.get("active"):
        phase=s["phase"]
        if scl and not old_clock:
            if phase=="receive":
                s["byte"]=(s["byte"]<<1)|int(sda); s["bits"]+=1
                if s["bits"]==8:
                    if s["address"]:
                        s["matched"]=s["byte"]==(int(address)<<1); s["address"]=False
                    elif s["matched"]: value=s["byte"]
                    s["phase"]="ack_pending"
            elif phase=="ack": s["phase"]="ack_seen"
        elif not scl and old_clock:
            if phase=="ack_pending": s.update(phase="ack",ack=s["matched"])
            elif phase=="ack_seen": s.update(phase="receive",ack=False,bits=0,byte=0)
    s.update(scl=scl,sda=sda)
    return s,value


def lcd_character(previous,byte,encoding):
    """One simulated cell per UTF-8 character, or one Windows-1250 byte."""
    if encoding=="windows-1250":
        try: return bytes([byte]).decode("cp1250")
        except UnicodeDecodeError: return "?"
    pending=previous.get("utf8_pending",b"")
    if pending:
        if not 0x80<=byte<=0xbf:
            previous.pop("utf8_pending",None)
            return "?"
        pending+=bytes([byte])
        expected=2 if pending[0]<0xe0 else 3 if pending[0]<0xf0 else 4
        if len(pending)<expected:
            previous["utf8_pending"]=pending; return None
        previous.pop("utf8_pending",None)
        try: return pending.decode("utf-8")
        except UnicodeDecodeError: return "?"
    if byte<128: return chr(byte) if byte>=32 else "?"
    if 0xc2<=byte<=0xf4:
        previous["utf8_pending"]=bytes([byte]); return None
    return "?"


def lcd_byte(previous, value, encoding="utf-8"):
    s=dict(previous); cells=list(s.get("cells"," "*32))
    s["backlight"]=bool(value&8)
    if s.get("port",0)&4 and not value&4:
        nibble=value>>4; rs=bool(value&1)
        if value&2: s["read_unsupported"]=True
        elif not s.get("four_bit"):
            if not rs and nibble==2: s["four_bit"]=True
        elif "nibble" not in s: s.update(nibble=nibble,rs=rs)
        else:
            byte=(s.pop("nibble")<<4)|nibble
            if s.pop("rs"):
                character=lcd_character(s,byte,encoding)
                if character is not None:
                    character=character if character.isprintable() else "?"
                    address=s.get("address",0)
                    index=address if address<16 else address-0x40+16 if 0x40<=address<0x50 else -1
                    if 0<=index<32: cells[index]=character
                    s["address"]=(address+s.get("direction",1))&127
            else:
                s.pop("utf8_pending",None)
                if byte in (1,2):
                    s["address"]=0
                    if byte==1: cells=list(" "*32)
                elif byte&128: s["address"]=byte&127
                elif byte&0xf8==8: s["display"]=bool(byte&4)
                elif byte&0xfc==4: s["direction"]=1 if byte&2 else -1
    s.update(port=value,cells="".join(cells))
    return s


def linearize(d, volts, ground, time, dt):
    from app.simulation.extended import Branch
    p=d.parameters; pins=p["pins"]; s=dict(d.state); branches=[]
    low=next((pins[k] for k in ("GND","VSS","GND_IN","IN−","IN-") if k in pins),ground)
    high=next((pins[k] for k in ("VCC","VDD","5V","3V3","VCC_IN","IN+","VIN") if k in pins),None)
    def voltage(n): return volts.get(n,0)-volts.get(low,0)
    def resistor(a,b,r): branches.append(Branch(a,b,1/max(.001,r)))
    def drive(pin,state,enabled=True): branches.append(Branch(pin,high if state else low,.04 if enabled else 1e-12))
    nominal=p.get("sim_nominal_voltage",5)
    supply=voltage(high) if high is not None else 0
    enabled=supply>1
    s.update(powered=enabled,supply=supply,nominal=nominal)
    if high is not None: resistor(high,low,nominal/max(1e-9,p.get("sim_load_current",.001)))
    for node in d.nodes: branches.append(Branch(node,low,1e-12))
    if d.kind=="joystick":
        for pin,key in (("VRx","sim_x"),("VRy","sim_y")):
            position=p[key]; resistor(high,pins[pin],10000*(1-position)); resistor(pins[pin],low,10000*position)
        resistor(pins["SW"],low,.001 if d.closed else 1e12)
    elif d.kind=="ir_receiver": drive(pins["SIG"],not d.closed,enabled)
    elif d.kind=="ir_transmitter":
        s["active"]=enabled and voltage(pins["DAT"])>supply*.5
        if s["active"]: resistor(high,low,220)
    elif d.kind=="gpio_manual":
        gpio=sorted(k for k in pins if re.fullmatch(r"GP[AB]?\d+",k))
        gpio.sort(key=lambda k:(k.rstrip("0123456789"),int(re.search(r"\d+",k)[0])))
        for bit,name in enumerate(gpio):
            drive(pins[name],bool(int(p["sim_gpio_mask"])&(1<<bit)),enabled and bool(int(p["sim_output_mask"])&(1<<bit)))
        s["gpio"]=sum(1<<i for i,k in enumerate(gpio) if voltage(pins[k])>supply*.5) if enabled else 0
    elif d.kind=="lcd_i2c":
        if enabled:
            bus,value=i2c_write(d.state.get("bus",{}),voltage(pins["SCL"])>supply*.5,voltage(pins["SDA"])>supply*.5,p["sim_address"])
            s["bus"]=bus
            if bus.get("ack"): resistor(pins["SDA"],low,.001)
            if value is not None: s["lcd"]=lcd_byte(d.state.get("lcd",{}),value,p.get("sim_text_encoding","utf-8"))
        else: s.update(bus={},lcd={})
    else:
        levels=tuple(voltage(node)>supply*.5 for node in d.nodes if node not in (low,high))
        old=d.state.get("levels",levels)
        s["edges"]=d.state.get("edges",0)+sum(a!=b for a,b in zip(levels,old)) if enabled else 0
        s["levels"]=levels
    return branches,s


def finish(d, trial, result, translate):
    cid=d.component.id; p=d.parameters
    profile=DISPLAY_PROFILES.get(p["name"])
    if profile:
        result.displays[cid]={"kind":profile.kind,"columns":profile.columns,
                              "rows":profile.rows,"powered":trial["powered"],
                              "protocol_model":False}
    if not trial["powered"]: text=translate("Unpowered","Brak zasilania")
    elif d.kind=="lcd_i2c":
        lcd=trial.get("lcd",{}); cells=lcd.get("cells"," "*32) if lcd.get("display",False) else " "*32
        result.displays[cid]={"kind":"lcd","cells":cells,"backlight":lcd.get("backlight",False),"powered":trial["powered"]}
        text=cells[:16]+"\n"+cells[16:]
        if lcd.get("read_unsupported"): text+="\n"+translate("LCD reads are not modelled","Odczyt LCD nie jest modelowany")
    elif d.kind=="gpio_manual": text=f"GPIO: 0x{trial['gpio']:04X}"
    elif d.kind=="peripheral_envelope":
        text=translate("Supply-only model; edges","Model samego zasilania; zbocza")+f": {trial['edges']}; "+translate("stimulus","bodziec")+f": {p['sim_stimulus']:g}"
    else: text=translate("Powered","Zasilany")
    result.readings[cid]=text
    if d.kind=="lcd_i2c" and not trial["powered"]:
        result.displays[cid]={"kind":"lcd","cells":" "*32,"backlight":False,"powered":False}
    if d.kind=="ir_transmitter": result.brightness[cid]=float(trial.get("active",False))
    if trial["supply"]>1.5*trial["nominal"] or trial["supply"]<-.5:
        result.faults[cid]=d.component.reference+": "+translate("Supply outside educational model limits","Zasilanie poza granicami modelu edukacyjnego")
