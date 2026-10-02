# Library and pinout notes

## Symbols are not physical layouts

A schematic symbol represents electrical connections, not the physical layout
of a board or package. Wire hardware using the pin number and signal name,
not the side of the rectangle on which the pin appears.

Definitions describe specific variants. Modules with the same marketing name
can differ in connector order, voltage rating or exposed signals. Check the
exact manufacturer's documentation before wiring hardware.

## Definition sources

- `app/libraries/pin_catalog.py`: pin descriptions, variants and source references.
- `app/libraries/built_in.py`: library construction and definition lookup.
- Custom definitions are stored inside the project's ELS file.

Entries may include a source URL, variant, pin scope and verification flag.
`verified=True` records a documentation check for that particular definition;
it is not a guarantee for every clone, package or board revision. Unverified
entries require additional checking.

## Identity and compatibility

Repeated names such as GND can represent separate contacts with separate IDs.
Boards with several connectors may use compound numbers such as `CN7.1` or
`ICSP.1`. Some modules use signal identifiers instead of physical connector
numbering; consult the variant notes.

Connections store stable pin numbers as well as indexes. Legacy definitions
hidden from the add menu may remain available when reading older ELS projects.
They are not silently replaced with a different device pinout.

Editing a custom definition updates its instances in the project. Removing or
renumbering a pin can leave a wire disconnected. Review connections afterwards.

## Examples requiring care

- **PN2222:** the catalog's onsemi TO-92 variant uses 1 = E, 2 = B, 3 = C.
  Do not assume the same order as the BC547 entry.
- **RGB LED:** the entry describes a common-cathode variant. Confirm the actual
  common terminal and color-pin order.
- **Potentiometer:** the wiper is a separate third terminal.
- **Iduino ST1167:** RX and TX paths do not all have the same directionality.
  Signal/group identifiers are not necessarily physical header positions.
- **Development boards:** symbols may cover expansion headers without exposing
  every USB, camera, debug or underside contact. Read the pin-scope field.

## Electrical checks

EN/PN use the IEC 60617 symbol family; ISO selects the sheet presentation profile.
These profiles draw rectangular resistors and logic gates; IEEE/ANSI selects
zigzag resistors and distinctive gate outlines, keeping all pin positions intact.
These options do not certify standards compliance or electrical correctness.

The experimental simulator in 1.1.0alfa2 supports only a subset of these drawing
symbols; see [Simulation limitations](SIMULATION.md). A successful simulation,
saved project or exported schematic still needs checks for polarity, supply
voltage, current limiting, device ratings, pin assignments and unintended connections.
