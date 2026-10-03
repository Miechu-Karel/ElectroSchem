# Simulation - 1.2.0

## Stable release 1.2.0

Version 1.2.0 promotes 1.2.0rc1 without functional changes.

## Changes in 1.2.0rc1

- X activates the delete tool without deleting the selection. Delete still
  removes the selection, Ctrl+X cuts, and text fields handle typing normally.

## Changes in 1.2.0alfa2

- Assigned boards show Detach Code with the delete icon instead of Assign Existing
  Code. Detaching removes source/workspace/compiled-firmware references only;
  files remain untouched. Detach first to assign a different entry point.
- Long paths wrap within the properties form instead of widening it offscreen.
- The X shortcut is corrected in 1.2.0rc1 as described above.

## Changes in 1.2.0alfa1

- A separate default code-folder preference controls new board source/workspace
  creation; default: Documents/ElectroSchem/Code. Settings remain in AppData.
- Existing source links stay intact, even after changing the default folder.
  No automatic migration, moving or deletion of old code takes place.
- Board properties show Create and Assign Code when unassigned, otherwise Edit
  Code. Assign Existing Code directly below links a .py or supported Arduino .ino
  entry point without copying it or running it. The assigned path is visible.

## Stable patch release

Version 1.1.1 promotes 1.1.1alfa2 unchanged except for the release version.

## Changes in 1.1.1alfa2

- The switch is labeled Switch / Łącznik, retaining its legacy library ID and pins.
- The sandbox lowers the integration step automatically for AC frequencies and
  crystal oscillators. Frequency is not capped at 50 Hz; at least 50 samples per
  cycle remain required. Very high frequencies can exceed the supported minimum
  step or run slower than real time.
- Sampling configuration errors pause simulation without marking components as
  damaged or triggering an explosion. Physical overvoltage faults remain active.

## Changes in 1.1.1alfa1

- New projects receive a persistent UUID stored in ELS, independent of title.
  Legacy documents derive a stable UUID from their sheet identifiers on load;
  it is stored on the next save. Renaming or saving a copy retains identity;
  creating a new project assigns a new UUID even when its title is identical.
- New Python entry points are empty. Existing linked code and helper folders
  remain untouched; unassigned code is not imported from unrelated legacy paths.
- New filenames use `<component-ID>_<project-UUID-without-hyphens>_code.py`.

## Stable release

Version 1.1.0 promotes rc10 without changing simulation behavior. The development
history below documents the implemented features and their limitations.

## Changes in rc10

- After the strong-fault flash ends, ringing holds its level for 1.5 seconds,
  then fades linearly over the next 1.5 seconds. Total duration is unchanged.

## Changes in rc9

- Strong-fault ringing fades over its final second instead of its final 0.25
  seconds. The flash and total sound duration are unchanged: ringing still ends
  3 seconds after the flash.

## Changes in rc8

- Strong-fault ringing ends 3 seconds after the flash, rather than 5.
- The decoded LCD model supports Polish uppercase/lowercase text, with UTF-8
  (default) and Windows-1250 byte decoding. Python RPLCD write_string sends UTF-8
  and normalizes combining marks; each decoded character occupies one of 16 cells.
  This is a simulator text extension, not emulation of a real LCD character ROM
  or CGRAM. Other display models still have supply-only previews without text APIs.

## Changes in rc7

- Completely loose non-reference components are excluded when a connected circuit
  is present. They remain visible on the schematic and sandbox with a warning.
  Connected invalid components are still validated, and named rails/GND retain
  their global reference semantics. Deliberate stand-alone simulations remain supported.
- Buzzer output volume doubles from 15% to 30% of the application audio sink;
  operating system volume is unchanged and the mute control remains available.
- Passive buzzers report prolonged DC drive instead of silently suggesting that
  a steady tone should work. The supplied switch/+5 V test has no periodic source.
  Use a driven passive buzzer (PWM/AC) or an active buzzer for DC-powered sound.

## Changes in rc6

- Potentiometers have sandbox dials that change the two wiper resistances,
  preserving total resistance. LED brightness follows the solved current.
- Keypads have enlarged 4x4 momentary buttons with real row/column contacts;
  holding a key closes its contact, releasing opens it. Source projects are unchanged.
- Active buzzers synthesize a configurable tone when powered. Passive buzzers
  estimate the drive frequency from sampled rising edges (20 Hz-10 kHz);
  constant DC is silent. This is educational tone synthesis, not piezo acoustics.
  Resolve pulse edges with the simulation time step. Audio can be muted and stops
  on pause, reset, fault and close; output volume is limited without changing the
  operating system volume. Buzzers no longer produce LED glows.
