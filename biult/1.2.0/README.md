# ElectroSchem 1.2.0 - portable Windows x64 build

Run `ElectroSchem.exe`. Keep the complete `_internal` directory beside the EXE;
this is a portable folder, not a single-file executable. No Python installation
is needed. Extract or copy the whole folder before starting the application.

Built with Python 3.14.6, PySide6/Qt 6.11.2 and PyInstaller 6.22.2. The executable
is unsigned; Windows may show an unknown-publisher warning.

## Changes in 1.2.0

- Separate default code-folder setting, initially Documents/ElectroSchem/Code.
- Create and assign board code, or link an existing supported source file.
- Detach Code removes references only, not files. Detach before reassigning.
- Code paths wrap inside component properties; no horizontal form clipping.
- X activates the delete tool; Delete removes the selection; Ctrl+X cuts.

Existing code links remain at their original locations. No automatic migration
or deletion takes place. Settings remain in the normal user AppData directory.

## Included

- Editor, analog simulation, Python board APIs, icons, documentation and examples.
- Node.js 22.23.2 and pinned AVR8js/RP2040js firmware engines.
- Qt libraries, multimedia plugins and third-party license notices.

## Optional external dependencies

- Arduino Uno/Nano `.ino` compilation requires Arduino CLI on PATH and its
  `arduino:avr` core. Compiled Intel HEX can be emulated without the compiler.
- Pico firmware using boot ROM routines needs a separately provided 16 KiB
  RP2040 boot ROM. No boot ROM is distributed here.
- Board code editing requires an external editor selected in Settings.
- Camera and audio features need compatible local devices and drivers.

The source launcher `Lunch_ElectroSchem.bat` is not needed for this portable
build. See `_internal/docs/SIMULATION.md` for model and emulator limitations.

## Verification

The frozen EXE is checked outside the source directory with Python and external
Node.js removed from PATH: window creation, icons, distinct project UUIDs, ELS
save/load, LED simulation and both bundled firmware-engine imports. Hardware
audio and camera are not exercised by these checks.

## Third-party notices and source

Included license texts are under `_internal/licenses`, `_internal/node/LICENSE`,
and each emulator package's `LICENSE` file. Qt/PySide6 are supplied as separate,
unmodified shared libraries; replacing them and debugging their modifications
is not restricted by this build.

Upstream component source:

- Python 3.14.6: https://www.python.org/downloads/source/
- Qt 6.11.2: https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/
- Qt for Python: https://download.qt.io/official_releases/QtForPython/pyside6/
- Node.js 22.23.2: https://nodejs.org/dist/v22.23.2/
- AVR8js 0.21.1: https://github.com/wokwi/avr8js
- RP2040js 1.4.0: https://github.com/wokwi/rp2040js

Application source is on `main`. Portable releases are on `biults` under
`biult/1.1.1` and `biult/1.2.0`; the 1.1.1 package is preserved unchanged.
