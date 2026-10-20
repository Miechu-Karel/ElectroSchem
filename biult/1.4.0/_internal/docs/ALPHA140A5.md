# ElectroSchem 1.4.0alfa5

## Changes

- Module symbols use the standard rectangular outline with the element name and
  pin labels; the flame-sensor illustration no longer obscures them.
- Two-terminal DC motors show two terminals rather than the three-terminal
  servo controller artwork. Motor and servo pin labels are moved outside the
  symbol body for readability.
- The default-location open/save menu labels no longer duplicate their
  `Alt+O` and `Alt+S` shortcuts.
- Added a wire-color painting tool between Delete and Draw Wire. Clicking a
  wire opens a color picker and colors that complete routed path, including its
  bends. The chosen color is visual only and has no effect on connectivity or
  simulation.
- Wire colors are stored in ELS format version 5; older application versions
  reject these files instead of silently discarding the new data.

## Verification

Automated coverage checks wire-color persistence and rendering, tool placement,
module appearance, motor/servo pins, and project-format compatibility.
