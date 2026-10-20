"""Versioned schematic design knowledge bundled with the application.

Rules are guidance, not physical certification or provider weight training.
Recipes refer to semantic pins; the model must resolve real catalog pin indices.
"""
RULE_GROUPS = {
    "visual_readability": [
        "Electrical correctness does not imply human-readable drawing. Treat composition as a separate acceptance condition.",
        "Before placing parts, divide the sheet into functional blocks: supply on the left, processing in the middle, outputs on the right. For multi-output supplies use aligned, evenly spaced branch rows or columns.",
        "Reserve at least two grid cells of clear space between symbol/label envelopes, not just between component centres. Use the provided layout_report envelopes to calculate spacing.",
        "Keep connected parts close within their block. Avoid long connections that cut across unrelated blocks. Reserve routing corridors before connecting pins.",
        "Prefer short horizontal/vertical routes with few bends; rotate components to face their neighbours and align related pins. Avoid a web of diagonals.",
        "ROTATE_COMPONENT angles are absolute clockwise in screen coordinates: 0:(x,y), 90:(-y,x), 180:(-x,-y), 270:(y,-x). Transform each catalog pin offset, then add the component centre. Pin index and physical pin identity NEVER change when rotated. Choose orientation from those coordinates, not the printed pin number or a memorized package order.",
        "No component or label overlaps, wires through symbols or labels, or stacked routes for different signals. Minimize non-junction wire crossings; intentional branches must be unambiguous.",
        "Use concise display names (voltage and purpose), not paragraphs printed over symbols. Explain caveats in the chat summary instead of the drawing.",
        "Read layout_report on revisions. Resolve the listed component references and wire IDs with MOVE_COMPONENT/ROTATE_COMPONENT and DISCONNECT/CONNECT deltas. Keep electrical nets and parameters unchanged for a readability-only request.",
        "Do not claim a layout is readable just because it simulates. State remaining layout warnings and let the user inspect the enlarged preview.",
    ],
    "topology": [
        "Every powered branch needs a closed return path to its own source negative terminal.",
        "Independent circuits may have independent references; do not merge their grounds without a reason.",
        "Crossing wires are not junctions; use real pin anchors and explicit shared endpoints.",
        "Never place a wire through a component body; route around symbols.",
        "Do not connect unlike ideal voltage sources in parallel.",
        "Power and ground labels create global named nets; label collisions matter.",
        "No unexplained floating signal inputs, supply pins or reference pins.",
        "Keep parts on the grid and preserve enough space for labels and routing.",
        "Do not overlap distinct wires collinearly for more than half a grid cell (10 scene units). Use one shared wire with explicit branch junctions instead of stacked cables.",
        "Never hide separate signals by drawing them on the same route. Reroute around existing cables; share a stretch only when the nets are intentionally electrically joined."],
    "power": [
        "For multiple outputs calculate SUM(Vout*Iout); input power must exceed this after efficiency losses. Never confuse input current with output current.",
        "Example: 3.3/5/9/12 V at 1.5 A each plus 25 V at 1 A needs 68.95 W output, at least 76.61 W input at 90% efficiency. An agreed 20 V / 5 A PD source has 100 W; 5 V / 8–10 A is insufficient.",
        "AMS1117 is not a 1.5 A output solution. Use an appropriately rated buck for 3.3/5/9/12 V from 20 V, and a boost for 25 V. Avoid large linear-regulator dissipation.",
        "Educational converter sim_max_current is an overload rating, not a verified CC clamp. Never claim physical current limiting unless the model actually implements it.",
        "Ports are passive and never generate power; connect an external source to VBUS/POWER and GND, not data pins.",
        "USB-C VBUS contacts are internally joined, as are GND contacts; PD negotiation is not emulated.",
        "Set source voltage and current limits explicitly; check total expected load current.",
        "Linear regulators need input above output plus dropout and share a return reference.",
        "Regulator dissipation is approximately (Vin-Vout)*I; verify thermal limits against a datasheet.",
        "Buck decreases voltage, boost increases it, buck-boost can do either within model limits.",
        "Converter input current is approximately Vout*Iout/(efficiency*Vin), not equal to output current.",
        "A bridge rectifier loses approximately two diode forward drops; add filtering when DC ripple matters."],
    "passives": [
        "Specify resistance, capacitance, inductance and units using valid catalog parameters.",
        "Resistor dissipation is I^2*R or V^2/R; choose a rating with headroom.",
        "Polarized capacitors require polarity and voltage rating above expected terminal voltage.",
        "RC time constant is R*C; do not equate it automatically with an oscillator period.",
        "Keep capacitor initial conditions explicit when startup or symmetry matters.",
        "An inductor needs a current path; do not ignore inductive turn-off voltage.",
        "A potentiometer's outer-terminal resistance is fixed; only wiper resistance changes.",
        "Connect a potentiometer wiper when controlling LED current or analog input."],
    "semiconductors": [
        "LEDs require a series current-limiting resistor and the correct A/K orientation.",
        "Estimate LED resistor with R=(Vs-Vf)/I; choose conservative current and power rating.",
        "LED colour and capacitor voltage rating are required simulation properties.",
        "Resolve E/B/C and G/D/S by actual library pin names; do not assume package order.",
        "NPN low-side switch: emitter to return, collector to load, base through a resistor.",
        "Add a flyback diode across inductive DC loads with cathode toward the positive supply.",
        "MOSFET gates need a defined off state and acceptable gate-source voltage.",
        "A transistor astable needs cross-coupling and bias paths, not merely two blinking labels."],
    "inputs": [
        "Tact contacts stay closed only while held; opposite sides switch, same-side contacts are common.",
        "The simulator defaults to released LOW/pressed HIGH joystick SW. Select physical mode for a real active-LOW SW-to-GND contact.",
        "Use a pull-up to the receiver's logic rail for active-LOW contacts; model pull-up is configurable.",
        "Do not pull a Raspberry Pi GPIO up to 5 V; use its 3.3 V logic rail.",
        "A keypad is a row/column contact matrix, not sixteen independent powered outputs.",
        "PIR needs supply and return; mouse motion supplies its stimulus in the sandbox.",
        "Joystick VRx/VRy are analog outputs; analog ADC coupling is not supported on every board.",
        "Do not pretend unsupported register protocols or sensor axes have been implemented."],
    "logic": [
        "Power complete logic IC packages at VCC/VDD and GND/VSS; ideal gate symbols differ.",
        "Keep logic levels inside the modeled supply rails and input thresholds.",
        "Tie unused gate inputs to a defined valid level; leave unused outputs open.",
        "An open-collector comparator output needs a pull-up resistor.",
        "Never directly join opposing push-pull outputs.",
        "Check inversion bubbles and gate truth tables rather than labels alone.",
        "Schmitt thresholds differ from ordinary half-supply thresholds.",
        "Output indicators are modeled references/loads, not arbitrary power sources."],
    "analog": [
        "Parallel DAC: D0 is LSB; OUT=VREF*code/(2^bits-1), with loaded-output error.",
        "DAC needs VCC, GND and VREF; every digital bit must have a defined level.",
        "DAC output resistance is 25 ohms in the educational model; do not expect it to drive heavy loads.",
        "Generic DACs are not pin-compatible promises for a named real chip.",
        "Op-amp outputs are clipped to supply rails; negative feedback and valid common-mode range matter.",
        "Comparator output is digital; op-amp output follows its closed-loop analog feedback.",
        "Analog switches need power and an enable signal; ON resistance affects the signal.",
        "Physical bandwidth, noise, settling and stability are not proved by simplified models."],
    "validation": [
        "Use only catalog IDs, known pin indices and declared property names.",
        "Revise existing proposals with deltas; do not duplicate a circuit to fix one parameter.",
        "Inspect geometry, electrical connectivity, parameters, polarity and expected observables separately.",
        "Use simulator faults/warnings to diagnose; a blocked test is not a passed test.",
        "A short probe may miss oscillator startup, long RC transients or intermittent faults.",
        "Firmware tests are manual; never claim that a simulator probe executed board code.",
        "Explain missing hardware models instead of inventing successful behavior.",
        "Do not certify mains wiring or real-world safety from this educational simulator."],
}

