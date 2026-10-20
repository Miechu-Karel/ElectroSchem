# ElectroSchem 1.4.0alfa6

## Changes

- Servo bodies are shifted right, their pin leads are longer, and signal names
  are shown once above the leads rather than duplicated beside them.
- Default-project menu labels are shorter so the Alt+O and Alt+S shortcuts no
  longer collide with the text.
- The wire-paint tool asks for a color once when enabled and remembers it for
  later activations and application sessions.
- Painting follows a connected wire chain only across a node with exactly one
  other wire. It stops at component pins and branches. The selected path color
  remains visual only and does not change electrical behavior.
- Wire appearance continues to be stored in ELS format v5.

## Verification

Focused regression tests cover the servo layout, menu labels, persistent paint
color, and propagation behavior at straight joins, branch nodes, and component
pins.
