"""Semantic, educational 1.3.0alpha4 parts, not certified physical pinouts."""
def install(add, terminals):
    parts = []
    def part(category, name, en, pins, **kw):
        add(name, en, pins, **kw)
        parts.append((category, name))
    part("Moduły i interfejsy", "Przełącznik wielostopniowy", "Multi-position Switch",
         "COM|1|2|3|4|5|6", symbol="connector", variant="One pole, 1–10 selectable outputs (six by default) and OFF; ideal break-before-make contacts")
    part("Zasilanie i połączenia", "Goldpin", "Gold Pin",
         terminals(("TOP", "TOP", -40, 0), ("BOTTOM", "BOTTOM", 40, 0)), symbol="goldpin", width=80, height=40,
         variant="One conducting pin with separate top (plug) and bottom (PCB) ends; repeat to build a header")
    part("Zasilanie i połączenia", "Kabel USB", "USB Cable",
         "A.VBUS|A.D−|A.D+|A.GND|B.VBUS|B.D−|B.D+|B.GND", symbol="connector",
         variant="USB 2.0 cable: A/B identify ends, not connector types. Matching conductors joined; no protocol or PD negotiation")
    part("Zasilanie i połączenia", "Kostka zasilająca USB", "USB Power Brick",
         terminals((1, "VBUS", -40, 0), (2, "GND", 40, 0)), symbol="battery", unit="V",
         variant="Educational regulated DC output; input mains and USB fast-charge negotiation not modelled")
    part("Moduły i interfejsy", "Klawiatura USB", "USB Keyboard", "VBUS|D−|D+|GND", symbol="connector",
         width=240, height=120,
         variant="USB-powered keyboard with simulated console text input; no USB enumeration/HID packets")
    part("Napędy", "Mini silnik MT64 3-6V", "MT64 Mini Motor 3-6V",
         terminals((1, "+", -80, 0), (2, "−", 80, 0)), symbol="motor", width=160, height=80,
         variant="Generic resistive DC motor envelope, indicative rotation only. Winding resistance is configurable, not measured MT64 data")
    for name, en, letter in (("Woltomierz", "Voltmeter", "V"), ("Amperomierz", "Ammeter", "A"),
                             ("Omomierz", "Ohmmeter", "Ω"), ("Tester ciągłości", "Continuity Tester", "•"),
                             ("Oscyloskop", "Oscilloscope", "~")):
        part("Narzędzia pomiarowe", name, en, terminals((1, "+", -40, 0), (2, "−", 40, 0)),
             symbol="meter", width=80, height=40, variant="Educational two-terminal instrument: "+letter)
    return parts
