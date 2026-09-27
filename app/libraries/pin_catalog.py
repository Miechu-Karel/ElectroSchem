"""Dane katalogowe, oddzielone od Qt i algorytmu rozmieszczania symboli.

UWAGA: schemat modułu to jego wskazany wariant, nie obietnica zgodności każdego
klona o podobnej nazwie. Pole ``verified`` dotyczy sprawdzenia wyprowadzeń
w podanym źródle; brak źródła celowo pozostaje widoczny we właściwościach.
Źródła odnoszą się do pinów, nie stanowią certyfikatu zgodności symboli z normą.
"""

CATALOG: dict[str, dict] = {}


def electronic_prefix(english_name: str) -> str:
    """Pierwsze trzy znaki każdego słowa, zgodnie z regułą użytkownika.

    Znak łącznika/slasha nie jest literą nazwy, dlatego np. Wi-Fi daje WiF.
    Model i rozmiar pozostają częścią nazwy; 1N4007 wnosi 1N4. Istniejące
    reference w zapisanych projektach nie są ponownie wyliczane.
    """
    chunks = []
    for word in english_name.split():
        chunk = "".join(character for character in word if character.isalnum())[:3]
        if chunk:
            chunks.append(chunk[0].upper() + chunk[1:])
    return "".join(chunks) or "Cmp"


def add(name, en, pins="1|2", *, prefix=None, symbol="module", variant="Generic terminal arrangement — verify your device", source="", unit="", verified=False, scope="All terminals of the specified variant", **geometry):
    # s_/ic_/mc_ mają oddzielną regułę. LED pozostaje wyjątkiem wskazanym
    # przez użytkownika. Reszta elektroniki nie używa arbitralnych skrótów.
    assigned_prefix = prefix if prefix and (prefix == "LED" or prefix.startswith(("s_", "ic_", "mc_", "oth_"))) else electronic_prefix(en)
    CATALOG[name] = dict(name_en=en, pins=pins, prefix=assigned_prefix,
                         symbol=symbol, variant=variant, source=source, unit=unit,
                         verified=verified, scope=scope, **geometry)


def terminals(*values):
    """Jawne pozycje stosujemy dla symboli nieprostokątnych (np. tranzystora)."""
    return [dict(number=str(number), name=name, x=x, y=y) for number, name, x, y in values]


# Podstawowe elementy dwukońcówkowe. Nazwy/prefiksy są niezależne od języka GUI.
add("Rezystor", "Resistor", prefix="Res", symbol="resistor", unit="Ω")
add("Kondensator Ceramiczny", "Ceramic Capacitor", prefix="CerCap", symbol="capacitor", unit="F")
add("Kondensator Elektrolityczny", "Electrolytic Capacitor", "+|−", prefix="EleCap", symbol="polar_capacitor", unit="F")
add("Kondensator Tantalowy", "Tantalum Capacitor", "+|−", prefix="TanCap", symbol="polar_capacitor", unit="F")
for pl, en, prefix in [("Obrotowy", "Rotary", "RotPot"), ("Suwakowy", "Slide", "SliPot")]:
    add(f"Potencjometr {pl}", f"{en} Potentiometer", terminals((1,"1",-40,0),(3,"3",40,0),(2,"W",0,-40)), prefix=prefix, symbol="potentiometer", unit="Ω", height=80)
add("Cewka Indukcyjna", "Inductor", prefix="Ind", symbol="inductor", unit="H")
for value in ("16MHz", "8MHz"):
    add("Kwarc Rezonator " + value, "Crystal Resonator " + value, prefix="CryRes", symbol="crystal", unit="Hz")
add("Fotorezystor LDR", "Light Dependent Resistor", prefix="LigDepRes", symbol="ldr", unit="Ω", height=80)
add("Termistor NTC", "NTC Thermistor", prefix="NTCThe", symbol="thermistor", unit="Ω")
add("Enkoder Obrotowy", "Rotary Encoder", "A|C|B|SW1|SW2", prefix="RotEnc", variant="Bare incremental encoder with push switch, 5 terminals")

for pl, en, prefix, sym in [
    ("Prostownicza 1N4007","Rectifier Diode 1N4007","oth_1N4007__","diode"),
    ("Zenera","Zener Diode","ZenDio","zener"),
    ("LED 3mm","LED 3mm","LED","led"),("LED 5mm","LED 5mm","LED","led"),
    ("Schottky","Schottky Diode","SchDio","schottky")]:
    add("Dioda " + pl, en, "A|K", prefix=prefix, symbol=sym, height=80 if sym=="led" else 40)
add("Dioda RGB", "RGB LED", terminals((1,"R",-80,-40),(2,"K",80,0),(3,"G",-80,0),(4,"B",-80,40)), prefix="LED", symbol="rgb", width=160,height=120,variant="4-lead common-cathode RGB LED; verify colour pin order")
for pl, en, prefix, sym in [("NPN BC547","NPN Transistor BC547","oth_BC547__","npn"),("PNP BC557","PNP Transistor BC557","oth_BC557__","pnp")]:
    add("Tranzystor " + pl, en, terminals((1,"C",40,-20),(2,"B",-40,0),(3,"E",40,20)), prefix=prefix, symbol=sym, height=80,
        variant="onsemi TO-92, C-B-E pin order", source="https://www.onsemi.com/pdf/datasheet/bc546-d.pdf" if sym=="npn" else "https://www.onsemi.com/pdf/datasheet/bc556b-d.pdf", verified=True)
