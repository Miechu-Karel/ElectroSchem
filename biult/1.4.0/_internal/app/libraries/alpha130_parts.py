"""1.3 catalogue additions. Generic models are not physical pinout promises."""
def install(add, terminals):
    parts = []
    def part(category, name, en, pins, **kwargs):
        add(name, en, pins, **kwargs)
        parts.append((category, name))
    power = "Zasilanie i połączenia"
    for suffix, pins in (("A", "VBUS|D−|D+|GND|SHIELD"), ("B", "VBUS|D−|D+|GND|SHIELD"),
                         ("Mini-B", "VBUS|D−|D+|ID|GND|SHIELD"), ("Micro-B", "VBUS|D−|D+|ID|GND|SHIELD")):
        part(power, "Port USB " + suffix, "USB " + suffix + " Port", pins, symbol="connector", height=160,
             variant="USB 2.0 semantic contacts and shell; no USB host, enumeration or data protocol")
    part(power, "Port USB C", "USB C Port", "GND.A1|TX1+|TX1−|VBUS.A4|CC1|D+.A6|D−.A7|SBU1|VBUS.A9|RX2−|RX2+|GND.A12|GND.B1|TX2+|TX2−|VBUS.B4|CC2|D+.B6|D−.B7|SBU2|VBUS.B9|RX1−|RX1+|GND.B12|SHIELD",
         symbol="connector", variant="Full USB-C semantic contacts; no PD negotiation or internal contacts assumed")
    part(power, "Port Lightning", "Lightning Port", "GND|L0+|L0−|ID0|POWER|L1−|L1+|ID1|SHIELD", symbol="connector",
         variant="Educational semantic connector; orientation switching and authentication are not emulated")
    part(power, "Prostownik AC/DC", "AC/DC Bridge Rectifier", "AC+|AC-|DC+|DC-",
         variant="Generic four-diode bridge; add an external filter capacitor")
    part(power, "Przetwornica DC/AC", "DC/AC Inverter", "DC+|DC-|AC+|AC-",
         variant="Non-isolated educational sine inverter; not a mains wiring diagram")
    for name, en in (("Przetwornica DC-DC Step-Up", "DC-DC Step-Up Converter"),
                     ("Przetwornica DC-DC Step-Down", "DC-DC Step-Down Converter"),
                     ("Przetwornica DC-DC Step-Up/Step-Down", "DC-DC Buck-Boost Converter")):
        part(power, name, en, "IN+|IN−|OUT+|OUT−", variant="Generic averaged non-isolated DC converter")
    for name, en in (("Stabilizator regulowany DC", "Adjustable DC Regulator"),
                     ("Stabilizator Liniowy 9V", "9V Linear Regulator")):
        part(power, name, en, "IN|GND|OUT", variant="Generic educational three-terminal regulator")
    part(power, "Panel słoneczny", "Solar Panel", terminals((1,"+",-40,0),(2,"−",40,0)), symbol="battery",
         variant="Illumination-scaled ideal DC source with a configurable current limit; no photovoltaic IV-curve")
    ic = "Układy i sterowniki"
    part(ic, "Przetwornik DAC 8-bit", "8-bit Parallel DAC", "D0|D1|D2|D3|D4|D5|D6|D7|VREF|OUT|GND|VCC", symbol="ic",
         variant="Generic parallel 8-bit DAC, straight binary; not a specific package")
    for bits in (10, 12):
        part(ic, f"Przetwornik DAC {bits}-bit", f"{bits}-bit Parallel DAC", "|".join([*(f"D{i}" for i in range(bits)), "VREF", "OUT", "GND", "VCC"]), symbol="ic",
             variant=f"Generic parallel {bits}-bit DAC, straight binary; not a specific package")
    part(ic, "Komparator LM393", "LM393 Dual Comparator", "1OUT|1IN−|1IN+|GND|2IN+|2IN−|2OUT|VCC", symbol="ic", prefix="ic_LM393__",
         source="https://www.ti.com/lit/ds/symlink/lm393.pdf", verified=True, variant="PDIP-8 / SOIC-8; dual open-collector comparator")
    part(ic, "Wzmacniacz LM324", "LM324 Quad Op Amp", "1OUT|1IN−|1IN+|VCC|2IN+|2IN−|2OUT|3OUT|3IN−|3IN+|GND|4IN+|4IN−|4OUT", symbol="ic", prefix="ic_LM324__",
         source="https://www.ti.com/lit/ds/symlink/lm324.pdf", verified=True, variant="PDIP-14 / SOIC-14; four amplifiers, GND labels VCC−")
    part(ic, "Przełącznik analogowy CD4066", "CD4066 Quad Analog Switch", "A1|A2|B2|B1|EN.B|EN.C|VSS|C1|C2|D2|D1|EN.D|EN.A|VDD", symbol="ic", prefix="ic_CD4066__",
         source="https://www.ti.com/lit/ds/symlink/cd4066b.pdf", verified=True, variant="PDIP-14 / SOIC-14; four independent bilateral switches")
    part("Czujniki", "Grove LSM6DS3 105020012", "Grove 6-Axis Accelerometer and Gyroscope LSM6DS3 105020012", "SCL|SDA|VCC|GND", prefix="s_LSM6DS3__",
         source="https://wiki.seeedstudio.com/Grove-6-Axis_AccelerometerAndGyroscope/",
         variant="Grove I2C connector; 3.3/5 V module supply; register/motion model to be defined")
    part("Elementy interaktywne", "Karta RFID", "RFID Card", [], symbol="interactive_card", width=200, height=120,
         library_id="moduły-i-interfejsy-karta-rfid",
         variant="Passive RF card, no wired terminals; drag near RC522 to present its configured ID")
    part("Elementy interaktywne", "Zapałka", "Match", [], symbol="match", width=120, height=40,
         variant="Interactive simulation prop; click to light or extinguish, then drag near a flame sensor")
    part("Elementy interaktywne", "Cel ultradźwiękowy", "Ultrasonic target", [], symbol="ultrasonic_target", width=120, height=80,
         prefix="Tgt", variant="Movable reflector for HC-SR04 simulation; scene distance is mapped to 1 m per 100 scene units")
    part("Elementy interaktywne", "Osoba", "Person", [], symbol="motion_target", width=80, height=120,
         prefix="Psn", variant="Movable PIR stimulus; presence within the sensor area sets its simulated output active")
    part("Elementy interaktywne", "Pilot IR", "IR remote control", [], symbol="ir_remote", width=80, height=160,
         prefix="Rem", variant="Click near an IR receiver to emit a short active-low stimulus; no carrier or remote protocol is emulated")
    return parts
