# ElectroSchem 1.3.0alfa7

Local development version; no automatic publication or EXE rebuild.

* Real three-way cable junctions retain dots. A two-wire bend remains continuous.
  Loading normalises older T/Y connections where a cable end meets another
  cable's middle; plain crossings without an endpoint are still not connected.
* Unpowered passive islands, including resistor + LED + ohmmeter, can run without
  an external supply. Other powered islands do not prevent measurements there.
* Diodes/LEDs have no fixed resistance. The meter reports apparent resistance at
  a virtual 1 mA, with a 3 V compliance limit. Reverse polarity/out-of-range gives
  OL. This test does not inject power into the sandbox. Lamp resistance remains
  its rated hot-filament approximation; powered networks must be disconnected.
* Entire unboxed assets rotate around a shared, grid-aligned centre, including
  their routes and comments. Selecting one member independently keeps individual
  rotation. A group rotation crossing the sheet boundary is rejected as a whole.
* Board sockets have a separate bottom strip and top-down metal housings, away
  from GPIO labels. USB cable/power-brick contacts stay internal, with no pin
  snap targets. Existing explicit contact anchors remain readable in old files.
* USB power bricks are regulated sources; ports still require an actual supply.
  Added sandbox example: LED powered via USB C. This is an educational USB 2.0
  wiring model, not USB-PD negotiation or a protocol emulator.
* AC source shapes: sine, square, triangle, sawtooth. Entered voltage always
  means RMS. The integration step must still resolve the selected frequency.
* Search results show their category/subcategory.
* Favorites sit between microcontrollers and instruments. F toggles the selected
  part; Shift+F or Ctrl+A, F opens reuse. Preferences are saved outside ELS.
  Reuse copies values/properties into a new UUID/reference, without carrying
  assigned executable files, USB targets or asset group IDs. Custom favorites
  require the corresponding definition to remain available.
* Rectifier: pins 1/2 AC+/AC-, pins 3/4 DC+/DC-. Inverter: pins 1/2 DC+/DC-,
  pins 3/4 AC+/AC-. Existing physical pin numbers/order remain unchanged.
  AC +/− labels identify the two terminals, not a constant DC polarity.

Automated tests use fake AI transport only; no paid API calls.
