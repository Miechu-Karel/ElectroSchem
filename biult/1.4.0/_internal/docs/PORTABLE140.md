# ElectroSchem 1.4.0 — portable Windows x64 build

Run `ElectroSchem.exe` and keep the complete `_internal` directory beside it.
No separate Python installation is required. Windows may show an
unknown-publisher warning because the executable is unsigned.

This is the official 1.4.0 build, promoted from 1.4.0rc2. It includes the
editor, simulator, icons, examples, release documentation and the required
runtime files. New project files use ELS format v4; older versions that only
support formats v1-v3 reject them.

GitHub synchronization uses Git for Windows and the account's configured Git
credential helper. Google Drive and OneDrive require the provider credentials
described in the in-app Cloud settings guide. Neither cloud credentials nor
GitHub tokens are bundled with the application.

Arduino Uno/Nano `.ino` compilation needs Arduino CLI and the `arduino:avr`
core. A separately supplied RP2040 boot ROM may be needed for some Pico
firmware. Camera and audio features need compatible local devices and drivers.
Application settings and user project files stay outside this portable folder.

See `_internal/docs/RELEASE140.md`, `_internal/docs/SIMULATION.md`, and the
in-app **Usage Instructions** for release details and limitations.