for pl,en,prefix,sym in [("N-MOSFET IRF540N","N-MOSFET IRF540N","oth_IRF540N__","nmos"),("P-MOSFET","P-MOSFET","oth_P-MOSFET__","pmos")]:
    add("Tranzystor " + pl, en, terminals((1,"G",-40,0),(2,"D",40,-20),(3,"S",40,20)), prefix=prefix, symbol=sym, height=80, variant="TO-220 G-D-S; tab connected to D" if sym=="nmos" else "Generic G-D-S; choose actual device before wiring")
add("Tranzystor NPN PN2222", "NPN Transistor PN2222",
    terminals((1,"E",40,20),(2,"B",-40,0),(3,"C",40,-20)),
    prefix="oth_PN2222__", symbol="npn", height=80,
    variant="onsemi PN2222 TO-92, pins 1 E / 2 B / 3 C",
    source="https://www.onsemi.com/download/data-sheet/pdf/pn2222-d.pdf", verified=True)
add("Tyrystor", "Thyristor", terminals((1,"A",-40,0),(2,"K",40,0),(3,"G",0,40)), symbol="thyristor", prefix="Thy",height=80)
add("Triak", "Triac", terminals((1,"MT1",-40,0),(2,"MT2",40,0),(3,"G",0,40)), symbol="triac",prefix="Tri",height=80)
add("Optoizolator PC817", "Optocoupler PC817", terminals((1,"A",-80,-20),(2,"K",-80,20),(3,"E",80,20),(4,"C",80,-20)), prefix="oth_PC817__", symbol="opto",width=160,height=120,variant="PC817 DIP-4", source="https://global.sharp/products/device/lineup/data/pdf/datasheet/pc817x_e.pdf")

# Zasilanie, symbole sieci i złącza. Szyny mają JEDEN pin, a nie pozorny
# drugi zacisk, który istniał w poprzedniej wersji programu.
for part in ("LM7805", "LM7812"):
    add("Stabilizator Liniowy " + part, "Linear Regulator " + part, "IN|GND|OUT", prefix="oth_"+part+"__", variant="TO-220, pins 1..3", source="https://www.st.com/resource/en/datasheet/l78.pdf")
add("Stabilizator AMS1117-3.3", "Linear Regulator AMS1117-3.3", "GND|OUT|IN", prefix="oth_AMS1117-3.3__", variant="SOT-223, tab = OUT", source="http://www.advanced-monolithic.com/pdf/ds1117.pdf")
for pl,en,pre in [("Bateria 9V","Battery 9V","Bat"),("Koszyk na Akumulator 18650","Battery Holder 18650","BatHol"),("Akumulator Li-Po 3.7V","Lithium Polymer Battery 3.7V","LitPolBat")]:
    add(pl,en,"+|−",prefix=pre,symbol="battery",unit="V",height=80)
for pl,en in [("Męski","Male"),("Żeński","Female")]:
    add("Złącze Goldpin "+pl,en+" Pin Header","1|2",prefix=en[:3]+"PinHea",symbol="connector",variant="1×2, 2.54 mm; use a custom element for another length")
for n in (2,3):
    add(f"Terminale Śrubowe ARK {n}-pin",f"Screw Terminal ARK {n}-pin","|".join(str(i+1) for i in range(n)),prefix="ScrTer",symbol="connector",variant=f"ARK {n}-position terminal block")
for supply in ("VCC", "+5V", "+3.3V", "+12V"):
    add("Szyna Zasilania "+supply,"Power Rail "+supply,terminals((1,supply,0,20)),prefix="PowRai",symbol="power",width=40,height=80)
add("Masa GND","Ground",terminals((1,"GND",0,-20)),prefix="Gro",symbol="ground",width=40,height=80)
add("Moduł Ładowania TP4056","TP4056 Charging Module","IN+|IN−|B+|B−|OUT+|OUT−",prefix="ChaMod",variant="Protected TP4056 module with DW01A, 6 solder terminals")
add("Przetwornik DC-DC Step-Down LM2596","LM2596 Step-Down Module","IN+|IN−|OUT+|OUT−",prefix="SteDow",variant="Adjustable 4-terminal LM2596 breakout")
add("Przetwornik DC-DC Step-Up MT3608","MT3608 Step-Up Module","IN+|IN−|OUT+|OUT−",prefix="SteUp",variant="Adjustable 4-terminal MT3608 breakout")
add("Konwerter Poziomów Logicznych","Logic Level Converter","LV|GND|LV1|LV2|LV3|LV4|HV|GND|HV1|HV2|HV3|HV4",prefix="LogLevCon",variant="4-channel bidirectional BSS138 module, 12 pins")
add("Konwerter Poziomów Logicznych Iduino ST1167", "Logic Level Converter Iduino ST1167",
    terminals(("LV", "LV/3.3V", -120, -40), ("LV.GND", "GND", -120, -20),
              ("CH1.RXO", "RXO1", -120, 0), ("CH1.TXI", "TXI1", -120, 20),
              ("CH2.RXO", "RXO2", -120, 40), ("CH2.TXI", "TXI2", -120, 60),
              ("HV", "HV/5V", 120, -40), ("HV.GND", "GND", 120, -20),
              ("CH1.RXI", "RXI1", 120, 0), ("CH1.TXO", "TXO1", 120, 20),
              ("CH2.RXI", "RXI2", 120, 40), ("CH2.TXO", "TXO2", 120, 60)),
    width=240, height=200, prefix="oth_ST1167__", show_pin_numbers=False,
    variant="Iduino ST1167: 2 UART channels; RXI→RXO HV-to-LV; TXI↔TXO bidirectional",
    source="https://cdn-reichelt.de/documents/datenblatt/A300/ST1167.pdf", verified=True,
    scope="12 terminals; signal/channel identifiers, not physical header numbering. LV/HV grounds are distinct contacts.")

