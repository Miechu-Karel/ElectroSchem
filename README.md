# ElectroSchem

**ElectroSchem 1.2.1** is an offline desktop editor for electronic schematics,
built with Python and PySide6 (Qt). Draw circuits, connect components and
prepare documentation without a full PCB design environment.

Create multi-sheet projects, use built-in symbols or define custom components,
save projects in the **ELS** format and export to **PDF, PNG or SVG**.

### Stable release 1.2.1

Version 1.2.1 promotes the tested 1.2.1rc1 without functional changes.

Creating board code now opens a Save dialog for both filename and location.
The suggested filename contains the component/project ID, and the initial
folder follows the code-folder preference. Accept the suggestion or choose
your own name and destination. The board determines the `.py` or `.ino`
extension. Cancel creates nothing; existing assigned code opens directly.
Selected destinations never overwrite existing files.

### Stable release 1.2.0

Version 1.2.0 promotes 1.2.0rc1 without functional changes. Portable Windows
releases are available on the `biults` branch under `biult/1.1.1` and
`biult/1.2.0`, with the latest patch in `biult/1.2.1`. Keep each EXE with its matching `_internal` directory. The `main`
branch contains source code, not portable build folders.

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
