"""Pin explanations, scoped by device before interpreting shared signal names.

74HC04/14/74/595 mappings follow the TI datasheets linked by pin_catalog.
Unknown signals stay explicitly undocumented rather than acquiring guessed roles.
"""
import re


def pin_explanation(definition, pin, language="en"):
    pl=language=="pl"
    def t(en,polish): return polish if pl else en
    name,symbol,label=definition.name,definition.symbol,pin.name
    if label in {"GND","VSS"}:
        return t("Ground: supply return and signal reference.","Masa: powrót zasilania i punkt odniesienia sygnałów.")
    if label in {"VCC","VDD","3V3","3.3V","5V"}:
        if symbol=="ic":
            return t("Positive supply input, shared by the internal circuits. Use the voltage range specified in the datasheet.","Dodatnie wejście zasilania, wspólne dla obwodów wewnętrznych. Stosuj zakres napięcia podany w dokumentacji.")
        return t("Supply rail. Check this variant's voltage and whether the board accepts input or provides output here.","Szyna zasilania. Sprawdź napięcie wariantu i czy płytka przyjmuje, czy udostępnia tu zasilanie.")
    if label=="NC":
        if symbol=="relay" or "Przekaźnik" in name:
            return t("Normally closed contact: connected to COM when the relay is not energised.","Styk normalnie zwarty: połączony z COM przy niewysterowanym przekaźniku.")
        return t("Not connected internally; leave unused as specified by the datasheet.","Niepołączony wewnętrznie; pozostaw nieużywany zgodnie z dokumentacją.")
    gates=any(code in name for code in ("74HC00","74HC04","74HC02","74HC08","74HC14","74HC32","74HC86","CD4093"))
    match=re.fullmatch(r"(\d+)([ABY])",label) if gates else None
    if match:
        channel,signal=match.groups()
        if signal=="Y": return t(f"Logic output of gate {channel}; determined by that gate's inputs.",f"Wyjście logiczne bramki {channel}; jego stan wynika ze stanów jej wejść.")
        suffix=t(" Schmitt-trigger input with hysteresis."," Wejście Schmitta z histerezą.") if "74HC14" in name or "CD4093" in name else ""
        return t(f"Input {signal} of gate {channel}.",f"Wejście {signal} bramki {channel}.")+suffix
    if "74HC74" in name:
        match=re.fullmatch(r"(\d)(/?Q|D|CLK|CLR|PRE)",label)
        if match:
            channel,signal=match.groups()
            roles={"D":("Data input, sampled on the rising clock edge.","Wejście danych, próbkowane narastającym zboczem zegara."),
                   "CLK":("Rising-edge clock input.","Wejście zegara wyzwalane zboczem narastającym."),
                   "CLR":("Asynchronous clear, active LOW; forces Q=0.","Asynchroniczne zerowanie, aktywne LOW; wymusza Q=0."),
                   "PRE":("Asynchronous preset, active LOW; forces Q=1.","Asynchroniczne ustawienie, aktywne LOW; wymusza Q=1."),
                   "Q":("Stored data output.","Wyjście zapamiętanego bitu."),"/Q":("Inverted stored data output.","Zanegowane wyjście zapamiętanego bitu.")}
            return t(f"Flip-flop {channel}: ",f"Przerzutnik {channel}: ")+t(*roles[signal])
    if "74HC595" in name:
        roles={"SER":("Serial data input.","Szeregowe wejście danych."),"SRCLK":("Shift clock: rising edge shifts one bit.","Zegar przesuwania: zbocze narastające przesuwa jeden bit."),
               "RCLK":("Rising edge copies the shift register into the output register.","Zbocze narastające przepisuje rejestr przesuwny do rejestru wyjściowego."),
               "SRCLR":("Active-LOW asynchronous clear of the shift register, not the output register.","Asynchroniczne zerowanie rejestru przesuwnego stanem LOW; nie zeruje rejestru wyjściowego."),
               "OE":("Output enable, active LOW; HIGH makes parallel outputs high-impedance.","Włączenie wyjść stanem LOW; HIGH przełącza wyjścia równoległe w wysoką impedancję."),
               "QH′":("Serial cascade output from the last shift stage.","Szeregowe wyjście ostatniego stopnia do łączenia kaskadowego.")}
        if label in roles: return t(*roles[label])
        if re.fullmatch(r"Q[A-H]",label): return t("Parallel output from the storage register.","Wyjście równoległe rejestru wyjściowego.")
    if symbol.startswith("gate_") or symbol in {"logic_input","logic_output"}:
        return t("Logic input.","Wejście logiczne.") if label in {"A","B","IN"} else t("Logic output.","Wyjście logiczne.")
    discrete={"B":("Base: controls collector current.","Baza: steruje prądem kolektora."),"C":("Collector terminal.","Zacisk kolektora."),"E":("Emitter terminal.","Zacisk emitera."),
              "G":("Gate: controls conduction through gate-source voltage.","Bramka: steruje przewodzeniem napięciem względem źródła."),"D":("Drain terminal.","Zacisk drenu."),"S":("Source terminal.","Zacisk źródła.")}
    if symbol in {"npn","pnp","nmos","pmos"} and label in discrete: return t(*discrete[label])
    if symbol in {"diode","led","zener","schottky"} and label in {"A","K"}:
        return t("Anode.","Anoda.") if label=="A" else t("Cathode.","Katoda.")
    if symbol in {"resistor","inductor","capacitor","thermistor","ldr","crystal"}:
        return t("Non-polarised terminal; either orientation is permitted.","Zacisk bez określonej biegunowości; dopuszczalna dowolna orientacja.")
    if label in {"+","-","−"}:
        return t("Positive terminal.","Zacisk dodatni.") if label=="+" else t("Negative terminal.","Zacisk ujemny.")
    common={"SDA":("I2C data line; requires suitable pull-up resistors.","Linia danych I2C; wymaga odpowiednich rezystorów podciągających."),
            "SCL":("I2C clock line; requires suitable pull-up resistors.","Linia zegara I2C; wymaga odpowiednich rezystorów podciągających."),
            "MOSI":("SPI data from controller to peripheral.","Dane SPI od kontrolera do urządzenia peryferyjnego."),
            "MISO":("SPI data from peripheral to controller.","Dane SPI od urządzenia peryferyjnego do kontrolera."),
            "SCK":("SPI clock.","Zegar SPI."),"SCLK":("SPI clock.","Zegar SPI."),
            "TX":("UART transmit signal.","Sygnał nadawania UART."),"RX":("UART receive signal.","Sygnał odbioru UART."),
            "COM":("Common relay/switch contact.","Wspólny styk przekaźnika lub przełącznika."),
            "NO":("Normally open contact.","Styk normalnie rozwarty.")}
    if label in common: return t(*common[label])
    if re.fullmatch(r"GPIO\d+|GP\d+|GP[A-B]\d+",label):
        return t("Programmable digital input/output; available alternate functions depend on the device.","Programowalne wejście/wyjście cyfrowe; funkcje alternatywne zależą od urządzenia.")
    return t("Device-specific signal. Consult the linked documentation for direction, levels and timing.","Sygnał specyficzny dla urządzenia. Kierunek, poziomy i przebiegi sprawdź w podlinkowanej dokumentacji.")
