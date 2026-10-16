# ElectroSchem 1.3.0alfa9

- E: properties in the editor; component actions in the sandbox, including held
  tact/joystick switches and Raspberry Pi console. Releasing E releases the switch.
- F: add/remove Favorites; Shift+F (or Ctrl+A then F): reuse Favorites.
- Multistage switch labels remain upright after rotation. OFF can be disabled in
  Properties; position zero then resolves to output one.
- USB sockets occupy a separate strip opposite a one-sided pin row, or below
  two-sided rows. Goldpin lead lengths now end exactly at the offset square.
- AI Regenerate replaces the last proposal from its pre-response snapshot.
  Nothing enters the actual project until Accept. No automatic paid retries.
- Local AI: configure a running Chat Completions-compatible server and installed
  model, e.g. Ollama at `http://127.0.0.1:11434/v1` or LM Studio at
  `http://127.0.0.1:1234/v1`. Only loopback URLs are accepted; no cloud keys are
  sent, no redirects followed, and no models downloaded or services launched.
  Responses still pass the command validator and bounded electrical probe.
  The startup course caches verified examples, not trained model weights.

## Added packages

TL072, LM386, NE556, ICL7660, MAX232, CD4017, 74HC165, 74HC138, CD4511,
CD4011, ULN2003A, IR2101, TC4420, DS18B20, MAX485, MCP2515, PCA9685,
CH340G, CP2102, LM7809, LM7905, LM7912, XL4015, TPS61030, MCP73831,
DS3231, DS1307, AT24C256, W25Q128.

NE56 was not guessed or silently replaced: an exact part designation is needed.
Physical pin numbers refer to the package stated in Properties; exposed pads
are not drawn. Consult linked manufacturer documentation before hardware use.

## Educational model limits

- TL072/LM386: rail-clipped gain; no bandwidth, slew, thermal or audio mechanics.
- NE556: two sampled comparator/latch timers; no propagation delay.
- CD4011/4017/4511 and 74HC165/138: ideal logic, finite output resistance,
  clock-edge state, no timing specification emulation.
- ULN2003A: approximate current-limited input resistors and collector switches.
- IR2101/TC4420: ideal gate levels, not peak current or switching-loss models.
- MAX232/MAX485: instantaneous level translation, not UART framing/arbitration.
- ICL7660 and LM7809/7905/7912: averaged power envelopes, not detailed transient,
  protection, charge-pump ripple, thermal or manufacturer SPICE models.
- DS18B20, MCP2515, PCA9685, CH340G, CP2102, XL4015, TPS61030, MCP73831,
  DS3231, DS1307, AT24C256 and W25Q128: **supply load only**. Their protocols,
  memory/register contents, PWM control, switching stages and charging are not
  emulated by these newly added bare-chip models. Existing module models remain.

No real local server or paid provider is invoked by the offline regression suite.
