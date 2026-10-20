# ElectroSchem for Android

## Product scope

The Android app is a touch-first companion to ElectroSchem Desktop. It must
open, edit and save the same `.els` projects and retain the desktop features
that make sense on a phone or tablet. Project files live in a connected cloud
provider; the app must not offer local project files or a code editor.

Keep the existing desktop app and its workflows intact. The Android client is
a separate app that shares the `.els` format and compatibility rules.

## Included capabilities

- Create, open, edit and save multi-sheet `.els` projects in cloud storage.
- Browse the component catalogue, place and edit components, rotate and
  arrange them, draw and edit wires, and add annotations.
- Use the existing electrical checks, simulation, instruments and interactive
  components where they can be operated by touch.
- Change project and sheet properties, select and move objects, undo and redo,
  and export or share supported outputs.
- Use the existing Polish and English interface and project format versions.
- Connect cloud accounts with Android-safe OAuth authorization.

The app has no local project browser, local project save action, code editor,
or source-code assignment workflow. Code-related simulation controls should be
explained as unavailable on Android where a project depends on them.

## Touch interaction contract

Provide a persistent **Multi-touch** setting, stored as an app preference, with
Polish label **Obsługa multi dotyku**. Default it to on. Show its current value
in the drawing toolbar or its immediately accessible overflow menu.

### Multi-touch on

- In cable mode, the first pointer-down fixes the cable start point.
- A second pointer-down fixes the cable end point. Commit the cable when both
  endpoint gestures have completed; show a preview between the fixed points.
- Track each pointer by its stable platform pointer ID from down through up.
  Never substitute a remaining finger when another finger lifts.
- Snap each endpoint independently to pins, wire nodes and the drawing grid.
- Ignore third and later pointers for that cable gesture.
- Outside cable mode, use two-finger pan and pinch zoom; keep one-finger object
  selection, dragging and tools predictable.

### Multi-touch off

- Capture the first pointer that goes down until it is lifted or cancelled.
- Ignore all other pointer IDs, including their movement and lift events.
- In cable mode, the active pointer draws from the start to its release point.
- Do not hand an in-progress gesture to another pointer if the active pointer
  is lifted.

System gesture cancellation, app backgrounding and a touch cancel event must
cancel the in-progress gesture without leaving a partial wire in the project.

## Cloud and account security

The current desktop cloud client uses a desktop callback flow and desktop
settings. Reuse the provider APIs and `.els` compatibility, but implement
Android-compatible OAuth for the mobile application. Register public Android
clients and use Authorization Code with PKCE and the provider's recommended
Android redirect mechanism. Do not embed a client secret in the APK or reuse
desktop refresh tokens. Keep account tokens in Android Keystore-backed secure
storage, and keep unsaved edits in memory only. When offline, clearly show that
changes are unsaved and require a connection before saving.

Support the configured Google Drive and OneDrive providers first. GitHub
desktop-clone synchronization is not a cloud-file API and is not part of the
mobile save flow.

## Implementation direction

Build a native Android client with a touch-first interface and a platform
canvas. Preserve `.els` as the exchange and cloud-storage format. Treat the
existing Python/Qt application as the behavioral and catalogue reference; its
Qt widgets and desktop OAuth callback cannot be reused as the Android UI.

Before implementing feature screens, establish a small cross-platform
compatibility layer around the `.els` schema and catalogue data. Validate
import/export against real project fixtures, including older supported format
versions, custom components, sheet settings, wire junctions and wire colors.
Keep desktop serialization as the reference until shared compatibility is
proven.

## Delivery milestones

1. **Compatibility foundation:** Android project, `.els` read/write, fixture
   round trips, catalogue access, cloud sign-in and cloud project list/open/save.
2. **Editor foundation:** mobile navigation, sheet tabs, catalogue, canvas,
   selection, component placement, properties, undo/redo, annotations and
   exports.
3. **Wiring and touch:** wire snapping and editing, the multi-touch setting,
   stable pointer tracking, pan/zoom, cancellation and gesture regression
   coverage.
4. **Feature parity:** simulation, instruments, interactive components,
   remaining supported desktop tools, accessibility and tablet layouts.
5. **Release readiness:** verify airplane-mode behavior, account disconnect,
   cloud conflicts, large projects, Android versions, Polish/English strings,
   and installation/update packaging.

## Acceptance checks

- A desktop-created project opens on Android and retains supported data after
  editing and saving; the saved project opens again on desktop.
- A project cannot be saved to a local path through the Android interface.
- No code editor or code-file picker is available on Android.
- With multi-touch enabled, two distinct touches in cable mode create exactly
  one cable between those two captured points, without endpoint swapping when
  either finger lifts first.
- With multi-touch disabled, secondary touches do not move the active cable
  endpoint, pan the canvas, select an object or complete a gesture.
- Pin snapping, junction creation, undo and cancellation remain correct for
  both cable gestures.