- Default-name and default-value checkboxes now identify their separate scopes.

## Changes in rc5

- Larger simulator-only OLED (128x64), TFT (128x160), e-paper (250x122),
  MAX7219 (8x8) and WS2812B (16x16) previews, with screen aspect ratios and
  individual LED cells. Schematic sizes, pin positions and project data are unchanged.
- These five peripherals still have supply-only models, not image protocol
  emulation. Their blank previews show the solved power state and this limitation;
  no invented bitmap or lit LED pattern is presented as a firmware result.
- LCD retains its decoded 16x2 text and enlarged blue panel.

## Changes in rc4

- Unconnected microcontroller GPIO pins no longer inflate the electrical solver
  matrix. Unloaded pin voltages remain available; wired pins and power checks
  retain the full electrical model.
- Continuous simulation queues bounded catch-up batches without waiting for the
  display timer. The selected integration step is preserved, not enlarged to
  hide slow computation. Extremely small steps or complex circuits may still lag.
- LCD simulation shows a larger blue-backlit 16-column, two-row panel with one
  fixed-width cell per character. The schematic footprint and wire anchors remain
  unchanged; the expanded panel is specific to the simulator.

## Changes in rc3

- Windows startup sets a stable ElectroSchem AppUserModelID before creating windows,
  separating its taskbar identity from Python and using the multi-resolution logo.
- At 100%, pacing targets one simulation second per SI second, using a monotonic
  nanosecond clock. One SI second corresponds to 9 192 631 770 periods of the
  caesium-133 defining transition. This does not provide atomic-clock accuracy:
  host clock tolerance, integration step size and solver performance still apply.
  At 50%, one simulation second targets two real seconds. Pause/resume excludes
  paused time and no physical steps are skipped to conceal computational lag.

## Changes in rc2