# Scalony układ, a nie jego płytka breakout. Kolejność oznacza numer obudowy.
TI="https://www.ti.com/lit/ds/symlink/"
for pl,en,part,pins,package in [
    ("Układ Scalony NE555","Timer NE555","NE555","GND|TRIG|OUT|RESET|CONT|THRES|DISCH|VCC","DIP-8 / SOIC-8"),
    ("Układ Scalony LM358","Dual Op Amp LM358","LM358","OUT1|IN1−|IN1+|V−|IN2+|IN2−|OUT2|V+","DIP-8 / SOIC-8"),
    ("Bramka Logiczna 74HC00","Quad NAND 74HC00","74HC00","1A|1B|1Y|2A|2B|2Y|GND|3Y|3A|3B|4Y|4A|4B|VCC","DIP-14 / SOIC-14"),
    ("Bramka Logiczna 74HC04","Hex Inverter 74HC04","74HC04","1A|1Y|2A|2Y|3A|3Y|GND|4Y|4A|5Y|5A|6Y|6A|VCC","DIP-14 / SOIC-14"),
    ("Przerzutnik 74HC74","Dual D Flip-Flop 74HC74","74HC74","1CLR|1D|1CLK|1PRE|1Q|1/Q|GND|2/Q|2Q|2PRE|2CLK|2D|2CLR|VCC","DIP-14 / SOIC-14"),
    ("Rejestr Przesuwny 74HC595","Shift Register 74HC595","74HC595","QB|QC|QD|QE|QF|QG|QH|GND|QH′|SRCLR|SRCLK|RCLK|OE|SER|QA|VCC","DIP-16 / SOIC-16"),
    ("Przetwornik ADC ADS1115","ADC ADS1115","ADS1115","ADDR|ALERT/RDY|GND|AIN0|AIN1|AIN2|AIN3|VDD|SDA|SCL","VSSOP-10 (not a breakout module)")]:
    slug=("sn"+part if part.startswith("74") else part).lower()
    add(pl,en,pins,prefix="ic_"+part+"__",symbol="ic",variant=package,source=TI+slug+".pdf",verified=True)
# Najczęściej używane bramki 74HC. Wszystkie są pełnymi obudowami DIP-14,
# z wyprowadzeniami zasilania zachowanymi w kolejności fizycznego układu.
for pl, en, part, function in [
    ("Bramka Logiczna 74HC02", "Quad NOR 74HC02", "74HC02", "NOR"),
    ("Bramka Logiczna 74HC08", "Quad AND 74HC08", "74HC08", "AND"),
    ("Bramka Logiczna 74HC32", "Quad OR 74HC32", "74HC32", "OR"),
    ("Bramka Logiczna 74HC86", "Quad XOR 74HC86", "74HC86", "XOR"),
    ("Bramka Logiczna 74HC14", "Hex Schmitt Inverter 74HC14", "74HC14", "NOT")]:
    add(pl, en, "1A|1B|1Y|2A|2B|2Y|GND|3Y|3A|3B|4Y|4A|4B|VCC",
        prefix="ic_"+part+"__", symbol="ic", variant=f"{function} logic, DIP-14 / SOIC-14",
        source=TI+"sn"+part.lower()+".pdf", verified=True)
# Pojedyncze symbole funkcji logicznych. To osobne elementy schematowe,
# niezależne od obudów 74HC, dzięki czemu użytkownik może narysować OR/AND/NOT
# bez wstawiania prostokątnego modułu płytki.
for pl, en, kind, prefix, pins in [
    ("Bramka AND", "AND Gate", "and", "GatAND", "A|B|Y"),
    ("Bramka OR", "OR Gate", "or", "GatOR", "A|B|Y"),
    ("Bramka NOT", "NOT Gate", "not", "GatNOT", "A|Y"),
    ("Bramka NAND", "NAND Gate", "nand", "GatNAN", "A|B|Y"),
    ("Bramka NOR", "NOR Gate", "nor", "GatNOR", "A|B|Y"),
    ("Bramka XOR", "XOR Gate", "xor", "GatXOR", "A|B|Y"),
    ("Bramka XNOR", "XNOR Gate", "xnor", "GatXNO", "A|B|Y"),
]:
    gate_pins = terminals((1, "A", -20, -20), (2, "B", -20, 20), (3, "Y", 20, 0)) if pins == "A|B|Y" else terminals((1, "A", -20, 0), (2, "Y", 20, 0))
    add(pl, en, gate_pins, prefix=prefix, symbol="gate_"+kind, width=40, height=40,
        variant=f"Standard {en} schematic symbol")
add("Ekspander Portów MCP23017","I/O Expander MCP23017","GPB0|GPB1|GPB2|GPB3|GPB4|GPB5|GPB6|GPB7|VDD|VSS|NC|SCL|SDA|NC|A0|A1|A2|RESET|INTB|INTA|GPA0|GPA1|GPA2|GPA3|GPA4|GPA5|GPA6|GPA7",prefix="ic_MCP23017__",symbol="ic",variant="DIP-28 / SOIC-28",source="https://ww1.microchip.com/downloads/en/devicedoc/20001952c.pdf",verified=True)
# Dodatkowe układy z katalogu użytkownika. Pinout MCP23008 odpowiada wersji
# PDIP/SOIC z karty Microchip; nazwy są sygnałami, a nie numerami dekoracyjnymi.
add("Ekspander Portów MCP23008", "I/O Expander MCP23008",
    "SCL|SDA|A2|A1|A0|RESET|NC|INT|VSS|GP0|GP1|GP2|GP3|GP4|GP5|GP6|GP7|VDD",
    prefix="ic_MCP23008__", symbol="ic", variant="PDIP-18 / SOIC-18",
    source="https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23008-and-MCP23S08-Data-Sheet-DS20001919.pdf", verified=True)