RECIPES = [
    ("LED indicator", "led dioda światło", "Source+ -> resistor -> LED A; LED K -> return. R=(Vs-Vf)/I; set colour and resistor power."),
    ("NPN low-side driver", "tranzystor pn2222 npn", "Emitter -> GND; collector -> load negative; load positive -> supply; base via resistor to control. Verify E/B/C."),
    ("Two-transistor astable", "mig blink astabil oscillator", "Two NPN stages: collector resistors/LED loads to supply, emitters to GND, base bias resistors and cross-coupled capacitors from opposite collector to base. Check capacitor polarity during the whole cycle."),
    ("RC delay", "czas delay rc kondensator", "Source -> resistor -> capacitor positive; capacitor negative -> return. Observe capacitor voltage and compare with R*C."),
    ("Potentiometer dimmer", "potencjometr dimmer jasność", "Connect wiper to LED series resistor; other terminals across supply/return. Check maximum current at both travel limits."),
    ("Joystick button", "pad joystick switch sw", "GND -> return; VCC -> supply; SW -> input. Simulator default: released LOW, held HIGH; physical mode: released HIGH with pull-up, held LOW. VRx/VRy need analog inputs."),
    ("Tact input", "tact guzik przycisk button", "One switched side to return; opposite side to input; pull-up input. Same-side tactile pins are internally common."),
    ("Keypad matrix", "keypad klawiatura", "Connect R1..R4 and C1..C4 to scan lines; one row driven at a time, column pull-ups; press closes exactly one row-column pair."),
    ("USB-powered circuit", "usb port lightning zasil", "Connect an external source/power brick to VBUS or POWER and GND. Ports and USB cables are passive; do not use D+/D- as power."),
    ("Linear regulator", "stabilizator regulator", "IN -> source positive, GND -> return, OUT -> load positive. Vin >= Vout+dropout; verify current and thermal dissipation."),
    ("Buck/boost converter", "step buck boost przetworn", "IN+/IN- -> source; OUT+/OUT- -> load. Choose buck/boost/buck-boost; verify requested output, efficiency and limits."),
    ("Bridge rectifier", "ac dc prostownik mostek", "AC+/AC- -> AC source; DC+/DC- -> load; optional rated filter capacitor across output. Model loses two diode drops. AC labels identify terminals, not fixed polarity."),
    ("Logic NOT test", "not bramka logic", "Logic Input -> NOT input; NOT output -> Output indicator. Check both input states and inversion."),
    ("Comparator threshold", "komparator lm393 comparator", "VCC/GND powered; IN+ -> signal, IN- -> reference; OUT pulled up to compatible rail. Check states above/below threshold."),
    ("Parallel DAC", "dac cyfrowo analog digital", "Power VCC/GND, set VREF, drive D0..Dn with defined levels, load OUT lightly. Check code 0, midpoint and full scale."),
    ("Op-amp follower", "wzmacniacz opamp lm324", "Power rails; signal -> IN+; OUT -> IN-; output to light load. Check clipping and model restrictions."),
    ("Active buzzer", "aktywn buzzer", "Rated DC across buzzer positive/negative with return. Switch it through a suitable driver when necessary."),
    ("Passive buzzer", "pasywn buzzer tone", "Alternating/PWM voltage across buzzer; DC does not provide sustained sound. Sample frequency sufficiently."),
    ("PIR input", "pir ruch motion", "Power VCC/GND; OUT -> compatible input. Motion in front of the symbol activates the modeled signal."),
    ("Solar load", "solar słonecz panel", "Panel+/- -> rated load. Test illumination slider at zero, half and full light; simplified voltage model, not real IV behavior."),
]


