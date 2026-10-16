# ElectroSchem 1.2.1 - portable Windows x64 build

Run `ElectroSchem.exe`. Keep the complete `_internal` directory beside it.
No Python installation is required. The executable is unsigned; Windows may
show an unknown-publisher warning.

## Changes in 1.2.1

Creating board code opens a Save dialog for filename and location. It suggests
the component/project-ID filename in the configured default code folder.
Accept it or choose another name and folder. Cancelling creates nothing,
existing files are never overwritten, and assigned code opens directly.
Version 1.2.1 promotes the tested 1.2.1rc1 without functional changes.

## Included and external dependencies

Built with Python 3.14.6, PySide6/Qt 6.11.2 and PyInstaller 6.22.2. Includes
Node.js 22.23.2, AVR8js 0.21.1 and RP2040js 1.4.0 firmware engines, icons,
documentation, examples and license notices.

Arduino Uno/Nano `.ino` compilation requires Arduino CLI and its `arduino:avr`
core. Pico firmware may need a separately supplied 16 KiB boot ROM; none is
bundled. Code editing requires an external editor selected in Settings.
Camera and audio require compatible devices and drivers.

Existing code stays in its original location. Settings remain in AppData.
The source launcher `Lunch_ElectroSchem.bat` is not needed for this package.
See `_internal/docs/SIMULATION.md` for model and emulator limitations.

## Verification and licenses

The frozen EXE is checked outside the source directory, without external Python
or Node on PATH: window, icons, project UUIDs, ELS save/load, LED simulation,
and both bundled firmware engines. Hardware audio and camera are not exercised.

License texts are in `_internal/licenses`, `_internal/node/LICENSE`, and each
emulator package's LICENSE. Qt/PySide6 remain separate, unmodified shared
libraries; replacing and debugging their modifications is not restricted.

Upstream source:

- Python: https://www.python.org/downloads/source/
- Qt: https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/
- Qt for Python: https://download.qt.io/official_releases/QtForPython/pyside6/
- Node.js: https://nodejs.org/dist/v22.23.2/
- AVR8js: https://github.com/wokwi/avr8js
- RP2040js: https://github.com/wokwi/rp2040js

Application source is on `main`; portable versions are on `biults` under
`biult/1.1.1`, `biult/1.2.0` and `biult/1.2.1`. Earlier packages are preserved.
