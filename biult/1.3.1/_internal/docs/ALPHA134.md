# 1.3.0alfa4 implementation and limits

Local development only; no release executable or GitHub publication.

## Inputs and consoles

Joystick SW defaults to released LOW and held HIGH. The physical contact mode
remains selectable, with an optional 10 kΩ pull-up. Momentary controls always
start released; saved editor properties are not altered by simulation.
Console visibility accepts both legacy boolean and string settings. A click
on an enabled Raspberry Pi console shows/hides its window. Program input is
cooperative and bounded: input(), print(), sys.stdin.readline()/read(),
sys.stdout/stderr.write()/flush(). No shell, host eval/exec, OS commands or
arbitrary Python packages. stdin.read() is a line-input approximation, not
an unbounded byte stream. Python syntax/hardware support remains limited by
the AST runtime. USB keyboard text entry is a powered educational interface,
not USB enumeration/HID packet emulation.

## Power, pins and measurement

All USB/Lightning sockets and USB cables are passive. Legacy sim_power=true
does not create a voltage source. Matching USB-C VBUS contacts are connected,
as are GND contacts; a cable joins each matching A/B conductor. Goldpin has
TOP/BOTTOM contacts for one conductor. The old 1×40 definition remains readable
in old projects but is hidden from insertion menus.

The new power brick is a regulated DC source abstraction. No mains input or
USB PD is emulated. MT64 uses a configurable resistive DC envelope and signed
rotation indicator, not measured winding/motor mechanics. Connector pictures
are decorative silhouettes and do not add invisible electrical terminals.

Voltmeter/oscilloscope probes have 1 TΩ input; the ammeter has a 1 mΩ series
shunt. Never wire the ammeter directly across a supply. Interactive probes
select real schematic terminals; current selects a modeled component branch.
Waveforms retain up to 500 integration samples; display refresh is bounded.
Resistance/continuity use an isolated passive DC conductance calculation with
voltage sources disconnected. Active/nonlinear networks are rejected instead
of assigned a fictitious resistance. This does not inject an ohmmeter signal
into the live simulation and is not a general impedance/LCR measurement.

RFID cards have an eight-hex-digit editable ID. Dragging within 260 scene
units of an RC522 supplies its UID stimulus preview; moving away removes it.
This is still a powered reader envelope, not an RF/SPI/MFRC522 register stack.

## Assets

File > Save as Asset saves selected components with internal wires, or the
whole sheet when nothing is selected. Choose an exposed-net module case or
original circuit placement. Module cases expand into original components for
simulation, keeping external electrical anchors. Copies get independent UUIDs
and references; original code-file references, when present, are retained.
Use Edit definition to customize the case while retaining the exported pin
count/numbering. Definitions are stored atomically in assets.json in the local
ElectroSchem AppData directory and embedded in ELS on placement. Limits: 100
source components, 128 exposed nets, 200 library assets and 5 MB JSON. Nested
definitions are flattened, not dynamically executed. Removing an instance
does not delete the source circuit or code files.

## Assistant preparation

See [assistant documentation](ASSISTANT.md) for the 20 exercises and cost
confirmation. The bundled 64 rules remain in design_knowledge.py; the Polish
user handout is output/Zasady_projektowania_AI.md. No network requests were
made during local testing. A provider response can still fail a practice task,
in which case preparation stops and reports the failure rather than silently
accepting an incorrect circuit.