RULE_GROUPS['planning_and_verification']=[
    'Use task_plan as ordered advice only; validate against the original request and actual catalogue. Plan text never grants host access or execution privileges.',
    'Each task must have an observable check: pin-to-net mapping, voltage/current range, truth table, or layout condition. State when a check is not simulated.',
    'Never claim a supply-only IC model emulates its UART, I2C, CAN, USB, PLL, memory, PWM registers or charging. Explain limitations or request a supported alternative.',
    'Identify bare IC package pin numbers separately from a ready-made breakout module header. Preserve the specified suffix and package.',
    'Open-collector/open-drain outputs need a compatible pull-up; active-low pins are not active-high buttons.',
    'Check GPIO voltage compatibility and source/sink current limits. Never drive an unpowered board input above its rails.',
    'Use series current limiting for LEDs, including when driven by a microcontroller; choose resistor power with headroom.',
    'An AC RMS value is not its peak. In limits mode Vmax must exceed Vmin; unequal limits introduce a DC offset. Check capacitor polarity against the entire waveform.',
    'Continuity and resistance probes require an isolated unpowered measurement path; an open switch must not be treated as a conductive bridge.',
    'Fixed oscilloscope V/div and vertical offset define the trace; do not interpret a clipped trace or changing scale as actual circuit dynamics.',
    'Complete safety-relevant missing requirements by asking the user, not silently guessing. A bounded simulation is not real-hardware certification.',
    'Read simulation_report and repair failed tests on the working proposal. Do not ignore errors, claim success without evidence or duplicate the whole circuit.',
]

def knowledge(prompt):
    lower = prompt.casefold()
    selected = [dict(name=name, design=design) for name, words, design in RECIPES if any(word in lower for word in words.split())]
    return {"version": "1.3.0rc4", "rule_groups": RULE_GROUPS, "selected_recipes": selected[:6],
            "available_recipes": [item[0] for item in RECIPES],
            "scope": "Bundled guidance and electrical conditions, not provider fine-tuning or a safety certificate."}
