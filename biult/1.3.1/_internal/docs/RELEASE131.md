# ElectroSchem 1.3.1

Official stable release promoted from the tested `1.3.1alfa1` build.

- Large selection drags avoid running expensive shortest-route searches on every mouse move. Affected wire routes are recalculated in a background worker after release and applied only if the canvas state is still current.
- Background route results are folded into the drag's existing undo state.
- Dark-theme sheet, grid and title-block brightness are reduced by about 15%.
- The ELS save format remains version 4; older releases that support only versions 1–3 reject these files.

The portable Windows build is available in the `biult/1.3.1` directory and the `exports/v1.3.1` Git branch. See [PORTABLE131.md](PORTABLE131.md) for launch and compatibility notes.