add("Układ Logiczny CD4093BE", "Quad NAND Schmitt Trigger CD4093BE",
    "1A|1B|1Y|2A|2B|2Y|GND|3Y|3A|3B|4Y|4A|4B|VDD",
    prefix="ic_CD4093BE__", symbol="ic", variant="TI PDIP-14",
    source="https://www.ti.com/lit/ds/symlink/cd4093b.pdf", verified=True)
add("MCP2008", "LIN Transceiver MCP2008",
    "VBB|LIN|VSS|RXD|TXD|CS|WAKE|NC", prefix="ic_MCP2008__", symbol="ic",
    variant="Generic 8-pin LIN transceiver arrangement; verify exact manufacturer",
    verified=False)
# Dawny wpis miał niepotwierdzoną funkcję i pinout. Zachowujemy geometrię
# dla istniejących ELS, ale jawnie oznaczamy brak identyfikacji urządzenia.
CATALOG["MCP2008"].update(display_name="Układ MCP2008 (niezweryfikowany)",
                         name_en="MCP2008 IC (unverified)",
                         variant="Unidentified part; legacy pin layout is unverified. Supply the exact datasheet before use.")
add("Przetwornik ADC MCP3008", "ADC MCP3008",
    "CH0|CH1|CH2|CH3|CH4|CH5|CH6|CH7|DGND|CS/SHDN|DIN|DOUT|CLK|AGND|VREF|VDD",
    prefix="ic_MCP3008__", symbol="ic", variant="10-bit, 8-channel SPI ADC; PDIP-16",
    source="https://ww1.microchip.com/downloads/en/DeviceDoc/21295d.pdf", verified=True)
add("Potencjometr Cyfrowy MCP41010","Digital Potentiometer MCP41010","CS|SCK|SI|VSS|PB0|PW0|PA0|VDD",prefix="ic_MCP41010__",symbol="ic",variant="DIP-8 / SOIC-8",source="https://ww1.microchip.com/downloads/en/DeviceDoc/11195c.pdf",verified=True,unit="Ω")
add("Generator Sygnałowy XR2206","Function Generator XR2206","AMSI|STO|MO|VCC|TC1|TC2|TR1|TR2|FSKI|BIAS|SYNCO|GND|WAVE1|WAVE2|SYMA1|SYMA2",prefix="ic_XR2206__",symbol="ic",variant="DIP-16 (bare IC)",source="https://www.maxlinear.com/ds/xr2206.pdf")
add("Mostek H L298N","Dual H Bridge L298N","SENSE_A|OUT1|OUT2|VS|IN1|ENA|IN2|GND|VSS|IN3|ENB|IN4|OUT3|OUT4|SENSE_B",prefix="ic_L298N__",symbol="ic",variant="Multiwatt15 (bare IC, not red driver module)",source="https://www.st.com/resource/en/datasheet/l298.pdf")
add("Sterownik Silników Krokowych A4988","Stepper Driver A4988","ENABLE|MS1|MS2|MS3|RESET|SLEEP|STEP|DIR|GND|VDD|1B|1A|2A|2B|GND|VMOT",prefix="ic_A4988__",symbol="module",variant="Pololu-compatible A4988 carrier, 2×8 header",source="https://www.pololu.com/product/1182")
# Numery złączy przepisane ze schematu v1.2, nie wymyślona numeracja 1..16.
# JP1.5/JP1.4 łączą UART przez dwa alternatywne mostki J2, JP1.3 CLK przez J1.
tmc_pins = [dict(number=f"JP1.{8-i}", name=name) for i, name in enumerate("EN|MS1|MS2|UART/J2.3|UART/J2.1|CLK/J1|STEP|DIR".split("|"))]
tmc_pins += [dict(number=f"JP2.{8-i}", name=name) for i, name in enumerate("GND|VIO|OB2|OB1|OA1|OA2|GND|VM".split("|"))]
add("Sterownik Silników Krokowych TMC2208","Stepper Driver TMC2208",tmc_pins,prefix="ic_TMC2208__",variant="Watterott SilentStepStick TMC2208 v1.2; UART/CLK contacts depend on solder bridges",source="https://github.com/watterott/SilentStepStick/blob/master/hardware/SilentStepStick-TMC2208_v12.pdf",verified=True,scope="16 main JP1/JP2 contacts; JP3/JP4/JP5 DIAG/INDEX/VREF test pads excluded")

# Moduły: nazwy pinów opisują sygnał, a nie dekoracyjne kreski.
add("Przycisk Tact Switch","Tactile Switch",terminals((1,"1",-40,0),(2,"2",40,0),(3,"1′",-40,20),(4,"2′",40,20)),prefix="TacSwi",symbol="switch",height=80,variant="4-leg normally-open switch; 1=3 and 2=4 internally")
for pl,en in [("Suwakowy","Slide"),("Dźwigniowy","Toggle")]:
    add("Przełącznik "+pl,en+" Switch",terminals((1,"A",40,-20),(2,"COM",-40,0),(3,"B",40,20)),prefix=en[:3]+"Swi",symbol="spdt",height=80,variant="SPDT, 3 terminals")
