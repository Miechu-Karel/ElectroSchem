# ElectroSchem

**ElectroSchem 1.0.0** is an offline desktop editor for electronic schematics,
built with Python and PySide6 (Qt). Draw circuits, connect components and
prepare documentation without a full PCB design environment.

Create multi-sheet projects, use built-in symbols or define custom components,
save projects in the **ELS** format and export to **PDF, PNG or SVG**.

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
- Keyboard shortcuts and contextual component information through `H`.

## Scope and limitations

ElectroSchem is a schematic editor, **not a circuit simulator or PCB editor**.
KiCad project import/export is not currently supported. Custom component
behavior descriptions are documentation text, not executable simulation code.

**AI assistance and Gemini datasheet analysis are disabled in 1.0.0.**
They are not accessible through the UI or former shortcuts. Saved API keys do
not enable them. Legacy integration code remains for a future rebuild.

EN/PN profiles use the IEC 60617 symbol family. ISO concerns sheet presentation,
not a separate electrical symbol set. These profiles do not imply certified
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

Alternatively, `uruchom_electroschem.bat` launches Python from
`%LOCALAPPDATA%\Programs\Python\Python314\python.exe`.
That interpreter must also have the required dependencies installed.

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

Release 1.0.0 verification: **151 tests passed**, with 17 historical tests for
the retired AI panel explicitly skipped. Coverage includes ELS files, geometry,
editing, properties, clipboard operations, exports and disabled AI entry points.
