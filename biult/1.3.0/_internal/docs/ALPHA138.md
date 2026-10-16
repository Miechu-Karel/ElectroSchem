# ElectroSchem 1.3.0alfa8

Local development version, not a published stable release.

- Multi-position switch property changes rebuild both drawing geometry and pins.
- USB Help explains VBUS/GND, differential data, shielding, USB-C CC/SBU/TX/RX,
  connection instructions and simulation limits, with USB-IF documentation.
- Raspberry Pi supplied by an external USB source no longer adds a conflicting
  ideal source on that same 5 V rail. GPIO fault detection remains active.
- USB keyboard has no public schematic pins. Its sandbox QWERTY panel accepts
  mouse and physical keyboard input, Polish AltGr characters and Enter. Lines
  go to the single connected simulated Python program, never the host terminal.
  This is educational stdin forwarding, not USB HID packet/OS emulation.
- F on a selected/pointed Pi opens/closes its console; F in the editor opens
  properties. Alt+F toggles Favorites; Shift+F/Ctrl+A then F reuses Favorites.
- New camera, mute/unmute, terminal and Favorites icons use the supplied assets.
- Sandbox examples have separated wire routes; new failure examples demonstrate
  LED overcurrent, resistor power overload and GPIO electrical damage.
- Edited collinear cable overlaps longer than one grid cell (20 scene units)
  are deduplicated, preserving component anchors, branches and shared nets.
  Crossings alone do not connect. Untouched legacy overlapping drawings are not
  silently rewired. A deliberate overlap joins the wires electrically.
- AI proposals still use the stricter half-cell overlap limit. Onboarding tasks
  17–20 set their input fixtures locally and check complete NOT/AND truth tables.
  Completed exercises stay cached; no automatic paid retry or reset is added.

Offline tests use reference responses, not live Gemini/OpenAI requests. They
verify the course and electrical checker, not arbitrary future model answers.
Simulation remains approximate: USB-PD and USB protocol packets are not emulated.