add("Przekaźnik Elektromechaniczny 5V","Electromechanical Relay 5V",terminals((1,"COIL+",-100,-20),(2,"COIL−",-100,20),(3,"COM",100,40),(4,"NC",100,-40),(5,"NO",100,0)),prefix="EleRel",symbol="relay",width=200,height=160,variant="Generic SPDT relay, 5 terminals; check package numbering")
add("Buzzer Piezoelektryczny Aktywny","Active Piezo Buzzer","+|−",prefix="ActPieBuz",symbol="buzzer")
add("Buzzer Pasywny","Passive Buzzer","+|−",prefix="PasBuz",symbol="buzzer")
add("Moduł Przekaźnika 1-kanałowy z optoizolacją 5V", "Optoisolated 1-channel Relay Module 5V",
    terminals(("VCC", "VCC/5V", -100, -20), ("GND", "GND", -100, 0), ("IN", "IN", -100, 20),
              ("NO", "NO", 100, -20), ("COM", "COM", 100, 0), ("NC", "NC", 100, 20)),
    width=200, height=120, variant="Botland MOD-01997; active-low input; optoisolated relay module",
    source="https://botland.com.pl/przekazniki-przekazniki-arduino/1997-modul-przekaznika-1-kanal-z-optoizolacja-styki-10a-250vac-cewka-5v-5904422359096.html",
    scope="Six named external terminals; identifiers follow board labels, not physical numbering")
add("Serwomechanizm EF90D 360° (praca ciągła)", "EF90D Continuous Rotation Servo 360°",
    terminals(("GND", "GND", -80, 20), ("VCC", "VCC", -80, -20), ("PWM", "PWM", -80, 0)),
    symbol="motor", width=160, height=120,
    variant="ELECFREAKS EF90D / EF09083, continuous rotation with wheel; PWM controls speed and direction, not angle",
    source="https://shop.elecfreaks.com/products/elecfreaks-360-digital-servo-with-wheel-and-tire-ef90d",
    scope="Three servo leads identified by signal; verify connector orientation")
add("Nadajnik Podczerwieni", "Infrared Transmitter", "A|K", prefix="oth_IR-TX__", symbol="led",
    variant="Generic 940 nm IR LED; verify polarity and current", verified=False)
add("Czujnik Podczerwieni", "Infrared Receiver", "VCC|GND|OUT", prefix="s_IR-RX__", symbol="module",
    variant="Generic 3-pin demodulating IR receiver module; exact frequency varies", verified=False)
add("Moduł Zasilania Stykowej","Breadboard Power Supply","VCC_L|GND_L|VCC_R|GND_R|5V|GND|3V3|GND",prefix="BrePowSup",variant="MB102-style, breadboard outputs plus 2×2 power header; variant-dependent")
add("Czujnik Dźwięku Iduino ST1146", "Iduino ST1146 Microphone Sound Sensor", "VCC|GND|OUT",
    prefix="s_ST1146__", variant="Iduino ST1146 microphone module; analog output, exact revision may vary",
    source="https://botland.com.pl/mikrofony-i-detektory-dzwieku/14287-czujnik-dzwieku-mikrofon-iduino-st1146-5903351242004.html")
add("Waveshare E-Paper Shield 2.13", "Waveshare E-Paper HAT 2.13 250x122",
    "VCC|GND|DIN/MOSI|CLK/SCK|CS|DC|RST|BUSY", prefix="EpaHat", variant="Raspberry Pi 40-pin HAT, SPI control header",
    source="https://botland.com.pl/raspberry-pi-hat-klawiatury-i-wyswietlacze/9097-e-paper-shield-213-250x122px-nakladka-z-wyswietlaczem-dla-raspberry-pi-4b3b3b-v21-waveshare-12915-5903351245074.html")
add("Wyświetlacz OLED 0.96 I2C 128x64","OLED 0.96 I2C 128×64","GND|VCC|SCL|SDA",prefix="OLEDis",variant="SSD1306 4-pin I2C module; VCC/GND order varies on clones")
add("Wyświetlacz LCD 16x2 I2C","LCD 16×2 I2C","GND|VCC|SDA|SCL",prefix="LCDDis",variant="HD44780 with PCF8574 backpack, 4 external pins")
add("Wyświetlacz LCD 16x2 I2C LCM1602", "LCD 16×2 I2C LCM1602", "GND|VCC|SDA|SCL", prefix="LCDLCM",
    variant="Blue HD44780-compatible display with LCM1602 I2C backpack",
    source="https://botland.com.pl/wyswietlacze-alfanumeryczne-i-graficzne/2351-wyswietlacz-lcd-2x16-znakow-niebieski-konwerter-i2c-lcm1602-5904422309244.html")
