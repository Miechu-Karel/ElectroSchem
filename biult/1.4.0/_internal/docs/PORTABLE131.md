# ElectroSchem 1.3.1 - portable Windows x64 build

Run `ElectroSchem.exe` and keep the complete `_internal` directory beside it.
No separate Python installation is required. Windows may show an
unknown-publisher warning because the executable is unsigned.

This is the official 1.3.1 release. It includes the editor, simulator,
firmware engines, icons, documentation, examples and required license notices.
New `.els` saves use format v4; older application releases that understand
only v1-v3 will reject them.

Arduino Uno/Nano `.ino` compilation needs Arduino CLI and the `arduino:avr`
core. A separately supplied RP2040 boot ROM may be needed for some Pico
firmware. Camera and audio features need compatible local devices and drivers.
Settings and user files stay outside this portable folder.

See `_internal/docs/SIMULATION.md` for simulator limitations and the root
`README.md` for release history.
