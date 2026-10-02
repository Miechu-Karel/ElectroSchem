"""Modele konkretnych modułów. Brak wpisu nigdy nie oznacza pustego modelu.

Nazwy pinów pochodzą z katalogu. Nie zakładamy, że pin 1 każdego modułu to
VCC ani że wszystkie prostokąty działają jak dwukońcówkowe rezystory.
"""
from app.libraries.simulation_catalog import P, CONTACT, approximate


def part_behavior(d):
    name = d.name
    if "Stabilizator" in name:
        return approximate("regulator", [P("sim_dropout", "Dropout voltage", "Minimalny spadek napięcia", "V", "1.2 V" if "1117" in name else "2 V"), P("sim_max_current", "Output current limit", "Limit prądu wyjściowego", "A", "1 A")])
    if "NE555" in name:
        return approximate("timer555", en="Comparator/latch model with control-voltage divider, RESET and discharge switch. 25 Ω output; no internal propagation delay.", pl="Model komparatorów i przerzutnika, dzielnik CONT, RESET i klucz rozładowujący. Wyjście 25 Ω; bez opóźnień wewnętrznych.")
    if "LM358" in name:
        return approximate("opamp", [P("sim_gain", "Open-loop gain", "Wzmocnienie otwartej pętli", default="100000")], en="Two gain stages limited to supply rails, 25 Ω output; no bandwidth or slew-rate model.", pl="Dwa wzmacniacze ograniczone szynami zasilania, wyjście 25 Ω; bez modelu pasma i szybkości narastania.")
    if any(part in name for part in ("74HC00", "74HC02", "74HC04", "74HC08", "74HC14", "74HC32", "74HC86", "CD4093")):
        return approximate("logic_package", en="Powered truth-table gates; 25 Ω outputs. HC14/CD4093 use 30%/70% Schmitt thresholds. No propagation delay.", pl="Zasilane bramki z tablicą prawdy; wyjścia 25 Ω. HC14/CD4093 mają progi Schmitta 30%/70%. Bez opóźnień propagacji.")
    if "74HC74" in name:
        return approximate("flipflop", en="Two rising-edge D flip-flops, active-low PRE/CLR. Initial Q = 0; PRE=CLR=0 is rejected.", pl="Dwa przerzutniki D na zbocze narastające, aktywne niskim PRE/CLR. Początkowo Q = 0; PRE=CLR=0 zgłasza błąd.")
    if "74HC595" in name:
        return approximate("shift_register", en="8-bit shift register, separate storage latch, active-low reset and output enable. Initial registers = 0.", pl="8-bitowy rejestr przesuwny, osobny zatrzask, reset i zezwolenie wyjść aktywne niskim. Początkowo rejestry = 0.")
    if "MCP3008" in name:
        return approximate("adc_spi", en="Sampled SPI mode 0/3, 10-bit ADC, eight single-ended or differential inputs. Both clock edges must be resolved by the circuit time step; no conversion noise.", pl="Próbkowane SPI 0/3, ADC 10-bit, osiem wejść pojedynczych/różnicowych. Krok musi rozróżniać oba zbocza zegara; bez szumu konwersji.")
    if "MCP41010" in name:
        return approximate("digital_pot", unit="Ω", en="SPI 16-bit write/shutdown commands; initial wiper 128/256. Ideal resistance array without wiper contact resistance. Sample both clock edges.", pl="16-bitowe polecenia SPI zapisu/shutdown; początkowy suwak 128/256. Idealna drabinka bez rezystancji styku suwaka. Próbkuj oba zbocza zegara.")
    if name == "Enkoder Obrotowy":
        return approximate("encoder", [P("sim_frequency", "Quadrature cycle frequency", "Częstotliwość cyklu kwadratury", "Hz", "2 Hz"), CONTACT], en="Continuous ideal quadrature contacts A/C/B and clickable push switch; no bounce.", pl="Ciągła idealna kwadratura styków A/C/B i klikany przycisk; bez drgań styków.")
    if "L298N" in name:
        return approximate("hbridge", en="Two enabled H bridges powered from VS, 2 Ω output stages and current-sense returns. No switching-loss or flyback-clamp model.", pl="Dwa mostki H zasilane z VS, wyjścia 2 Ω i powroty pomiarowe SENSE. Bez strat przełączania i ogranicznika przepięć.")
    if "A4988" in name or "TMC2208" in name:
        return approximate("stepper_driver", [P("sim_max_current", "Phase current limit", "Limit prądu fazy", "A", "1 A")], en="Educational full-step abstraction of STEP/DIR, enable/reset/sleep and current-limit faults. MS inputs must be LOW in this model; this is not the TMC2208 hardware microstep table. No chopper or UART.", pl="Edukacyjne przybliżenie pełnych kroków STEP/DIR, enable/reset/sleep i awarii prądu. Model wymaga MS=LOW; nie odwzorowuje sprzętowej tabeli mikrokroków TMC2208. Bez choppera i UART.")
    if "LM2596" in name or "MT3608" in name:
        return approximate("converter", [P("sim_output_voltage", "Output voltage", "Napięcie wyjściowe", "V", "5 V"), P("sim_efficiency", "Efficiency (0–1)", "Sprawność (0–1)", default="0.9", minimum=.01, maximum=1), P("sim_max_current", "Output current limit", "Limit prądu wyjścia", "A", "1 A")], en="Averaged regulated DC model with input-power balance. No switching ripple/startup dynamics; buck/boost voltage range is enforced.", pl="Uśredniony model DC z bilansem mocy wejścia. Bez tętnień i rozruchu; uwzględnia zakres step-down/step-up.")
    if "ST1167" in name:
        return approximate("level_converter", en="RX uses HV-to-LV resistor dividers; TX uses a bidirectional MOS-switch approximation and 10 kΩ pull-ups. No parasitic capacitance/timing model.", pl="RX ma dzielnik HV→LV; TX ma dwukierunkowy model klucza MOS i podciągnięcia 10 kΩ. Bez pojemności pasożytniczych i modelu czasowego.")
    if "Klawiatura Membranowa" in name:
        choices = (("none", "None", "Brak"),) + tuple((str(i), f"R{i//4+1} / C{i%4+1}", f"R{i//4+1} / C{i%4+1}") for i in range(16))
        return approximate("keypad", [P("sim_key", "Pressed key", "Naciśnięty klawisz", default="none", choices=choices)], en="One selected row/column contact; click to cycle through keys, then release.", pl="Jeden wybrany styk wiersz/kolumna; klikaj, aby zmieniać klawisz i zwolnić.")
    if "Przekaźnika" in name:
        return approximate("relay_module", en="Active-low inputs, powered relay contacts. No optocoupler isolation transient or coil inductance.", pl="Wejścia aktywne niskim, zasilane styki przekaźników. Bez stanów przejściowych optoizolacji i indukcyjności cewki.")
    if name in {"Czujnik Podczerwieni", "Czujnik Ruchu PIR HC-SR501", "Czujnik Dźwięku Iduino ST1146"}:
        return approximate("digital_sensor", [P("sim_active", "Stimulus active", "Aktywny bodziec", default="false", choices=(("false", "No", "Nie"), ("true", "Yes", "Tak")))], en="Manually supplied stimulus, powered digital output. IR carrier/remote-control protocol is not generated.", pl="Ręcznie ustawiany bodziec i zasilane wyjście cyfrowe. Brak generowania nośnej/protokołu pilota IR.")
    if name in {"Czujnik Wilgotności Gleby", "Czujnik Gazu MQ-2", "Czujnik Płomienia", "Czujnik Dźwięku MAX9814"}:
        return approximate("analog_sensor", [P("sim_signal", "Signal fraction of supply (0–1)", "Sygnał jako część zasilania (0–1)", default="0.5", minimum=0, maximum=1), P("sim_trip", "Digital comparator threshold (0–1)", "Próg komparatora cyfrowego (0–1)", default="0.5", minimum=0, maximum=1)], en="Set the electrical output fraction directly; does not convert gas concentration, sound or moisture to voltage.", pl="Ustaw bezpośrednio względny sygnał elektryczny; brak przelicznika stężenia gazu, dźwięku i wilgotności na napięcie.")
    if "HC-SR04" in name:
        return approximate("ultrasonic", [P("sim_distance", "Distance [m]", "Odległość [m]", default="1", minimum=.02, maximum=4)], en="Trigger rising edge generates ECHO pulse 2 × distance / 343 m/s. Sampled at circuit time steps.", pl="Zbocze TRIG generuje impuls ECHO 2 × odległość / 343 m/s. Próbkowanie krokiem symulacji.")
    if d.symbol == "motor":
        if "NEMA" in name:
            return approximate("stepper_motor", [P("sim_resistance", "Phase resistance", "Rezystancja fazy", "Ω", "10 Ω"), P("sim_inductance", "Phase inductance", "Indukcyjność fazy", "H", "3 mH")], en="Two independent RL windings; phase currents and electrical activity only. No mechanical torque/position model.", pl="Dwa niezależne uzwojenia RL; prądy faz i aktywność elektryczna. Bez modelu momentu/pozycji mechanicznej.")
        return approximate("servo", en="Sampled PWM: 1–2 ms commands 0–180 degrees; EF90D uses signed speed. 100 Ω supply load (50 mA at 5 V), no mechanical inertia/stall model.", pl="Próbkowane PWM: 1–2 ms steruje 0–180 stopni; EF90D steruje prędkością ze znakiem. Obciążenie 100 Ω (50 mA przy 5 V), bez bezwładności/prądu zablokowania.")
    from app.libraries.peripheral_models import peripheral_behavior
    return peripheral_behavior(d)