add("Wyświetlacz TFT 1.8 SPI","TFT 1.8 SPI","GND|VCC|SCK|SDA/MOSI|RESET|DC|CS|LED",prefix="TFTDis",variant="ST7735 8-pin display header; SD connector not included")
add("Matryca LED 8x8 MAX7219","LED Matrix 8×8 MAX7219","VCC_IN|GND_IN|DIN|CS_IN|CLK_IN|VCC_OUT|GND_OUT|DOUT|CS_OUT|CLK_OUT",prefix="LEDMat",variant="MAX7219 matrix module with 5-pin input and output headers")
add("Moduł Przekaźnika 1-kanałowy","Single Relay Module","VCC|GND|IN|COM|NC|NO",prefix="RelMod",variant="3-pin control + 3 screw terminals, no separate JD-VCC")
add("Moduł Przekaźnika 4-kanałowy","Four Relay Module","VCC|GND|IN1|IN2|IN3|IN4|JD-VCC|COM1|NC1|NO1|COM2|NC2|NO2|COM3|NC3|NO3|COM4|NC4|NO4",prefix="RelMod",variant="4-channel optoisolated board; 6-pin input + JD-VCC + 12 relay terminals")
add("Moduł Bluetooth HC-05","Bluetooth Module HC-05","EN|VCC|GND|TXD|RXD|STATE",prefix="BluMod",variant="ZS-040 6-pin carrier, not bare 34-pad HC-05 radio")
add("Moduł Wi-Fi ESP8266 ESP-01","Wi-Fi Module ESP8266 ESP-01","GND|TXD|GPIO2|EN|GPIO0|RST|RXD|VCC",prefix="WiFMod",variant="ESP-01 2×4 header; logical order, check orientation",source="https://docs.ai-thinker.com/en/esp8266")
add("Klawiatura Membranowa 4x4","Membrane Keypad 4×4","R1|R2|R3|R4|C1|C2|C3|C4",prefix="MemKey",variant="8-wire row/column matrix; tail order varies")
add("Czytnik Kart SD","SD Card Reader","GND|VCC|MISO|MOSI|SCK|CS",prefix="SDCarRea",variant="6-pin SPI microSD carrier")
add("Zegar Czasu Rzeczywistego RTC DS3231","RTC DS3231 Module","32K|SQW|SCL|SDA|VCC|GND",prefix="RTC",variant="ZS-042 6-pin main header; duplicate 4-pin header not modelled")
add("Moduł RFID RC522","RFID Module RC522","SDA/SS|SCK|MOSI|MISO|IRQ|GND|RST|3V3",prefix="RFIMod",variant="MFRC522 8-pin SPI carrier")

for pl,en,part,pins,variant in [
    ("Czujnik Odległości HC-SR04","Distance Sensor HC-SR04","HC-SR04","VCC/5V|TRIG|ECHO|GND","HC-SR04 4-pin module"),
    ("Czujnik Ruchu PIR HC-SR501","PIR Motion Sensor HC-SR501","HC-SR501","VCC|OUT|GND","HC-SR501 3-pin module"),
    ("Czujnik Temperatury DHT11","Temperature/Humidity Sensor DHT11","DHT11","VCC|DATA|NC|GND","Bare 4-pin sensor, front view; not 3-pin breakout"),
    ("Czujnik Temperatury DHT22","Temperature/Humidity Sensor DHT22","DHT22","VCC|DATA|NC|GND","AM2302/DHT22 bare 4-pin sensor"),
    ("Czujnik Temperatury DS18B20","Temperature Sensor DS18B20","DS18B20","GND|DQ|VDD","TO-92, flat front view; cable colours are not pin numbers"),
    ("Czujnik Natężenia Światła BH1750","Light Sensor BH1750","BH1750","VCC|GND|SCL|SDA|ADDR","GY-302 5-pin module"),
    ("Czujnik Wilgotności Gleby","Soil Moisture Sensor","SoilMoisture","VCC|GND|DO|AO","FC-28/YL-69 comparator module, 4-pin host interface"),
    ("Czujnik Gazu MQ-2","Gas Sensor MQ-2","MQ-2","VCC|GND|DO|AO","4-pin MQ-2 breakout, not bare six-pin sensor"),
    ("Czujnik Jakości Powietrza BME280","Temperature/Humidity/Pressure Sensor BME280","BME280","VCC|GND|SCL|SDA|CSB|SDO","6-pin I2C/SPI breakout; BME280 does not measure gas quality"),
    ("Akcelerometr MPU6050","Accelerometer/Gyroscope MPU6050","MPU6050","VCC|GND|SCL|SDA|XDA|XCL|AD0|INT","GY-521 8-pin breakout"),
    ("Moduł GPS NEO-6M","GPS Module NEO-6M","NEO-6M","VCC|RX|TX|GND","GY-GPS6MV2 4-pin UART carrier"),
    ("Czujnik Płomienia","Flame Sensor","Flame","VCC|GND|DO|AO","4-pin LM393 flame detector carrier"),
    ("Czujnik Dźwięku MAX9814","Microphone Amplifier MAX9814","MAX9814","VDD|GND|OUT|GAIN|AR","5-pin auto-gain microphone breakout")]:
    add(pl,en,pins,prefix="s_"+part+"__",variant=variant)

# Weryfikacja dotyczy konkretnej obudowy, nie dowolnego modułu z tym układem.
CATALOG["Czujnik Temperatury DS18B20"].update(
    source="https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf",
    verified=True,
)

# Płytki: wyprowadzamy złącza użytkownika, nie wewnętrzne wyprowadzenia SoC.
def board(name,pins,variant,source="",verified=False,scope="Main user expansion headers; USB/HDMI/camera sockets are not individual schematic pins"):
    add(name,name,pins,prefix="mc_"+name+"___",variant=variant,source=source,verified=verified,scope=scope)


ARDUINO="https://docs.arduino.cc/resources/pinouts/"
def header(connector, names):
    return [dict(number=f"{connector}.{i+1}",name=name) for i,name in enumerate(names.split("|"))]


