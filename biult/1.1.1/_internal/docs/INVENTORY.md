# Inventory additions - alfa8

Selected from the user's Inwentarz_elektroniczny.pdf. Tools, consumables,
organizers and adapters without useful circuit behaviour were excluded.
The Raspberry Pi camera and DSI touchscreen were explicitly excluded.

| Inventory item | Library entry | Simulation scope |
| --- | --- | --- |
| Grove gesture sensor | Grove PAJ7620U2 Gesture Sensor | Supply envelope and stimulus/edge preview |
| Iduino joystick | Iduino ST1079 Joystick | Two 10 kOhm dividers and switch |
| Grove IR receiver | Grove 38 kHz IR Receiver | Manual demodulated active-low output |
| IR transmitter board | 3-pin IR Transmitter Module | Powered DAT activity and emitter load |
| DHT11 carrier | DHT11 3-pin Module | Supply envelope; separate from bare 4-pin DHT11 |
| WS2812B matrix | WS2812B 16x16 RGB Matrix | Supply load and edge count; no colour decoding |
| Common-anode RGB | Common Anode RGB LED | Three independent LED channels |
| GL5528 | GL5528 Photoresistor | Resistance controlled by illumination parameter |
| 4N35 | 4N35 Optocoupler | LED/phototransistor with exposed base; CTR approximation |
| Raspberry Pi supply | Raspberry Pi USB-C 27 W Supply | Ideal 5.1 V DC, adjustable 5 A limit; no USB PD |
| Female Pi header | Raspberry Pi 2x20 Socket | 40 independent contacts |
| 40-pin strip | 1x40 Pin Header | 40 independent contacts |

Existing Pi boards, MCP3008/MCP23008, CD4093, relays, PIR, microphone,
DS3231, buzzers, LCD/e-paper, PN2222, 1N4007, 74HC595, common-cathode RGB,
NTC and passive parts were retained instead of duplicated. Resistor, capacitor,
inductor and potentiometer values remain editable properties.

Module signal labels are semantic endpoints; do not assume their drawing order
is the physical connector order. Verify the board revision before wiring.
The 4N35 package numbering uses the manufacturer's DIP-6 drawing.

References used to identify the parts:

- [Seeed PAJ7620U2 gesture sensor](https://wiki.seeedstudio.com/Grove-Gesture_v1.0/)
- [Seeed infrared receiver](https://wiki.seeedstudio.com/Grove-Infrared_Receiver/)
- [Vishay 4N35 datasheet](https://www.vishay.com/docs/81181/4n35.pdf)
- [NXP PCF8574 datasheet](https://www.nxp.com/docs/en/data-sheet/PCF8574_PCF8574A.pdf)
