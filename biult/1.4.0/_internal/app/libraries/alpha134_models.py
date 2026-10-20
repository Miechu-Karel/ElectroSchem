from app.libraries.simulation_catalog import P, Behavior, approximate

def behavior(d):
    from app.libraries.alpha1311_parts import behavior as alpha11
    newer=alpha11(d)
    if newer: return newer
    if d.name == "Goldpin":
        return Behavior("connector",note_en="TOP and BOTTOM are the two ends of one conductor, internally connected. Repeat pins to build a header.",note_pl="TOP i BOTTOM to dwa wewnętrznie połączone końce jednego przewodnika. Powielaj piny, aby zbudować listwę.")
    if d.name == "Kabel USB":
        from app.simulation.usb import TYPES
        choices=tuple((x,x,x) for x in TYPES)
        return Behavior("connector",(P("sim_usb_a_type","First plug","Pierwsza końcówka",default="A",choices=choices),P("sim_usb_b_type","Second plug","Druga końcówka",default="C",choices=choices)),note_en="Passive cable. Drag plugs onto matching sockets in the sandbox. No HID/USB-PD protocol.",note_pl="Kabel pasywny. Przeciągaj wtyczki na zgodne gniazda w symulatorze. Bez protokołu HID/USB-PD.")
    if d.name == "Przełącznik wielostopniowy":
        return approximate("multi_switch", [P("sim_allow_off","Allow fully open position","Możliwość całkowitego rozpięcia",default="true",choices=(("true","Yes","Tak"),("false","No","Nie"))),P("sim_outputs","Number of outputs","Liczba wyjść",default="6",choices=tuple((str(i),str(i),str(i)) for i in range(1,11))),P("sim_position", "Position", "Pozycja", default="1",
            choices=tuple((str(i), "OFF" if i == 0 else str(i), "Wyłączony" if i == 0 else str(i)) for i in range(11)))],
            en="Choose 1–10 output terminals (six by default). COM connects to the selected terminal. Position 0 is open. Click to cycle.",
            pl="Ustaw 1–10 wyjść (domyślnie sześć). COM łączy się z wybranym zaciskiem. Pozycja 0 rozwiera styk. Kliknij, aby zmienić pozycję.")
    if d.name == "Kostka zasilająca USB":
        return approximate("dc", [P("sim_max_current", "Current limit", "Limit prądu", "A", "2 A")], "V",
            en="Regulated DC output. No mains input model or fast-charge negotiation.",
            pl="Stabilizowane wyjście DC. Bez modelu wejścia sieciowego i negocjacji szybkiego ładowania.")
    if d.name == "Klawiatura USB":
        return approximate("usb_keyboard", [P("sim_load_current", "Supply current", "Prąd zasilania", "A", "20 mA")],
            en="5 V load and text entry into a connected simulated Python console. No HID packets or USB host stack.",
            pl="Obciążenie 5 V i wpisywanie tekstu do podłączonej symulowanej konsoli Python. Bez pakietów HID i stosu USB.")
    if d.name == "Mini silnik MT64 3-6V":
        return approximate("dc_motor", [P("sim_resistance", "Winding resistance", "Rezystancja uzwojenia", "Ω", "20 Ω"),
            P("sim_rated_voltage", "Rated voltage", "Napięcie znamionowe", "V", "5 V"),
            P("sim_max_current", "Current limit", "Limit prądu", "A", "300 mA")],
            en="Resistive DC load, signed rotation indicator. No inertia, torque, back-EMF or measured MT64 characteristics.",
            pl="Rezystancyjne obciążenie DC i wskaźnik kierunku obrotów. Bez bezwładności, momentu, SEM i zmierzonych charakterystyk MT64.")
    if d.symbol == "meter":
        return approximate("ammeter" if d.name == "Amperomierz" else "meter",
              en="Ammeter: series 1 mΩ shunt. Other probes: 1 TΩ input. Resistance/continuity require a de-energised passive circuit. Scope axes are controlled directly in the simulator.",
            pl="Amperomierz: bocznik szeregowy 1 mΩ. Pozostałe sondy: wejście 1 TΩ. Opór i ciągłość wymagają pasywnej sieci bez zasilania. Osie oscyloskopu ustawisz bezpośrednio w symulatorze.")
    return None