uno = header("POWER","NC|IOREF|RESET|3V3|5V|GND|GND|VIN") + header("ANALOG","A0|A1|A2|A3|A4/SDA|A5/SCL") + header("DIGITAL","D0/RX|D1/TX|D2|D3|D4|D5|D6|D7|D8|D9|D10/SS|D11/MOSI|D12/MISO|D13/SCK|GND|AREF|SDA|SCL") + header("ICSP","MISO|5V|SCK|MOSI|RESET|GND")
board("Arduino Uno R3",uno,"UNO Rev3, expansion and ATmega328P ICSP headers",ARDUINO+"A000066-full-pinout.pdf",True)
board("Arduino Leonardo",header("POWER","NC|IOREF|RESET|3V3|5V|GND|GND|VIN")+header("ANALOG","A0|A1|A2|A3|A4|A5")+header("DIGITAL","D0/RX|D1/TX|D2/SDA|D3/SCL|D4|D5|D6|D7|D8|D9|D10|D11|D12|D13|GND|AREF|SDA|SCL")+header("ICSP","MISO|5V|SCK|MOSI|RESET|GND"),"Leonardo, expansion and ICSP headers",ARDUINO+"A000057-full-pinout.pdf")
board("Arduino Nano","D1/TX|D0/RX|RESET|GND|D2|D3|D4|D5|D6|D7|D8|D9|D10|D11/MOSI|D12/MISO|D13/SCK|3V3|AREF|A0|A1|A2|A3|A4/SDA|A5/SCL|A6|A7|5V|RESET|GND|VIN","Classic Nano, 30 main header contacts",ARDUINO+"A000005-full-pinout.pdf")
mega=header("POWER","NC|IOREF|RESET|3V3|5V|GND|GND|VIN")+header("ANALOG","|".join("A"+str(i) for i in range(16)))+header("DIGITAL","|".join("D"+str(i) for i in range(54)))+header("AUX","5V|5V|GND|GND|AREF|GND|SDA|SCL")+header("ICSP","MISO|5V|SCK|MOSI|RESET|GND")
board("Arduino Mega 2560",mega,"Mega 2560 Rev3, expansion and main ICSP headers",ARDUINO+"A000067-full-pinout.pdf",True)
pico="GP0|GP1|GND|GP2|GP3|GP4|GP5|GND|GP6|GP7|GP8|GP9|GND|GP10|GP11|GP12|GP13|GND|GP14|GP15|GP16|GP17|GND|GP18|GP19|GP20|GP21|GND|GP22|RUN|GP26/ADC0|GP27/ADC1|AGND|GP28/ADC2|ADC_VREF|3V3_OUT|3V3_EN|GND|VSYS|VBUS"
for name in ("Raspberry Pi Pico","Raspberry Pi Pico W"):
    board(name,pico,"40-pin main header", "https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf",True,scope="All 40 main header contacts; SWD test connector excluded")
rpi="3V3|5V|GPIO2/SDA1|5V|GPIO3/SCL1|GND|GPIO4|GPIO14/TXD|GND|GPIO15/RXD|GPIO17|GPIO18|GPIO27|GND|GPIO22|GPIO23|3V3|GPIO24|GPIO10/MOSI|GND|GPIO9/MISO|GPIO25|GPIO11/SCLK|GPIO8/CE0|GND|GPIO7/CE1|GPIO0/ID_SD|GPIO1/ID_SC|GPIO5|GND|GPIO6|GPIO12|GPIO13|GND|GPIO19|GPIO16|GPIO26|GPIO20|GND|GPIO21"
for name in ("Raspberry Pi Zero 2 W","Raspberry Pi 4 Model B","Raspberry Pi 5"):
    board(name,rpi,"40-pin GPIO expansion header", "https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio-and-the-40-pin-header",True)
board("ESP32 DevKitC",header("J2","3V3|EN|GPIO36/VP|GPIO39/VN|GPIO34|GPIO35|GPIO32|GPIO33|GPIO25|GPIO26|GPIO27|GPIO14|GPIO12|GND|GPIO13|GPIO9/D2|GPIO10/D3|GPIO11/CMD|5V")+header("J3","GND|GPIO23|GPIO22|GPIO1/TX|GPIO3/RX|GPIO21|GND|GPIO19|GPIO18|GPIO5|GPIO17|GPIO16|GPIO4|GPIO0|GPIO2|GPIO15|GPIO8/D1|GPIO7/D0|GPIO6/CLK"),"Espressif ESP32-DevKitC V4 / WROOM, 38 contacts", "https://documentation.espressif.com/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html",True)
board("ESP32-S3 NodeMCU",header("J1","3V3|3V3|EN|GPIO4|GPIO5|GPIO6|GPIO7|GPIO15|GPIO16|GPIO17|GPIO18|GPIO8|GPIO3|GPIO46|GPIO9|GPIO10|GPIO11|GPIO12|GPIO13|GPIO14|5V|GND")+header("J3","GND|GPIO43/TX|GPIO44/RX|GPIO1|GPIO2|GPIO42|GPIO41|GPIO40|GPIO39|GPIO38|GPIO37|GPIO36|GPIO35|GPIO0|GPIO45|GPIO48|GPIO47|GPIO21|GPIO20|GPIO19|GND|GND"),"ESP32-S3-DevKitC-1 compatible 44-pin variant; NodeMCU clones may differ", "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide.html")
board("Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)","D0/GPIO1|D1/GPIO2|D2/GPIO3|D3/GPIO4|D4/SDA/GPIO5|D5/SCL/GPIO6|D6/TX/GPIO43|D7/RX/GPIO44|D8/SCK/GPIO7|D9/MISO/GPIO8|D10/MOSI/GPIO9|3V3|GND|5V","XIAO ESP32-S3 Sense, 14 castellated main edge contacts", "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/",True,scope="14 main edge contacts; battery pads and camera expansion connector excluded")
# Oba rzędy liczymy oddzielnie, od strony gniazda USB. Teensy ma 48
# otworów bocznych, NIE 49; nazwy L/R są identyfikatorami graficznego złącza,
# nie numerami wyprowadzeń układu i.MXRT.
board("Teensy 4.1",header("L","GND|D0/RX1|D1/TX1|D2|D3|D4|D5|D6|D7/RX2|D8/TX2|D9|D10/CS|D11/MOSI|D12/MISO|3V3|D24|D25|D26|D27|D28|D29|D30|D31|D32")+header("R","VIN|GND|3V3|D23/A9|D22/A8|D21/A7|D20/A6|D19/A5/SCL|D18/A4/SDA|D17/A3|D16/A2|D15/A1|D14/A0|D13/SCK|GND|D41|D40|D39|D38|D37|D36|D35|D34|D33"),"Teensy 4.1, 48 main side contacts, L/R counted from USB end", "https://www.pjrc.com/teensy/card11a_rev3_web.pdf",True,scope="All 48 main side contacts; Ethernet/USB host/debug/underside memory pads excluded")
# 25 fizycznych pasków, a nie 21 unikatowych sygnałów: 3V/GND mają też
# po dwa paski ochronne. Powtórzone zasilanie musi dać się osobno podłączyć.
board("Microbit V2","P3|P0|P4|P5|P6|P7|P1|P8|P9|P10|P11|P12|P2|P13/SCK|P14/MISO|P15/MOSI|P16|3V|3V|3V|P19/SCL|P20/SDA|GND|GND|GND","micro:bit V2, 25 edge-connector strips from left to right (front view)", "https://tech.microbit.org/hardware/edgeconnector/",True,scope="25 front strips including five large rings and 3V/GND guard strips; unconnected rear strips excluded")

