from app.libraries.simulation_catalog import P, approximate, Behavior, ON_OFF

def behavior(d):
    name = d.name
    if name.startswith("Port USB") or name == "Port Lightning":
        return Behavior("connector", note_en="Passive socket. Supply must come from a wired source; no built-in 5 V or USB PD. USB-C VBUS contacts are joined, as are GND contacts.",
                        note_pl="Pasywne gniazdo. Zasilanie musi pochodzić z podłączonego źródła; bez wbudowanych 5 V i USB PD. Styki VBUS USB-C są połączone, podobnie styki GND.")
    if name == "Karta RFID":
        return Behavior("connector", (P("rfid_id", "Card ID (hexadecimal)", "ID karty (szesnastkowo)", default="A1B2C3D4"),), note_en="Drag the passive card near an RC522 in simulation. UID preview only, not an RF/SPI protocol.", note_pl="Przeciągnij pasywną kartę do RC522 w symulacji. Podgląd UID, nie emulacja protokołu RF/SPI.")
    if name == "Zapałka":
        return Behavior("connector", note_en="A movable simulation prop. Click to light or extinguish it; a lit match near a flame sensor changes that sensor's simulated output.", note_pl="Ruchomy rekwizyt symulacji. Kliknij, aby zapalić lub zgasić; płonąca zapałka obok czujnika płomienia zmienia jego sygnał.")
    if name == "Cel ultradźwiękowy":
        return Behavior("connector", note_en="Move this reflector near an HC-SR04. Distance is approximated as 1 m per 100 scene units and drives the ECHO pulse; outside 4 m the configured distance is used.", note_pl="Przesuń ten odbijający cel w pobliże HC-SR04. Odległość jest przybliżana jako 1 m na 100 jednostek sceny i steruje impulsem ECHO; poza 4 m używana jest odległość ustawiona w modelu.")
    if name == "Osoba":
        return Behavior("connector", note_en="Move this heat-source prop within 2.6 m (260 scene units) of a PIR sensor to set its simulated output active. This is a simplified presence stimulus, not a Fresnel-zone or motion-history model.", note_pl="Przesuń ten rekwizyt źródła ciepła w zasięg 2,6 m (260 jednostek sceny) od czujnika PIR, aby uaktywnić jego wyjście. To uproszczony bodziec obecności, bez modelu stref soczewki Fresnela i historii ruchu.")
    if name == "Pilot IR":
        return Behavior("connector", note_en="Click near an IR receiver to send a short active-low stimulus pulse. Optical carrier, command encoding and remote protocols are not emulated.", note_pl="Kliknij w pobliżu odbiornika IR, aby wysłać krótki impuls aktywny stanem niskim. Nośna optyczna, kodowanie komend i protokoły pilotów nie są emulowane.")
    if name == "Panel słoneczny":
        return approximate("solar", [P("sim_open_voltage", "Full-light voltage", "Napięcie przy pełnym oświetleniu", "V", "6 V"),
            P("sim_light", "Illumination (0–1)", "Oświetlenie (0–1)", default="1", minimum=0, maximum=1),
            P("sim_max_current", "Current limit", "Limit prądu", "A", "200 mA")],
            en="Ideal voltage proportional to illumination with an overcurrent warning. Not a photovoltaic IV-curve or irradiance/temperature model.",
            pl="Idealne napięcie proporcjonalne do oświetlenia i błąd przeciążenia. Bez krzywej IV ogniwa ani modelu temperatury.")
    if name == "Prostownik AC/DC":
        return approximate("rectifier", en="Four 0.7 V piecewise-linear diodes, no smoothing capacitor or isolation.", pl="Cztery diody odcinkowo-liniowe 0,7 V, bez kondensatora filtrującego i izolacji.")
    if name.startswith("Przetwornica DC"):
        params = [P("sim_output_voltage", "Output voltage (RMS for AC)", "Napięcie wyjściowe (RMS dla AC)", "V", "5 V"),
            P("sim_efficiency", "Efficiency (0–1)", "Sprawność (0–1)", default="0.9", minimum=.01, maximum=1),
            P("sim_max_current", "Output current limit", "Limit prądu wyjściowego", "A", "1 A")]
        if name == "Przetwornica DC/AC": params.append(P("sim_frequency", "Frequency", "Częstotliwość", "Hz", "50 Hz"))
        return approximate("inverter" if name == "Przetwornica DC/AC" else "converter", params,
            en="Averaged non-isolated energy-balance model; no switching ripple, transformer or USB/mains protocol.",
            pl="Uśredniony nieizolowany model bilansu energii; bez tętnień, transformatora i protokołu zasilania.")
    if name in {"Stabilizator regulowany DC", "Stabilizator Liniowy 9V"}:
        return approximate("regulator", [P("sim_output_voltage", "Output voltage", "Napięcie wyjściowe", "V", "9 V" if "9V" in name else "5 V"),
            P("sim_dropout", "Dropout voltage", "Minimalny spadek napięcia", "V", "2 V"), P("sim_max_current", "Output current limit", "Limit prądu wyjściowego", "A", "1 A")])
    if name == "Komparator LM393":
        return approximate("comparator", en="Two ideal open-collector comparators. External pull-up required; no offset/delay/common-mode model.", pl="Dwa idealne komparatory z otwartym kolektorem. Wymagają podciągnięcia; bez offsetu, opóźnień i zakresu common-mode.")
    if name == "Wzmacniacz LM324":
        return approximate("quad_opamp", [P("sim_gain", "Open-loop gain", "Wzmocnienie otwartej pętli", default="100000")],
            en="Four rail-clipped gain stages, 25 Ω outputs. No bandwidth/slew-rate or input common-mode model.", pl="Cztery wzmacniacze ograniczone szynami, wyjścia 25 Ω. Bez pasma, slew-rate i modelu common-mode.")
    if name == "Przełącznik analogowy CD4066":
        return approximate("analog_switch", [P("sim_on_resistance", "ON resistance", "Rezystancja włączenia", "Ω", "100 Ω")],
            en="Four bilateral resistive switches, enabled above half VDD. No charge injection/timing model.", pl="Cztery dwukierunkowe klucze rezystancyjne, załączenie powyżej połowy VDD. Bez wstrzykiwania ładunku i opóźnień.")
    if name.startswith("Przetwornik DAC "):
        bits = sum(pin.name.startswith("D") and pin.name[1:].isdigit() for pin in d.pins)
        return approximate("parallel_dac", en=f"Binary D0..D{bits-1} sampled at half VCC; output = VREF × code/{(1<<bits)-1}, 25 Ω output. No settling/noise model.", pl=f"Próbkowanie D0..D{bits-1} przy połowie VCC; wyjście = VREF × kod/{(1<<bits)-1}, rezystancja 25 Ω. Bez czasu ustalania i szumu.")
    if name == "Grove LSM6DS3 105020012":
        return approximate("peripheral_envelope", [P("sim_nominal_voltage", "Model supply voltage", "Napięcie zasilania modelu", "V", "3.3 V"),
            P("sim_load_current", "Model supply current", "Prąd zasilania modelu", "A", "0.9 mA"),
            P("sim_stimulus", "Preview stimulus", "Bodziec podglądu", default="0", minimum=-1e6, maximum=1e6)],
            en="Supply-envelope placeholder only. Motion, six-axis values and I2C registers are not yet emulated; interaction will be designed together.",
            pl="Na razie tylko model zasilania. Ruch, sześć osi i rejestry I2C nie są emulowane; sterowanie ustalimy razem.")
    return None