- Dark-theme paper and title blocks now approximate 70% white luminance (#dadada).
  Grid colours are adjusted for the brighter paper; exports remain white.
- The application and simulator use a multi-resolution logo with the supplied
  72, 144, 432 and 576 pixel variants. Qt selects the appropriate image for the
  displayed size and DPI without changing the logo colours between themes.

## Changes in rc1

- The application uses the supplied outlined pixel-art logo in its original colours.
- Dark-theme paper and title-block backgrounds now approximate 60% white luminance
  (#cbcbcb), with adjusted grid colours. The simulator sandbox stays dark and exports
  retain white paper. This changes canvas colours, not monitor brightness.

## Changes in alfa11

- Arduino Uno R3 and classic Nano can run real `.ino` sketches: Arduino CLI
  compiles the sketch folder, then avr8js executes the generated AVR instructions.
  Reload from editor compiles asynchronously. New code for these boards defaults
  to `.ino`; other firmware boards remain limited to their listed integrations.
  Compiler-created boards use explicit simulated USB power; legacy assigned HEX
  retains its existing external-power requirement. Compilation never uploads.
- Install Arduino CLI and `arduino:avr` separately. On this workspace, verified
  official CLI 1.5.1 and AVR core 1.8.8 are under ignored `.tools/`; they are not
  bundled into source distribution. System `arduino-cli` takes precedence.
- Python uses a cooperative AST runtime, not host `exec`/`eval`: functions,
  for/while loops, positional/keyword/default arguments, expressions and local
  same-folder helper `.py` imports. GPIO APIs include RPi.GPIO, gpiozero and
  machine.Pin. RPLCD.i2c.CharLCD supports PCF8574 16x2 write_string, cursor_pos,
  clear/home/backlight and close; smbus/smbus2 support byte/block writes.
  See [RPLCD API](https://rplcd.readthedocs.io/en/stable/api.html).
  Classes, decorators, try/with, arbitrary Python modules and native extensions
  are not implemented. Unsupported operations report errors, not success.
- Python bus writes and AVR Wire/TWI writes are routed to LCDs by SDA/SCL nets,
  common GND and I2C address, then checked against the solved supply voltage.
  This is atomic transaction-level integration, not I2C edge-timing simulation.
  The old sampled electrical I2C decoder remains available for bit-banged tests.
  I2C reads, other slave models and general SPI/ADC coupling are not implemented.
- The LCD now draws its actual two-line text and green backlight in the circuit,
  rather than showing text only in tooltips. Unsupported glyphs remain marked.
- Device Camera Preview is a new abstract module. The camera button also applies
  to the existing XIAO Sense camera board. Click Allow and start, choose a device,
  and restart if changing the selection. Consent is session-scoped and revoked
  by Stop, reset or closing. No microphone, recording, file saving or network I/O.
  Frames appear on the module and in a separate preview. This is host-camera
  preview, not OV3660/CSI/UVC firmware protocol emulation. Hardware capture was
  not enabled during automated testing; permission/start/stop are tested with mocks.
- In the dark theme, sheet colour #959595 approximates 30% white luminance with
  contrasting ink. No monitor setting changes; export remains white.
- The supplied LCD project wires were verified with RPLCD code: two lines display
  ElectroSchem and LCD dziala!. Its previous linked source only blinked GPIO12.

## Changes in alfa10

- Simulator controls, tabs, tables and logs follow the selected UI theme;
  only the circuit sandbox stays dark. Editor paper stays light in both themes.
- Fault effect names are Gentle, Medium and Strong. New settings default to
  Strong; previously saved choices remain unchanged. Gentle or Medium is
  recommended for people with photosensitive epilepsy. Esc stops effects.
- EN/PN/ISO use IEC-style rectangular resistors and logic gates. IEEE/ANSI
  selects zigzag resistors and distinctive gate shapes in editor, simulator
  and exports without changing terminals or connectivity. This is a limited
  drawing convention implementation, not a standards compliance certificate.
  References: [IEC TC3](https://tc3.iec.ch/tc-activity/graphical-symbols-for-diagrams/),
  [IEEE 315](https://standards.ieee.org/ieee/315/515/) and
  [IEEE logic symbols](https://standards.ieee.org/ieee/91/6541/).
- Code filenames are `<component-ID>_<project-ID>_code.<extension>`.
  Project ID is the first 16 hexadecimal characters of SHA-256 of the exact
  UTF-8 project title. Renaming a project changes this identifier (superseded by
  persistent UUIDs in 1.1.1alfa1). Component
  UUID directories additionally isolate copies with the same visible reference.
  Previous linked files are copied, never deleted or overwritten.
- Board properties offer Create / open code folder. It creates an entry file,
  README and requirements file and opens VS Code/VSCodium/Cursor as a workspace
  (other editors fall back to the system folder browser). The GPIO simulator
  executes only the linked entry file with its restricted API: arbitrary local
  Python module imports, packages and a full Linux OS are not emulated.

## Changes in alfa9

- Light/dark editor themes cover the canvas, labels, comments, properties,
  menus, tabs and icons. Export uses the original light palette and restores
  the visible theme even when rendering fails.
- Three persisted effect levels: Mini (silent red glow), Medium (local wave,
  sparks, smoke and a short bang) and Mega (larger wave/debris, whole-client-window
  white flash and synthesized ringing). A flash is a single fade, not a strobe.
  Mega lasts 2.2 seconds visually; ringing ends 5 seconds after that. Esc,
  Reset and closing the simulator stop both visuals and audio. Device/system
  volume is respected. Existing dramatic-effects preferences migrate to Mega.
- LCD writes are verified through actual circuit nodes as well as an isolated
  bus decoder. The alfa8 test's extra expected space was corrected.

## Changes in alfa8

- Errors and simulator UI use the selected language, including already open
  simulator windows after changing settings. English help is Usage Instructions.
- Windowed/maximized/fullscreen preference applies to both editor and simulator;
  maximized is the default. Disabled buttons give click feedback without executing.
- Secondary category entries use muted text and the same stable component ID.
- 12 schematic-relevant inventory additions bring the selectable library to 144;
  camera and Raspberry Pi DSI display are excluded. See [inventory mapping](INVENTORY.md).
- Joystick dividers/switch, manual active-low IR receiver, IR transmitter activity,
  common-anode RGB, GL5528, exposed-base 4N35 and a 5.1 V supply have electrical models.
- MCP23008/17 have manual direction/output masks with loaded electrical outputs.
  These masks do not implement I2C configuration registers or interrupts.
- LCD LCM1602 accepts sampled PCF8574 I2C writes/ACK at address 0x27 by default
  (decimal setting 39), then HD44780 four-bit ASCII text, clear/home, address,
  display-enable and entry direction. Mapping: P0=RS, P1=RW, P2=E, P3=backlight,
  P4..7=data. No readback/custom glyphs/busy timing; use pull-ups and sample
  every SCL edge. Text appears in its measurement tooltip.
- Complex modules use explicit supply-envelope models: editable resistive supply
  load, supply-limit faults, signal-edge counters and numeric stimulus previews.
  Their signal pins remain high impedance. This permits power checks, not
  operation of their real protocol, firmware, charging, storage, RF or graphics.
  Nominal voltage/current fields describe the chosen model, not hardware ratings.

## Changes in alfa7

- Wrapped property text reserves its full height, including at large UI fonts.
- Save as and export suggest a filesystem-safe name based on the project title.
- A component-help icon sits below Find; component help includes pin-function
  tables and clickable HTTP(S) documentation links. Unknown pin roles are marked
  as device-specific rather than guessed. 74HC04 explicitly describes six NOT gates.
- Options includes a structured User manual with a shortcut table and sections.
- The packaged-logic category is simply Logic ICs.
- Opt-in dramatic faults now include one white flash across the sandbox and a
  stronger synthesized bang. Controls remain visible; system brightness and
  volume are never changed. Default effects remain gentle and silent. Do not
  enable dramatic effects with photosensitivity or hearing sensitivity.

## Changes in alfa6

- Input/Output selection bounds follow the body and the actual pin side, with
  no empty mirrored pin margin. Visible names retain their own grid-aligned row.
- Input and Output share the same large bold numeric font and square frame in
  simulation. Both glow softly in white at HIGH and stop glowing at LOW.
- Pin locations and saved wire connections remain unchanged.

## Changes in alfa5

- One Add component menu, grouped related components and tools, and a simulation
  toolbar icon. Properties and code editing remain available through Tools.
- Compact property forms; opt-in **Remember these values for new components**
  saves electrical values and simulation parameters across sessions. It does not
  change existing components or copy firmware/source paths to other boards.
- New 9 V batteries have a nominal 9 V value. Legacy empty battery values also
  simulate at 9 V; explicit values remain unchanged.
- Board code uses `<visible-ID>_code.py` inside a per-instance AppData directory.
  Existing linked code keeps its extension (for example `.ino`); another filename is copied without deleting the
  original; a conflicting destination is never overwritten.
- Simulation shows sheet comments and a subtle glowing numeric Output indicator.
  Input/Output body edges and pins align to the grid; dot-grid points are clearer.
- Stronger opt-in fault flash and synthesized crack/thump. The default remains
  gentle and silent; damage visuals are not a physical explosion prediction.
- Emulator controls use **Restart** and state-dependent **Start/Pause** labels;
  the functionality table uses **Model** and **Limitations**.

This is an experimental educational simulator. It is **not** a hardware safety
assessment, a complete SPICE implementation or a prediction of component
failure timing. Never use its output as permission to build a hazardous circuit.

## Quick start

1. Draw a circuit and enter its component values in Properties. Capacitors need
   both capacitance and rated voltage. LEDs need a colour; their electrical
   limits are separate, editable simulation parameters.
2. Press **F5** or choose **Tools → Simulation sandbox**.
3. Run, pause, single-step or reset. The sandbox uses a copy of the active sheet.
   It does not move, damage or change the source document.
4. After editing the schematic, choose **Reload from editor**. Other sheets are
   not implicitly connected or simulated.
5. The example selector includes 5 V + switch + LED, AC + lamp, capacitor
   overvoltage, a supply-rail circuit and a PN2222 LED switch. Examples never
   replace the project.

Click ON/OFF, tactile or SPDT switches, an encoder button, a keypad or a digital
sensor in the sandbox to change its input state. Reset restores the initial
state. Hover over a wire
for voltage or a component for current. Green/blue/grey wire colours indicate
positive/negative/near-zero voltage, **not measured current direction**.
The displayed clock is simulated time; execution is not guaranteed real-time.

## Functionality database

`app/libraries/simulation_catalog.py` is separate from the symbol/pin database.
It declares behavior, required units, editable parameters and model notes.
The sandbox's database tab lists every catalog entry with an explicit status.
Unknown/custom components and unsupported models block Run.

| Model | Implementation and required values |
| --- | --- |
| Resistor | Ohm's law; resistance and rated power (default model rating 0.25 W) |
| Capacitor | Backward Euler; capacitance, rated voltage and editable initial voltage (default 0 V) |
| Polarized capacitor | Same, with `auto` initial voltage (reproducible ±100 mV startup precharge) and a non-blocking reversed-polarity warning below −0.5 V |
| Inductor | Backward Euler Norton equivalent; inductance, zero initial current |
| Battery/cell | Ideal DC source; explicit voltage, not inferred from the catalog name |
| AC source | Ideal sine source; RMS voltage, frequency (default 50 Hz), zero phase |
| LED | Two-segment model; forward voltage, 10 Ω dynamic resistance, maximum current and reverse voltage |
| Rectifier diode | Two-segment model; forward voltage, maximum current; no recovery/breakdown model |
| ON/OFF switch | 1 mΩ closed, 1 TΩ open; initial state and interactive toggle |
| Lamp | Constant hot resistance `V_rated² / P_rated`; rated voltage and power |
| GND / supply rails | GND is the common reference; +5V, +3.3V and +12V supply their labelled voltage. VCC has an editable voltage (initially 5 V). A GND return is required for rail-only circuits. |

Repeated symbols of the same rail share one ideal source. Incompatible rail
voltages on one net block Run. A source-current reading for a shared rail refers
to the aggregate source, not a fabricated current split between its symbols.
An independent battery connected across an ideal rail can overconstrain the
solver; use one source for that net. Rails and GND connect within the active sheet.

## Changes in alfa4

- The sandbox moved to Tools; F5 is displayed once as a standard shortcut.
- LEDs have a bright core above the symbol and dimmer voltage-coloured wires.
- Time scale sets a wall-clock target: 100% means one simulated second per real
  second; 50% means one per two real seconds. A slow solver can fall behind;
  the clock tooltip reports this. Pause/Run resets the pacing anchor without
  skipping physical steps. Single Step always advances exactly one step.
- Separate electrical islands are solved independently. Each battery/board can
  have its own reference; explicit GND/rail symbols still denote common nets.
  A fault pauses everything. Run resumes healthy islands with their state intact;
  failed islands stay frozen until Reset. With no healthy islands left, Run
  resets and retries the simulation. An unchanged faulty circuit can trip again.
- Fault effects stay gentle and silent by default. Settings provides an optional
  abrupt local flash and synthesized rupture sound. This opt-in effect may be
  unsuitable for people with photosensitivity; it is not a physical explosion
  prediction. Reset clears fault markers.
- Input (click to toggle 0/5 V) and Output (LOW/HIGH indicator at 2.5 V) are in
  Logic gates. They use an implicit logic ground, so a simple logic circuit needs
  no extra battery or GND symbol. Output is a high-impedance reference/indicator,
  not a short circuit between a gate output and ground.
- Visible component IDs use dots instead of whitespace. Loading old ELS files
  migrates the references and counters while preserving UUIDs and pin anchors.
- Settings includes Default orientation and Username / default author.
- Properties, Edit code, Add component and Find component use the supplied icons.

### Editing and running GPIO code

Select a board and choose **Properties → Edit code**, or use the Edit code tool.
The application creates a per-instance `.py` file in
`%APPDATA%/ElectroSchem/code`, saves its link in the ELS component properties and
opens the configured editor. Existing code is never overwritten. Save the code,
then use **Reload from editor** in the sandbox. ELS currently stores the source
path, not the source contents; transfer the code too when moving a project.

Every catalog board has a **digital GPIO behavioural mode**. This is a bounded
Python AST interpreter, not Raspberry Pi OS, a CPU, Wi-Fi or full MicroPython.
It supports assignments, functions, local helper modules, for/while/if, keyword
arguments, GPIO reads/writes, positive sleep/sleep_ms, gpiozero LED, machine.Pin
and RPi.GPIO. RPLCD and smbus writes couple to a connected PCF8574 LCD. Unknown
syntax/APIs report errors. Local helper modules are interpreted by the same AST
runtime; host modules are never imported by user code. Use schematic pin labels
for other boards. See the alfa11 section for precise API limitations.

Example for Raspberry Pi GPIO12 (physical header pin 32; pin 34 is GND):

```python
from gpiozero import LED
from time import sleep

led = LED(12)  # BCM GPIO numbering, not physical header pin numbering
while True:
    led.on()
    sleep(0.5)
    led.off()
    sleep(0.5)
```

Place a series resistor (for example 330 Ω) with the LED. A direct GPIO-to-LED
connection can exceed the entered LED current limit and stop simulation.
RPi.GPIO `BOARD` mode instead accepts physical pin numbers. GPIO script mode
includes ideal board power and nominal digital levels (Arduino 5 V, micro:bit
3 V, other boards 3.3 V) with a 25 Ω output approximation; these are simplified
model values, not verified device drive ratings. Analog, peripheral and some
special-purpose pins remain unsupported. Compiled firmware mode is still limited
to the previously integrated AVR8js/RP2040js boards; assigning HEX/UF2 selects
that mode rather than executing a GPIO script.

### Fixes introduced in alfa3

The NPN/PNP collector model now makes a continuous transition between active
operation and saturation, with both voltage derivatives included in the solver.
It retains base loading, beta-dependent current and an approximate 1 Ω
saturation channel. This fixes convergence during switching in cross-coupled
PN2222 LED oscillators. The model remains an educational approximation, without
reverse-active operation, junction capacitance or charge storage.

Polarized capacitors default to `auto` initial voltage: a deterministic value
within ±100 mV based on the component ID (increased from ±1 mV in alfa4 to reduce
the artificial startup delay). This explicit startup precharge lets an
otherwise perfectly symmetric oscillator start. Resetting the same circuit
repeats the same run. Enter a voltage, including `0 V`, to override it. `auto`
survives editing component properties and saving/reopening ELS. Ordinary
capacitors still default to zero initial voltage.

Reverse voltage below −0.5 V produces a warning, logged once per component per
run, without stopping the simulation. This is still a damage risk; the model
does not predict chemical degradation or time to failure. Exceeding the rated
capacitor voltage still stops the simulation. Reset clears warning history.

Startup charge and simulation state never change the source schematic. Timing
depends on the entered values, the simplified models and the time step; a
successful simulated oscillation is not a guarantee of an exact hardware period.

## Models added in alfa2

In alfa2, the catalog had models for **94 of 130 selectable entries**, up from 23.
This count includes the four previously integrated firmware boards. It does
**not** mean that all library devices or all of their operating modes are implemented.

| Family | Behaviour and limits |
| --- | --- |
| Potentiometers | Three terminals; loaded divider, editable wiper fraction 0–1. End resistance is limited to 1 mΩ for numerical stability. |
| LDR / NTC | LDR resistance scales inversely with an entered relative light level; NTC uses R25 and a beta equation with temperature in kelvin. |
| Schottky / Zener / RGB | Forward conduction; Zener breakdown and power checks; separate R/G/B currents and mixed glow for common-cathode RGB. |
| NPN / PNP | Named B/C/E terminals, base loading, beta-controlled current, resistive saturation and current-limit diagnostics. Includes PN2222. |
| N/P MOSFET | Gate-controlled channel, gradual transition over 1 V above threshold, body diode and current limit. No gate-charge model. |
| SCR / triac / PC817 | Trigger/latch and holding current for SCR/triac; input diode and CTR-limited output for PC817. No switching/recovery dynamics. |
| Tactile / SPDT / relays | Internal tactile pin pairs; selectable contacts; relay pickup/release hysteresis. Relay boards have active-low inputs. |
| Buzzers | Declared resistive load and activity indication; passive activity requires changing voltage. No speaker audio. |
| Crystal | Passive motional RLC and parallel capacitance; frequency and parameters required. At least 50 steps per period. It does not generate a clock by itself. |
| Logic gates and packages | Seven individual gate functions and 74HC/CD4093 packages with powered outputs; HC14/CD4093 use model Schmitt thresholds. |
| NE555 / LM358 | Sampled comparator/latch/discharge timer with external RC; two supply-limited op-amp gain stages. No bandwidth/slew-rate model. |
| 74HC74 / 74HC595 | Edge-triggered D flip-flops and shift/storage registers, reset/preset/output enable; initial registers zero. |
| Linear regulators / DC converters | Named supply pins; dropout or buck/boost constraints; load reflected to input; adjustable current limits. No switching ripple or thermal dynamics. |
| ST1167 | RX voltage dividers; TX bidirectional switch approximation with pull-ups. No timing/parasitic-capacitance model. |
| Encoder / keypad | Ideal quadrature contacts and push switch; one selected keypad row/column contact. No contact bounce. |
| PIR / IR / ST1146 | User-controlled stimulus drives a powered digital output. IR does not generate a remote-control frame. |
| Soil / MQ-2 / flame / MAX9814 | User-defined electrical output fraction, optional comparator output. No physical gas/moisture/audio conversion. |
| HC-SR04 | Trigger produces a sampled echo pulse based on an entered distance and 343 m/s propagation speed. |
| L298N / A4988 / TMC2208 | H bridges or an educational STEP/DIR full-step abstraction with MS=LOW; not the TMC2208 hardware microstep selection table. Other MS settings report a fault. No UART/chopper emulation. |
| NEMA 17 / servos | Two RL windings; sampled servo PWM command displayed on hover. EF90D reports signed speed; others report angle. No mechanical load/torque simulation. |
| MCP3008 / MCP41010 | Sampled SPI ADC conversion and digital-pot write/shutdown commands. Both clock edges must be resolved by the time step. |
| Terminal blocks | Independent electrical contacts; adjacent terminals are not shorted. |

Component current tooltips for multi-terminal devices report the first model
branch (for example the collector branch or relay coil), not a sum of every pin
current. Extra readings show relay state, servo command, winding currents or ADC
code. For RGB the displayed current is the sum of the three channels.

Parameters describe educational approximations and are editable in Properties.
They are not a library of verified SPICE models. Finite switch/output resistance,
input leakage and sampled timing are intentional parts of these models. The
NE555 comparator samples the preceding accepted step, so transitions can be
delayed by one step. Reduce the step until results stabilize.

SPI models can be driven through schematic pins (including bit-banged GPIO).
They do not add hardware-SPI integration to the existing firmware bridge; fast
edges between co-simulation steps can still be missed.

### Still unsupported

Before alfa8, the following **23 non-board entries** blocked simulation:

- TP4056, the breadboard supply module and XR2206.
- MCP23008, MCP23017 and ADS1115.
- OLED, I²C LCD, e-paper, TFT and MAX7219 displays.
- HC-05, ESP-01, SD reader, DS3231 and RC522.
- DHT11, DHT22, DS18B20, BH1750, BME280, MPU6050 and NEO-6M.

The 13 board profiles without native firmware integration now have GPIO script
mode, as described above; their full CPU/OS backends are still unavailable.

In alfa8 these entries gained the limited models listed above. Their full
protocol, register and firmware behaviour remains outside this release's scope.

### Pinout corrections

74HC02 and 74HC14 now have their own DIP-14 signal order instead of a copied
quad-gate layout. Existing projects retain pin-number anchors; review affected
connections because pin labels now describe the correct physical signals.
The symbol ID and pin numbers are unchanged.

Lamp glow and its overload indicator use a 50 ms exponential average of
electrical power, without modelling temperature-dependent filament resistance.
The simplified fault threshold is 1.44× rated average power or 2× rated voltage
instantaneously. Thus nominal AC does not trip just because its peak exceeds RMS.

LED colour is visual; changing red to blue does not silently invent a new
datasheet. Set the forward voltage and limits for the intended LED. IR glow is
a **visible diagnostic indicator**, not a claim that IR is visible to people.

Faults stop execution and highlight affected symbols. A capacitor warning is a
model-threshold violation, **not an exact explosion simulation**. Reset is
required to restart a failed island; healthy islands can resume. Thermal aging,
leakage, ESR, physical component tolerances, battery internal
resistance, magnetic saturation and many nonlinear effects are not included.

### Numerical and connectivity rules

- Dense modified nodal analysis with pivoting; maximum 80 unknowns per island.
- Fixed time steps from 0.1 ns to 10 ms; AC requires at least 50 steps per period.
- Diode active-set iteration has a convergence limit and reports failure.
- Wire endpoints, physical pin numbers and explicit junctions create nets.
  Crossing wire interiors alone does not create a connection.
- Repeated power flags with the same library ID share a net on the current sheet.
- Without GND, each island uses the negative terminal of its first voltage
  source, a board ground or an implicit logic reference.
- Invalid values, singular circuits and unsupported models are rejected.
  Electrically independent islands are allowed; no hidden ground resistors are
  added to disguise an otherwise singular circuit.
- Unconnected decorative wires may be displayed but are not circuit devices.
- Very small/large time constants can require a smaller step for useful accuracy.
  Passing validation is not a guarantee of numerical accuracy for every circuit.

## Firmware and external editors

Install Node.js 22+ and run `npm ci --ignore-scripts` inside
`app/simulation/emulators`. The lockfile pins AVR8js 0.21.1 and RP2040js 1.4.0.
These dependencies are optional and excluded from Git's `node_modules` tracking.

Add a supported board to the schematic. In the sandbox's **Firmware emulators**
tab, refresh the board list, assign a compiled firmware file, and optionally link
a source file. **Edit source** opens that exact file in the configured external
editor using argument-safe process launching. Uno/Nano .ino sources compile on
Restart or Reload from editor using Arduino CLI. Other targets require external
compilation; Load/restart reads their firmware again. RP2040 SDK firmware calls boot
ROM routines. Use **Pico ROM…** to assign a legally obtained 16 KiB RP2040 ROM
binary; no ROM is bundled or downloaded automatically. Bare-metal programs that
do not access ROM can run without it. An actual ROM access without the file
stops with an explicit error. Tests cover ROM-independent ARM instructions,
not a complete Pico SDK/MicroPython boot.

Saving a source file alone does not start it. Reload compiles assigned Uno/Nano
sketches, including sibling C/C++/header files, then Run starts execution.

The firmware panel runs firmware independently for CPU/GPIO inspection. To
couple it to the drawn circuit, assign firmware, then **Reload from editor** and
Run on the Circuit tab. Each supported board gets its own local process. GPIO
inputs and outputs are exchanged once per circuit time step, so pulses faster
than that step can be missed. This is sampled co-simulation, not edge-exact timing.

| Board | Status in this build |
| --- | --- |
| Arduino Uno R3 / classic Nano | ATmega328P HEX execution, 16 MHz, 32 KiB flash, 2 KiB SRAM, GPIO, timers, UART |
| Raspberry Pi Pico | RP2040 UF2 execution, core 0, GPIO and UART |
| Raspberry Pi Pico W | Same RP2040 core; **no Wi-Fi/Bluetooth model** |
| Arduino Mega / Leonardo | Not integrated: different AVR register/peripheral maps |
| ESP32 / ESP32-S3 / XIAO Sense | Not integrated: requires a target-specific engine, GPIO bridge and board/peripheral models |
| STM32 Nucleo-F401RE / micro:bit V2 | Not integrated: board-specific backend and peripheral adapters remain |
| Teensy 4.1 | No integrated i.MX RT1062 board backend |
| Raspberry Pi Zero 2 W / 4 / 5 | No integrated board/OS/GPIO co-simulation |
| Banana Pi M5 / Orange Pi 3 LTS | No integrated board/OS backend |

**The request for all board emulators is not complete in this alpha.** The status
table is not a collection of working emulators, and planned engine names are
not substitutes for tested board support. Installing QEMU or Renode alone will
not enable the unintegrated rows.

For circuit coupling, supply Uno/Nano through **5V + GND**, and Pico through
**VSYS + GND**. Other board supply arrangements are not modelled in this alpha.
Board supply loading is a declared 1 kΩ approximation. GPIO outputs use a 25 Ω
Thevenin model, inputs use 1 TΩ, and pull-ups use 50 kΩ. Model checks flag voltage
outside −0.3 V to Vlogic+0.3 V and output current above 40 mA; these are generic
simulation limits, not recommended operating ratings for any board.

Only the mapped GPIO, ground and supply pins participate. Connecting other
board pins blocks the circuit instead of treating them as two-terminal devices.
Apart from transaction-level PCF8574 LCD writes, attached SPI/I²C peripherals,
analog ADC coupling, USB protocols, radio, camera firmware drivers and multicore
interactions are not implemented. Host-camera preview is a separate consent-gated
feature, not a camera firmware driver. AVR ADC requests explicitly
fail rather than returning a fabricated analog measurement.

Firmware files remain local files; only their paths are saved in ELS. Copying a
project to another machine can require reassigning those paths. Opening ELS does
not execute firmware. The bridge validates HEX checksums/addresses and RP2040
UF2 family/address/length records, caps file size, and runs in a separate process
with request timeouts. The process is **not an operating-system security sandbox**;
only run firmware and dependencies you trust.

## Sources and licenses

- [TI NE555](https://www.ti.com/lit/ds/symlink/ne555.pdf): comparator, reset and discharge behaviour.
- [onsemi PN2222](https://www.onsemi.com/download/data-sheet/pdf/pn2222-d.pdf): named E/B/C pin mapping; simulation parameters remain configurable approximations.
- [TI 74HC02](https://www.ti.com/lit/ds/symlink/sn74hc02.pdf) and [74HC14](https://www.ti.com/lit/ds/symlink/sn74hc14.pdf): corrected signal ordering.
- [Microchip MCP3008](https://ww1.microchip.com/downloads/en/DeviceDoc/21295d.pdf) and [MCP41010](https://ww1.microchip.com/downloads/en/DeviceDoc/11195c.pdf): sampled SPI framing and commands.
- [AVR8js](https://github.com/wokwi/avr8js): MIT; CPU, timer, GPIO and UART APIs.
- [RP2040js](https://github.com/wokwi/rp2040js): MIT; RP2040 execution and peripheral APIs.
- RP2040 boot ROM is **not bundled**. The upstream
  [pico-bootrom sources](https://github.com/raspberrypi/pico-bootrom) include
  separately licensed floating-point routines; their terms must not be confused
  with the top-level BSD license or the emulator's MIT license.
- [Espressif QEMU](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/qemu.html)
  and [QEMU Raspberry Pi targets](https://www.qemu.org/docs/master/system/arm/raspi.html)
  are references for future integrations, not bundled engines.

Numerical tests compare DC, RC, RL and AC results against analytical/discrete
equations. Emulator tests execute AVR and ARM machine instructions; a Qt test
checks firmware → GPIO → resistor → LED in the circuit window. This does not
constitute validation of arbitrary firmware, full Arduino libraries or all
RP2040 peripherals.