# SBC-producenci stosują różne mapowania mimo mechanicznie podobnych złączy.
# Etykiety są nazwami banków SoC danego producenta, NIE numerami BCM Raspberry Pi.
board("Banana Pi M5","3V3|5V|GPIOX_17/SDA|5V|GPIOX_18/SCL|GND|GPIOX_5|GPIOX_12/TX|GND|GPIOX_13/RX|GPIOX_3|GPIOAO_8|GPIOX_4|GND|GPIOX_7|GPIOX_0|3V3|GPIOX_1|GPIOX_8|GND|GPIOX_9|GPIOX_2|GPIOX_11|GPIOX_10|GND|GPIOX_16|GPIOA_14/SDA|GPIOA_15/SCL|GPIOX_14/CTS|GND|GPIOX_15/RTS|GPIOX_19|GPIOX_6|GND|GPIOAO_7|GPIOH_5|GPIOAO_9|GPIOAO_10|GND|GPIOAO_4","Banana Pi BPI-M5, 40-pin expansion header", "https://wiki.banana-pi.org/Banana_Pi_BPI-M5#GPIO_PIN_define",True)
board("Orange Pi 3 LTS","3V3|5V|PD26/SDA|5V|PD25/SCL|GND|PD22/PWM0|PL2|GND|PL3|PD24/UART3_RX|PD18|PD23/UART3_TX|GND|PL10|PD15|3V3|PD16|PH5/MOSI|GND|PH6/MISO|PD21|PH4/SCLK|PH3/CS|GND|PL8","Orange Pi 3 LTS, 26-pin header, user manual v2.1 section 3.17", "https://orangepi.vn/wp-content/uploads/2022/07/OrangePi_3_LTS_H6_User-Manul_v2.1.pdf",True)

# Morpho obejmuje wszystkie kontakty CN7 i CN10, także NC i powtórzone masy.
cn7="PC10|PC11|PC12|PD2|VDD|E5V|BOOT0|GND|NC|NC|NC|IOREF|PA13|RESET|PA14|3V3|PA15|5V|GND|GND|PB7|GND|PC13|VIN|PC14|NC|PC15|PA0|PH0|PA1|PH1|PA4|VBAT|PB0|PC2|PC1|PC3|PC0"
cn10="PC9|PC8|PB8|PC6|PB9|PC5|AVDD|U5V|GND|NC|PA5|PA12|PA6|PA11|PA7|PB12|PB6|NC|PC7|GND|PA9|PB2|PA8|PB1|PB10|PB15|PB4|PB14|PB5|PB13|PB3|AGND|PA10|PC4|PA2|NC|PA3|NC"
board("STM32 Nucleo-F401RE",header("CN7",cn7)+header("CN10",cn10),"NUCLEO-F401RE MB1136, CN7/CN10 Morpho headers", "https://www.st.com/resource/en/user_manual/um1724-stm32-nucleo64-boards-mb1136-stmicroelectronics.pdf",scope="76 Morpho contacts; Arduino-compatible duplicate headers and ST-LINK connector excluded")

add("Silnik Krokowy NEMA 17","Stepper Motor NEMA 17",terminals((1,"A+",-80,-20),(2,"A−",-80,20),(3,"B+",80,-20),(4,"B−",80,20)),prefix="SteMot",symbol="motor",width=160,height=120,variant="4-wire bipolar motor; NEMA17 specifies mounting size, not wiring colours")
for model in ("SG90","MG996R"):
    add("Serwomechanizm "+model,"Servo "+model,terminals((1,"GND",-80,20),(2,"VCC",-80,-20),(3,"PWM",-80,0)),prefix="Ser",symbol="motor",width=160,height=120,variant="3-wire hobby servo; verify supply rating for exact model")

# Nazwa biblioteczna po polsku jest historycznym kluczem ELS; jej nie
# zmieniamy. Angielski interfejs i nowe ID nie mogą jednak zawierać polskiego
# dopisku, który wcześniej został przypadkowo skopiowany z tego klucza.
xiao = CATALOG["Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)"]
xiao["name_en"] = "Seeed Studio XIAO ESP32-S3 Sense (OV3660 camera)"
xiao["prefix"] = "mc_" + xiao["name_en"] + "___"
