# ElectroSchem 1.3.0alfa6

Includes unfinished alpha5 work and the follow-up alpha6 requests.

## USB

Kabel USB properties select A, B, Mini-B, Micro-B, C or Lightning for each
end. Drag plugs to compatible sockets on component edges. Each socket accepts
one plug. The sandbox restarts when a connection changes; the editor sheet is
unchanged. The passive cable joins VBUS, GND and available data conductors.
Sockets do not generate power: connect a USB power brick or another external
source. Board sockets connect declared 5V/GND pins, not GPIOs or fictional USB
data pins. No enumeration, USB-PD negotiation or real USB host stack.

## Measurements

The simulator tool opens a movable multimeter and two draggable probes. Probes
snap to component pins or cable segments. Voltage AC is time-weighted RMS over
two periods of the slowest modeled AC source; initial partial windows settle
as samples arrive. DC readings remain signed. Oscilloscopes show instantaneous
voltage, with a bounded 500-sample history. A branch current reading is not a
physical parallel ammeter short.

Resistance and continuity work on unpowered passive networks. Resistance-only
schematics with an ohmmeter/continuity tester can run without a voltage source;
no load current is injected. A lamp uses R=Vnom²/Pnom, its modeled hot resistance,
not a measured temperature-dependent cold filament curve. Ratings are required.
The UI refuses a live network with voltage or nonzero load current; merely
having zero current at an AC zero crossing is not permission to measure a live
circuit. Continuity below 10 ohms beeps when sound is not muted. Audio depends
on a working output device and never changes the system volume.

## Editing and AI

The adjustable Bateria retains its old stable library ID. Goldpin has a square
shifted by half a grid cell, leaving unequal leads. A multi-position switch has
COM and 1–10 selectable outputs, plus OFF. Lowering the output count adjusts an
invalid selected position. Custom-library LMB places an item; RMB edits/removes
its definition. Unboxed assets use persistent group IDs; Shift-click bypasses
group dragging, duplication creates a new independent group. Two wire segments
joined at a bend have no dot; branch nodes and component anchors keep their dots.
New editor/AI connections route around collinear overlaps greater than half a
cell. Imported older routes are preserved rather than silently altered.

Before API requests, consent describes provider, model, request count, shared
data and billing uncertainty. OpenAI API billing is separate from ChatGPT;
Gemini may have a Free Tier or Paid Tier. No exact price is invented. Known
declared ADD_COMPONENT properties are converted to separate SET_PROPERTY
commands; unknown arguments still fail with named diagnostics. Gemini may
retry once after a server error and use one fallback model after 404/503 (up
to three generation attempts); the cost dialog explicitly discloses this.
OpenAI does not automatically retry. The exercise-13
case is covered offline with LED color arguments; the original live response
was not available. Verified course progress remains saved. No paid API test.

Sandbox examples include AC/RMS/oscilloscope, unpowered lamp resistance and
continuity, and Raspberry Pi LED blinking with built-in Python GPIO code.
