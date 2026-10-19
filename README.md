# ElectroSchem

**ElectroSchem 1.4.0** is a desktop editor for electronic schematics, built
with Python and PySide6 (Qt). Draw circuits, connect components and prepare
documentation without a full PCB design environment.

Create multi-sheet projects, use built-in symbols or define custom components,
save projects in the **ELS** format and export to **PDF, PNG or SVG**.

### Latest stable release 1.4.0

Version 1.4.0 promotes the tested 1.4.0rc2. Floating wire ends show a node
unless connected to a component pin or another wire. It also includes the
wire-color tool, local GitHub synchronization (commit on each project save;
manual push/pull), and Google Drive/OneDrive setup guides. The portable
Windows build is published on the [`exports/v1.4.0` branch](https://github.com/Miechu-Karel/ElectroSchem/tree/exports/v1.4.0).
See the [release notes](docs/RELEASE140.md), [GitHub setup guide](docs/GITHUB_SYNC.md),
and [cloud setup guide](docs/CLOUD_SETUP.md).

### Release-candidate history: 1.4.0rc2 and 1.4.0rc1

RC2 refreshes isolated-end markers after connection changes; RC1 removed
Dropbox and Nextcloud, ordered the remaining cloud providers, and added a
commit for each successful project save. See the [RC2 notes](docs/RC1402.md)
and [RC1 notes](docs/RC1401.md).

### Previous stable release 1.3.1

Version 1.3.1 promotes the tested 1.3.1alfa1. Large schematic selections
remain responsive during movement, with affected wires rerouted after release
in a background worker. The dark-theme sheet, grid and title block are dimmed
by about 15%. See [1.3.1 release details](docs/RELEASE131.md).

### Previous stable release 1.3.0

Version 1.3.0 promotes the tested 1.3.0rc25. It includes the **Terminale**
submenu for terminal blocks, ELS format v4 saves, and the other RC25 features.
See [1.3.0 release details](docs/RELEASE130.md).

### Previous release candidate 1.3.0rc25

RC25 added the **Terminale** submenu under **Kable i złącza**. See
[RC25 details](docs/RC1325.md).

## Previous development versions

### Previous development version 1.3.0rc24

RC24 removes the intermediate **Przyrządy pomiarowe** submenu, so instruments
open directly. **Kable i złącza** now has **Porty USB**, **Goldpiny** and
**Kable** subcategories. New saves use ELS format v4, which older releases
reject instead of opening. The bilingual usage instructions have been updated.
See [RC24 details](docs/RC1324.md).

### Previous development version 1.3.0rc23

RC23 moved the measurement-tools and interactive-components categories to the
bottom of the component sidebar and moved the RFID card markings upward. See
[RC23 details](docs/RC1323.md).

### Previous development version 1.3.0rc22

RC22 moved interactive components below measurement tools in the library and
stacked the card ID above its “RFID” marking to the right of the chip. See
[RC22 details](docs/RC1322.md).

### Previous development version 1.3.0rc21

RC21 adds interactive components with draggable RFID cards, matches, ultrasonic
reflectors, PIR person props and an IR remote, plus sensor stimulus sliders,
physical-looking simulation props, and square navigation/numeric keyboard keys.
See [RC21 details](docs/RC1321.md).

### Previous development version 1.3.0rc20

RC20 stabilizes routing while moving shared wire junctions and removes spurious
short elbows. It retains RC19's independent wire-drawing gestures and visible
nodes at isolated floating ends. Full application testing is pending. See
[RC20 details](docs/RC1320.md).

### Previous development version 1.3.0rc19

RC19 cancels wire drawing after each completed segment, shows nodes at isolated
floating wire ends, and debounces canvas fitting while minimizing/restoring.
See [RC19 details](docs/RC1319.md).

### Previous development version 1.3.0rc18

RC18 stabilizes the wire-drawing bend, fixes junction-dot display for
non-branching connections, updates measurement guidance, refines the assistant
status/buttons, and adds a voltage cursor and finer time/division steps to the
oscilloscope. See [RC18 details](docs/RC1318.md).

### Previous development version 1.3.0rc17

RC17 preserves and validates the selected OpenAI model, refreshes the obsolete
AI help text for the currently exposed question-and-answer interface, and adds
regressions for the release, current assistant controls, and asset case tests.
See [RC17 details](docs/RC1317.md).

### Previous development version 1.3.0rc16

RC16 recalculates moved wires to the shortest legal route whenever their
endpoints move, whether dragged directly, moved with a component, or moved as
part of a selection. See [RC16 details](docs/RC1316.md).

### Previous development version 1.3.0rc15

RC15 aligns custom-asset interaction and light windows with their live
components, fixes case-editor stroke origins, and formats resistance readings
with SI prefixes. See [RC15 details](docs/RC1315.md).

### Previous RC10 changes

RC10 restores introductory AI exercises and retries invalid AI proposals. See
[RC10 details](docs/RC1310.md).

### Previous RC9 changes

RC9 added asset-case selection and interaction validation, internal-part property permissions, and fixes to asset illumination and GPIO/PWM execution. See [RC9 details](docs/RC1309.md).

### Previous RC8 changes

RC8 merges IN/OUT tools into one grid-snapped PIN tool, adds an editable
selection area and terminal stems, and improves light/interaction target
selection in asset cases. Pencil drawings save as an outer envelope.
Wire stretching removes redundant bends and loops; cable plugs stay within
the editor drawing area. Local AI supports protected API tokens and specific
authentication diagnostics; AI errors can be copied. See [RC8 details](docs/RC1308.md).

### Previous RC7 changes

RC7 allows free placement of case terminals. Shift constrains rectangles to
squares and ellipses to circles. Saved cases display the union of their shapes,
without inner construction edges, and remain visible in the simulator while
their internal circuit is solved. Case light windows and interaction regions
can be assigned to internal components. See [RC7 details](docs/RC1307.md).

### Previous RC6 changes

RC6 adds Paint-style case tools: freehand pencil, Shift straight lines,
rectangles/circles, erasing, undo, and explicit IN/OUT terminals connected to
chosen internal pins. New cases start without autogenerated terminals.
Legacy 45-degree wires retain their angles when stretched; dragging uses
the original gesture geometry rather than accumulating bends frame by frame.
See [RC6 usage and limitations](docs/RC1306.md). This is still a release candidate.

### Previous RC5 changes

RC5 adds a native asset case editor with rectangles, circles, shape erasing,
exported-pin positioning and a visual circuit miniaturizer. Saving an asset now
requires selecting its components. Hold Shift+S to see faint wires beneath
cases, or enable this permanently in editor settings. Jumper housings are slim,
goldpins regain their previous appearance, and assistant routing prefers
orthogonal paths with penalties for crossings. See [RC5 details](docs/RC1305.md).

### Previous RC4 changes

RC4 adds an editable, isolated proposal preview: move and rotate parts, save to
the proposal, then Accept to transfer the changes into the actual project.
The assistant has a question/explanation mode with editing blocked, plus a local
readability report and better routing preferences. Sound cycles on the large
button, probes start free, and cable edits preserve simulation time and device
state. Rotation direction is configurable. See [RC4 details](docs/RC1304.md).

### Previous RC3 changes

RC3 adds a tested educational USB-C five-output reference to assistant examples
and offers it on an empty sheet after explicitly confirming its assumptions.
Scope controls sit beside each instrument. A 104-key simulator keyboard has
one-shot modifiers, I2C addresses use hexadecimal input, sound offers 50% and
25%, and cables/connectors sit directly below electronics with the supplied icon.
Breadboard is no longer offered. Cable plug housings are rectangular with USB
ports inside them. See [RC3 details and limitations](docs/RC1303.md).

RC2 removes the drawn-wire/jumper mode selector and two-click automatic jumper
creation. Cables remain in their own category and can still be plugged by dragging
their ends. An offline bilingual local-AI tutorial is available in Settings → AI
and Usage Instructions: Ollama / LM Studio setup, model sizes, memory/context,
privacy, limitations and troubleshooting. No models are downloaded automatically.

RC1 adds a selectable drawn-wire/jumper connection mode and a mini breadboard,
with a separate cable category, visible secondary buzzers in Sound, cable-only
goldpin plug contacts, and unified monochrome connector graphics. Scope controls
are embedded directly in the simulator. H shows pin details, model limits and
documentation links. Planning questions are scoped to each request, with numeric
power-budget checks and explicit USB-PD/current-limiting limitations.
See [RC1 details and test notes](docs/RC1301.md).

Alpha11 adds triggered, stationary oscilloscope acquisitions, live voltage/time
scales and defaults with optional automatic scaling of both axes. A laboratory
CV/CC supply is adjustable in the sandbox. USB and male/female jumper cables can
be plugged in the editor and simulator. AI consent is remembered, conversation
cards support editing/stopping. RC1 rechecks clarification before drawing.
See [alpha11 details and limitations](docs/ALPHA1311.md).

Alpha10 fixes continuity measurements and adds their audible signal, functional
IC names and smaller categories, NE567, clickable AI error explanations and a
separate planning stage. Oscilloscopes have a fixed adjustable vertical scale
and selectable display sizes; AC sources support RMS or explicit voltage limits.
Simulation can stop on failure or continue unaffected electrical islands.
See [alpha10 details and limitations](docs/ALPHA1310.md).

Alpha9 adds 29 named IC packages with documented educational model limits,
E inspection/actions, restored F Favorites, upright switch labels, corrected
USB socket/Goldpin geometry, optional OFF positions, safe proposal regeneration
and a loopback-only local AI adapter. See [alpha9 details](docs/ALPHA139.md).

Alpha8 fixes USB-powered Pi rails and switch geometry updates, adds a clickable
USB keyboard, useful USB pin help, refreshed toolbar icons and three failure
examples. E opens component properties in the editor or performs an action in the
sandbox; F toggles Favorites. Shared edited cable stretches longer than one
grid cell become one electrical wire; examples and AI routing avoid overlaps.
Course task 18 now applies its input fixture and checks the entire truth table.
See [alpha8 details and limitations](docs/ALPHA138.md).

Alpha7 added Favorites (F / Shift+F), searchable category labels, selectable AC
waveforms, a USB-C LED example and common-centre asset rotation. Unpowered
passive islands run without a supply; LED/diode resistance uses a virtual
1 mA / 3 V meter and is polarity-dependent. USB cable/power-brick contacts are
internal, board sockets occupy a separate bottom strip, and AC/DC converters
use AC+, AC-, DC+, DC- labels without changing saved physical pin numbers.
See [alpha7 details and limitations](docs/ALPHA137.md).

### Previous development version 1.3.0alfa6

Alphas 5–6 add configurable draggable USB plugs and edge sockets, a moving
multimeter with two probes, AC RMS readings, a continuity beep and oscilloscope
plots. Passive resistance-only circuits run without an external supply.
The adjustable battery is named Battery. Goldpin has asymmetric leads;
multi-position switches have 1–10 outputs. Unboxed assets move together,
with Shift for individual movement and independent groups after duplication.
Instrument menus are flat and simulation tool buttons are compact squares.
AI requests display provider/model, request count, shared data and billing
information; declared ADD properties are normalized into SET_PROPERTY commands.
New wire routes avoid overlaps longer than half a grid cell.
See [alpha6 details and limitations](docs/ALPHA136.md).

Joystick SW now defaults to released LOW / held HIGH, with physical active-LOW
contact mode available in its properties. USB sockets/cables are passive: a
separate power source is required. New parts include a six-position switch,
two-ended gold pin, USB cable/keyboard/power brick, an educational MT64 motor
and five schematic measurement instruments. Measurement tools have a dedicated
sidebar category and live probes/waveforms in the sandbox. RFID card IDs are
editable and cards can be dragged near an RC522 for UID preview (not RF/SPI).

Settings are grouped into General, Editor and code, AI and Simulation tabs.
The AI button is shown when an AI provider is selected; the editor terminal is
hidden. Raspberry Pi consoles open on board clicks and support cooperative
program `input()` and
`sys.stdin/stdout/stderr`, not unrestricted Python or an operating-system shell.
USB keyboards provide text entry when powered and connected to a simulated
Python board; no USB HID host stack is emulated.

File > Save as Asset stores a selected circuit (or the whole sheet) for reuse
across projects. Place original circuit copies or a configurable module case;
simulation expands cases into their original circuits. Assets are bounded JSON,
not executable plugins. See [alpha4 details](docs/ALPHA134.md).

Before its first project request, AI can run 20 actual provider exercises after
separate cost consent. Commands are electrically checked and successful
examples cached locally for later prompts. Preparation can be cancelled and
resumed; a failed exercise does not count. No provider weights are trained.
Live provider onboarding has not been tested using paid API requests.

Held tact/keypad/joystick contacts now release with the mouse. Raspberry Pi
GPIO input pull-ups/pull-downs are modeled, including gpiozero button polarity.
USB and Lightning connectors receive power only through external sources.
Parallel DACs (8, 10 and 12 bits) have a dedicated menu. Click the proposal
thumbnail to inspect it. AI receives 65 bundled design conditions and 20
topic-selected circuit recipes. Live pacing adapts the integration step within
frequency and reactive limits and displays actual measured speed; hardware
compute limits remain visible rather than falsifying simulated time.

Provider settings offer Gemini, OpenAI, Local AI or None, with a provider-aware
key field and an editable OpenAI model ID. The current assistant interface
answers questions and explains concepts; circuit generation and the editor
command terminal are hidden. Power menus are split into smaller groups. Tact
and joystick presses have visible feedback; the joystick also has a clickable
SW button.

The editor and simulator work offline. Optional cloud AI uses Gemini or OpenAI
with separate, locally protected API keys and explicit transfer consent; local
AI requires a model server that the user has already started. No API key is
included in project files. The AI button disappears when the provider is set to
None. Settings includes a local-AI setup guide.

This alpha adds momentary tact/keypad inputs, mouse-motion PIR, a draggable
joystick, a solar-panel illumination slider, a Raspberry Pi Python-output
console, USB/Lightning contacts, AC/DC and DC/AC conversion, buck/boost models,
regulators, a parallel DAC, LM393, LM324, CD4066, Grove LSM6DS3 and a passive RFID
card preview. Simulation parameters have separate numeric/unit fields; C selects
comments and module names can be copied from properties.

See [AI and command safety](docs/ASSISTANT.md) and [simulation limitations](docs/SIMULATION.md).
Grove motion/I2C registers and RFID radio/SPI protocols are not implemented in
this alpha. Portable builds remain at the latest stable release, **1.2.1**;
the alpha has not been published.

### Stable release 1.2.1

Version 1.2.1 promotes the tested 1.2.1rc1 without functional changes.

Creating board code now opens a Save dialog for both filename and location.
The suggested filename contains the component/project ID, and the initial
folder follows the code-folder preference. Accept the suggestion or choose
your own name and destination. The board determines the `.py` or `.ino`
extension. Cancel creates nothing; existing assigned code opens directly.
Selected destinations never overwrite existing files.

### Stable release 1.2.0

Version 1.2.0 promotes 1.2.0rc1 without functional changes. Earlier portable
builds remain on the `biults` branch; versioned exports are kept in their own
`exports/vX.Y.Z` branches, including `exports/v1.3.0` and `exports/v1.3.1`.
Keep each EXE with its matching `_internal` directory. The `main` branch
contains source code, not portable build folders.

### 1.2.0rc1 changes

**X** activates the delete tool without removing the current selection.
**Delete** removes the selection; **Ctrl+X** still cuts. Text fields retain
normal typing behavior.

### 1.2.0alfa2 changes

Assigned code cannot be replaced directly: the assignment button becomes
**Detach Code**, which removes references without deleting any files. Detach
before assigning another source. Long code paths wrap inside the properties
dialog. The X shortcut is corrected in 1.2.0rc1 as described above.

### 1.2.0alfa1 changes

Settings now include a separate default code folder, initially
`Documents/ElectroSchem/Code`. New board code is created there, isolated by project
UUID and board identity. Existing files stay where they are; changing the setting
does not move or overwrite them. Component properties offer **Create and Assign
Code** when no file is linked, **Edit Code** otherwise, and **Assign Existing Code**
directly below it. Assigning a file links its original path without copying or
executing it. Python `.py` works with the supported board APIs; `.ino` compilation
is limited to Arduino Uno R3 and classic Nano.

### 1.1.1alfa1 fixes

Project IDs are now persistent UUIDs, not title hashes. Two newly created projects
with the same title have different IDs; renaming or saving a copy retains the ID.
Older ELS documents receive a stable migrated identity that is stored on the next
save. New Python code files are empty, and existing source links are preserved.

### 1.1.1alfa2 fixes

The switch label is shortened to Switch / Łącznik without changing its library ID.
The sandbox automatically lowers the time step for higher AC frequencies; sampling
errors no longer trigger component explosions. Genuine overvoltage still causes faults.

## Features

- A 5 × 5 mm snapping grid, 90° component rotation and wire routing in 45° increments.
- Connections to pins and junctions, movable wire endpoints and group editing.
- Passive components, semiconductors, logic gates, ICs, sensors, modules,
  actuators and development boards, including Arduino, ESP32 and Raspberry Pi.
- Custom component creation, editing and deletion; definitions stored with the project.
- Readable reference IDs, multiline names, values, units, automatic SI prefix
  scaling and optional label visibility.
- Multiple A0–A5 sheets, portrait/landscape orientation, margins and title blocks.
- Direct title-block editing for project title, sheet name and author;
  modification timestamps and on-sheet text annotations.
- Copy, cut, paste, duplicate, undo and redo.
- Export all sheets to PDF or the current sheet to PNG/SVG.
- English and Polish UI, configurable default paper size, grid contrast,
  file directory and external code editor.
- Consistent light and dark UI themes, light schematic paper and a dark simulation sandbox.
- Windowed, maximized (default) and fullscreen modes for the editor and simulator.
- Keyboard shortcuts and contextual component information through `H`.
- A separate dark simulation sandbox (`F5`), editable model parameters,
  voltage/current inspection, LED/lamp glow and fault diagnostics.
- ON/OFF switches, incandescent lamps and sinusoidal AC voltage sources.
- Supply rails that power circuits relative to GND, plus transistor, potentiometer,
  relay, logic, timer, driver and sampled SPI peripheral models. See the
  [model coverage and limitations](docs/SIMULATION.md) for the exact scope.
- A subtle dotted grid when normal grid contrast is disabled.
- Improved transistor oscillator convergence, reproducible capacitor startup
  and non-blocking capacitor reverse-polarity warnings.
- Optional local AVR8js / RP2040js firmware execution, GPIO co-simulation and
  source-file links to the configured external editor.
- Per-board editable GPIO scripts, including Raspberry Pi 5 digital-pin
  simulation (not full CPU/OS emulation); code stored under AppData.
- Logic Input/Output components, independent circuit islands, resumable healthy
  circuits after faults and a wall-clock-based time-scale control.
- Brighter LED indicators, configurable fault effects with a silent Gentle mode
  and optional sudden flash/sound; a configurable default author.
- Persistent, opt-in component value defaults, nominal 9 V batteries, compact
  property forms, readable board-code filenames and comments in simulation.
- Tightly bounded, grid-aligned logic I/O with matching framed numeric indicators
  and a subtle white glow when HIGH.
- Gentle, Medium and Strong fault effects: silent red glow, local sparks/smoke with
  a short bang, or a window flash with synthesized ringing. Esc cancels effects.
  Strong is the default for new settings; existing preferences are preserved.
  Gentle or Medium is recommended for people with photosensitive epilepsy.
- Project-scoped code filenames and editable multi-file board code folders.
- Arduino Uno/Nano .ino compilation and AVR execution, Python GPIO/I2C/LCD APIs,
  a visible 16x2 LCD and consent-gated local device-camera preview.
- Polish LCD text in UTF-8 or Windows-1250; one decoded character per cell.
- Interactive potentiometer and 4x4 keypad controls, plus audible active/PWM buzzers.
- 145 selectable components, including [inventory additions](docs/INVENTORY.md).
  All have explicit simulation models or documented educational simplifications.

## Scope and limitations

This release adds an **experimental, limited circuit simulator**, not a
production SPICE replacement or a PCB editor. The functionality database
explicitly lists supported and unsupported components. Unsupported devices
block simulation when connected. Completely loose non-reference components are
excluded from connected circuits with a warning instead of blocking them.

Integrated firmware targets are **Arduino Uno R3, classic Nano and the RP2040
core of Pico/Pico W**. Other boards have digital GPIO script simulation but
do **not** yet have full firmware/OS emulator integrations. Pico W networking is not emulated. See
[Simulation and emulator limitations](docs/SIMULATION.md) before use.

Uno/Nano sketches use **Arduino CLI + arduino:avr**, installed separately or
provided locally under `.tools/arduino-cli`. Compiling never uploads to a board.
Raspberry Pi Python supports specific simulated APIs and local helper modules;
it is not unrestricted CPython, Raspberry Pi OS or compatibility with every
library. LCD I2C writes are transaction-level and require correct wiring.
Camera preview uses Qt Multimedia after per-session consent; it is not a
USB/CSI or firmware camera-driver emulator and does not record or transmit frames.

KiCad project import/export is not currently supported. Custom component
behavior descriptions are documentation text, not executable simulation code.

**AI assistance and Gemini datasheet analysis remain disabled.**
They are not accessible through the UI or former shortcuts. Saved API keys do
not enable them. Legacy integration code remains for a future rebuild.

EN/PN profiles use the IEC 60617 symbol family. ISO concerns sheet presentation,
not a separate electrical symbol set. These profiles draw rectangular resistors
and logic gates. IEEE/ANSI selects zigzag resistors and distinctive gate shapes.
Pin positions and connections do not change. These profiles do not imply certified
compliance with every applicable standard. Check the circuit and exact device
pinout before building hardware; see [Library and pinout notes](docs/PINOUTS.md).

## Getting started

Development and release testing use **Windows, Python 3.14 and PySide6**.
Dependencies are listed in `requirements.txt`. From the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Alternatively, `Lunch_ElectroSchem.bat` launches Python from
`%LOCALAPPDATA%\Programs\Python\Python314\python.exe`.
That interpreter must also have the required dependencies installed.

### Optional firmware emulators

The schematic editor and analog simulation need only the Python requirements.
Firmware emulation additionally requires **Node.js 22 or later** and the pinned
local packages. No package-install scripts are executed:

```powershell
cd app/simulation/emulators
npm ci --ignore-scripts
```

For Uno/Nano, link a real .ino sketch and choose Restart or Reload from editor:
Arduino CLI compiles it locally. Alternatively assign Intel HEX. Compile Pico
firmware externally and assign RP2040 UF2 in `Tools → Simulation sandbox → Firmware emulators`.
Pico firmware that calls ROM routines additionally needs an external 16 KiB
boot ROM selected with **Pico ROM…**; no ROM is bundled.
Firmware is not executed when opening an ELS file; starting execution requires
an explicit Run/Load action. No cloud compilation or external API is used.

## Basic controls

The library is on the left, tools on the right and sheet tabs at the bottom.
Double-click a component to edit its properties. Double-click a sheet tab to
rename or delete the sheet.

| Control | Action |
| --- | --- |
| Left click | Select an object |
| Right-button drag | Rectangle selection |
| Hold the middle mouse button | Pan the view |
| Right click while drawing | Cancel the wire |
| `S` / `D` / `R` | Select / draw wire / rotate |
| `Del` | Delete selection |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` / `Ctrl+D` | Copy / cut / paste / duplicate |
| `Ctrl+Z` / `Ctrl+Y` or `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` | New / open / save / save as |
| `Ctrl+A`, then `A` | Combined add menu |
| `Shift+A`, then `S` | Add a sheet |
| `H` | Information about the selected object |

Shortcuts containing “then” are key sequences, not simultaneous three-key
combinations. Additional category shortcuts are listed under **Options → Help**.

## Projects and preferences

An `.els` file is an ElectroSchem container: a ZIP package with a manifest and
JSON data. It stores sheets, components, connections, annotations and custom
definitions. It is not encrypted. Project saving is atomic.

Preferences are stored separately in `%APPDATA%\ElectroSchem`.
The initial open/save directory is the system Documents folder and can be
changed in Settings.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Coverage includes ELS files, geometry, editing, properties, clipboard operations,
exports, disabled AI entry points, numerical circuit checks, firmware execution
and GPIO-to-LED integration. Historical tests for the retired AI panel remain
explicitly skipped; firmware tests skip when optional Node dependencies are absent.
