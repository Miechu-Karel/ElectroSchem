"""Oddzielna baza funkcjonalności, niezależna od katalogu rysunków.

Brak modelu oznacza BRAK obsługi, nigdy idealny przewód ani pominięcie
elementu. Parametry i ograniczenia są wspólne dla formularza i silnika.
Wartości domyślne opisują model edukacyjny, nie dokumentację części.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Parameter:
    key: str
    en: str
    pl: str
    unit: str = ""
    default: str = ""
    choices: tuple = ()
    minimum: float = 1e-15
    maximum: float = 1e15


@dataclass(frozen=True)
class Behavior:
    kind: str
    parameters: tuple[Parameter, ...] = ()
    primary_unit: str = ""
    note_en: str = ""
    note_pl: str = ""


P = Parameter
BEHAVIORS = {
    "resistor": Behavior("resistor", (P("sim_max_power", "Rated power", "Moc znamionowa", "W", "0.25 W"),), "Ω"),
    "capacitor": Behavior("capacitor", (P("sim_initial_voltage", "Initial voltage", "Napięcie początkowe", "V", "0 V", minimum=-1e6, maximum=1e6),), "F"),
    "polar_capacitor": Behavior("polar_capacitor", (P("sim_initial_voltage", "Initial voltage (V or auto)", "Napięcie początkowe (V lub auto)", "V", "auto", minimum=-1e6, maximum=1e6),), "F",
        "auto applies a reproducible startup precharge within ±100 mV. Enter 0 V for an uncharged ideal capacitor.",
        "auto ustawia powtarzalne wstępne napięcie do rozruchu w zakresie ±100 mV. Wpisz 0 V dla idealnego nienaładowanego kondensatora."),
    "inductor": Behavior("inductor", (), "H"),
    "battery": Behavior("dc", (), "V"),
    "ac_source": Behavior("ac", (P("sim_frequency", "Frequency", "Częstotliwość", "Hz", "50 Hz"),), "V",
                          "Voltage is RMS; sine wave, zero phase.", "Napięcie skuteczne RMS; sinusoida, faza zerowa."),
    "lamp": Behavior("lamp", (P("sim_rated_voltage", "Rated voltage", "Napięcie znamionowe", "V"),), "W",
                     "Constant hot resistance approximation; no thermal transient.",
                     "Przybliżenie stałej rezystancji gorącego włókna; bez modelu nagrzewania."),
    "spst": Behavior("switch", (P("sim_closed", "Initially ON", "Początkowo ON", default="false", choices=(("false", "OFF", "OFF"), ("true", "ON", "ON"))),)),
    "led": Behavior("led", (P("sim_forward_voltage", "Forward voltage", "Napięcie przewodzenia", "V", "2 V"),
                            P("sim_max_current", "Maximum current", "Maksymalny prąd", "A", "20 mA"),
                            P("sim_reverse_voltage", "Maximum reverse voltage", "Maksymalne napięcie wsteczne", "V", "5 V")),
                    note_en="Piecewise-linear LED, 10 Ω dynamic resistance. Set ratings for your LED.",
                    note_pl="Odcinkowo-liniowa LED, rezystancja dynamiczna 10 Ω. Ustaw parametry swojej diody."),
    "diode": Behavior("diode", (P("sim_forward_voltage", "Forward voltage", "Napięcie przewodzenia", "V", "0.7 V"),
                                 P("sim_max_current", "Maximum current", "Maksymalny prąd", "A", "1 A")),
                      note_en="Piecewise-linear diode; no breakdown/recovery model.",
                      note_pl="Dioda odcinkowo-liniowa; bez modelu przebicia/odzyskiwania."),
    "ground": Behavior("ground"),
    "logic_input": Behavior("logic_input", (P("sim_closed", "Initial state", "Stan początkowy", default="false", choices=(("false","LOW","LOW"),("true","HIGH","HIGH"))),)),
    "logic_output": Behavior("logic_output", note_en="High-impedance logic indicator with an implicit ground reference.", note_pl="Wskaźnik logiczny o dużej impedancji z wewnętrznym odniesieniem do masy."),
    "power": Behavior("rail_source"),
}


# Parametry modeli są przechowywane w ELS, ale nie zmieniają katalogu symboli.
# Zero jest poprawne np. dla suwaka potencjometru; zakres walidujemy wspólnie
# dla formularza i solvera, zamiast poprawiać błędną wartość po cichu.
ON_OFF = (("false", "OFF", "OFF"), ("true", "ON", "ON"))
CONTACT = P("sim_closed", "Initially ON", "Początkowo ON", default="false", choices=ON_OFF)
APPROX_EN = "Educational approximation; editable parameters are model values, not verified part ratings."
APPROX_PL = "Przybliżenie edukacyjne; edytowalne parametry opisują model, nie potwierdzone parametry części."


def approximate(kind, parameters=(), unit="", en="", pl=""):
    return Behavior(kind, tuple(parameters), unit, en or APPROX_EN, pl or APPROX_PL)


BEHAVIORS.update({
    "potentiometer": approximate("potentiometer", [P("sim_position", "Wiper position (0–1)", "Położenie suwaka (0–1)", default="0.5", minimum=0, maximum=1)], "Ω"),
    "ldr": approximate("ldr", [P("sim_light", "Relative illumination (1 = reference)", "Względne oświetlenie (1 = odniesienie)", default="1", minimum=.001, maximum=1000)], "Ω",
                       "Resistance = entered reference resistance / relative illumination.", "Rezystancja = wpisana rezystancja odniesienia / względne oświetlenie."),
    "thermistor": approximate("thermistor", [P("sim_temperature", "Temperature [K]", "Temperatura [K]", default="298.15", minimum=1, maximum=1000), P("sim_beta", "Beta [K]", "Beta [K]", default="3950")], "Ω",
                              "Beta model; entered resistance is R25 at 298.15 K.", "Model beta; wpisana rezystancja to R25 przy 298,15 K."),
    "schottky": approximate("diode", [P("sim_forward_voltage", "Forward voltage", "Napięcie przewodzenia", "V", "0.3 V"), P("sim_max_current", "Maximum current", "Maksymalny prąd", "A", "1 A")]),
    "zener": approximate("zener", [P("sim_forward_voltage", "Forward voltage", "Napięcie przewodzenia", "V", "0.7 V"), P("sim_breakdown", "Zener voltage", "Napięcie Zenera", "V", "5.1 V"), P("sim_max_power", "Rated power", "Moc znamionowa", "W", "0.5 W")]),
    "rgb": approximate("rgb", [P("sim_forward_voltage", "Channel forward voltage", "Napięcie przewodzenia kanałów", "V", "2 V"), P("sim_max_current", "Maximum current per channel", "Maksymalny prąd kanału", "A", "20 mA")],
                       en="Three independent LED branches with a common cathode. Equal adjustable channel thresholds; no spectral model.", pl="Trzy niezależne diody ze wspólną katodą. Wspólny ustawiany próg kanałów; bez modelu widma."),
    "switch": approximate("tactile", [CONTACT]),
    "spdt": approximate("spdt", [CONTACT], en="OFF selects COM–A, ON selects COM–B. Click to switch in the sandbox.", pl="OFF łączy COM–A, ON łączy COM–B. Kliknij w sandboxie, aby przełączyć."),
    "relay": approximate("relay", [P("sim_coil_resistance", "Coil resistance", "Rezystancja cewki", "Ω", "70 Ω"), P("sim_pickup", "Pickup voltage", "Napięcie załączenia", "V", "3.5 V")],
                         en="Resistive coil, pickup threshold and 50% release hysteresis; no coil inductance/contact bounce.", pl="Rezystancyjna cewka, próg załączenia i histereza zwolnienia 50%; bez indukcyjności i drgania styków."),
    "opto": approximate("opto", [P("sim_forward_voltage", "Input forward voltage", "Napięcie przewodzenia wejścia", "V", "1.2 V"), P("sim_ctr", "Current transfer ratio (1 = 100%)", "Współczynnik CTR (1 = 100%)", default="0.5")]),
    "buzzer": approximate("buzzer", [P("sim_resistance", "Equivalent load resistance", "Zastępcza rezystancja obciążenia", "Ω", "250 Ω"), P("sim_rated_voltage", "Rated voltage", "Napięcie znamionowe", "V", "5 V"), P("sim_tone_frequency","Active buzzer tone","Ton buzzera aktywnego","Hz","2 kHz",minimum=20,maximum=10000)],
                          en="Resistive load with synthesized audio, not LED glow. Active buzzer uses the set tone; passive buzzer estimates frequency from sampled rising edges (20 Hz-10 kHz), not DC. The time step must resolve the signal.", pl="Obciążenie rezystancyjne z syntezowanym dźwiękiem, bez poświaty LED. Aktywny buzzer używa ustawionego tonu; pasywny szacuje częstotliwość ze zboczy (20 Hz-10 kHz), nie z DC. Krok musi rozróżniać przebieg."),
    "connector": Behavior("connector", note_en="Independent terminals; no internal short between adjacent pins.", note_pl="Niezależne zaciski; sąsiednie piny nie są wewnętrznie zwarte."),
    "crystal": approximate("crystal", [P("sim_motional_capacitance", "Motional capacitance", "Pojemność gałęzi rezonansowej", "F", "20 fF"), P("sim_series_resistance", "Series resistance", "Rezystancja szeregowa", "Ω", "30 Ω"), P("sim_parallel_capacitance", "Parallel capacitance", "Pojemność równoległa", "F", "5 pF")], "Hz",
                           "Passive series RLC branch in parallel with C0. Not a clock generator; requires a time step below 1/(50 f).", "Pasywna szeregowa gałąź RLC równolegle z C0. To nie generator zegara; krok musi być mniejszy od 1/(50 f)."),
})
for symbol in ("npn", "pnp"):
    BEHAVIORS[symbol] = approximate(symbol, [P("sim_vbe", "Base–emitter threshold", "Próg baza–emiter", "V", "0.7 V"), P("sim_gain", "Current gain beta", "Wzmocnienie prądowe beta", default="100"), P("sim_max_current", "Collector current limit", "Limit prądu kolektora", "A", "100 mA")],
        en="Piecewise-linear base junction, beta-controlled collector current, resistive saturation; no reverse-active or charge-storage model.", pl="Odcinkowo-liniowe złącze bazy, prąd kolektora sterowany beta, rezystancyjne nasycenie; bez pracy inwersyjnej i magazynowania ładunku.")
for symbol in ("nmos", "pmos"):
    BEHAVIORS[symbol] = approximate(symbol, [P("sim_threshold", "Gate threshold", "Próg bramki", "V", "2 V"), P("sim_on_resistance", "ON resistance", "Rezystancja włączenia", "Ω", "0.1 Ω"), P("sim_max_current", "Drain current limit", "Limit prądu drenu", "A", "1 A")],
        en="Voltage-controlled channel with body diode; no gate charge or switching losses.", pl="Kanał sterowany napięciem i dioda podłoża; bez ładunku bramki i strat przełączania.")
for symbol in ("thyristor", "triac"):
    BEHAVIORS[symbol] = approximate(symbol, [P("sim_trigger", "Gate trigger voltage", "Napięcie wyzwalania bramki", "V", "1 V"), P("sim_holding", "Holding current", "Prąd podtrzymania", "A", "5 mA")])


def behavior_for(definition):
    from app.libraries.emulator_catalog import profile_for
    if definition is None:
        return None
    profile = profile_for(definition)
    if profile:
        return Behavior("mcu" if profile.ready else "mcu_gpio",
            note_en=profile.reason_en+" GPIO script mode supports digital pins only. Create a program or assign an existing source file using the buttons above. It does not emulate the OS or CPU.",
            note_pl=profile.reason_pl+" Tryb skryptu GPIO obsługuje piny cyfrowe. Utwórz program lub przypisz istniejący plik kodu przyciskami powyżej. Nie emuluje systemu ani procesora.")
    symbol, name = definition.symbol, definition.name
    if symbol == "power":
        voltage = "3.3 V" if "+3.3V" in name else "12 V" if "+12V" in name else "5 V"
        parameters = (P("sim_voltage", "Supply voltage", "Napięcie zasilania", "V", voltage),) if name.endswith("VCC") else ()
        return Behavior("rail_source", parameters, note_en="Ideal supply relative to GND. Identical rail symbols share one source.", note_pl="Idealne zasilanie względem GND. Identyczne symbole szyny korzystają ze wspólnego źródła.")
    if symbol.startswith("gate_"):
        return approximate("logic_gate", [P("sim_logic_voltage", "Logic HIGH voltage", "Napięcie logicznego HIGH", "V", "5 V")], en="Ideal truth table; 25 Ω output, half-supply threshold. Implicit supply referenced to circuit ground.", pl="Idealna tablica prawdy; wyjście 25 Ω, próg połowy zasilania. Wewnętrzne zasilanie względem masy obwodu.")
    if symbol in BEHAVIORS:
        return BEHAVIORS[symbol]
    # Konkretna funkcja zależy od układu, nie od prostokątnego symbolu 'ic'.
    from app.libraries.simulation_parts import part_behavior
    return part_behavior(definition)


def functionality_database():
    """Każdy symbol biblioteki ma jawny status, także modele przyszłe."""
    from app.libraries.built_in import AVAILABLE_ITEMS
    return {d.id: behavior_for(d) for d in AVAILABLE_ITEMS}
