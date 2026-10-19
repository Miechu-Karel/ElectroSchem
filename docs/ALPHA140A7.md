# ElectroSchem 1.4.0alfa7

## Changes

- Wire-color propagation now follows shared junction IDs as well as matching
  model and rendered endpoint coordinates. This repairs propagation across
  connected segments in existing projects whose saved endpoint coordinates
  differ slightly.
- Servo leads are shortened to exactly two 20-unit grid cells before the
  controller body.

## Verification

Regression tests cover slightly drifted endpoints that retain a shared
junction ID, straight chains, branch stops, pin stops, and servo lead geometry.
