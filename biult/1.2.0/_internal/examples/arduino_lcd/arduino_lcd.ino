// Real Wire I2C writes to a PCF8574 LCD backpack at 0x27.
// Mapping: P0=RS, P1=RW, P2=E, P3=backlight, P4..7=data.
#include <Wire.h>

void portWrite(byte value) {
  Wire.beginTransmission(0x27);
  Wire.write(value);
  Wire.endTransmission();
}

void nibble(byte value, byte rs) {
  portWrite((value << 4) | rs | 12);
  portWrite((value << 4) | rs | 8);
  delayMicroseconds(100);
}

void lcdByte(byte value, byte rs = 0) {
  nibble(value >> 4, rs);
  nibble(value & 15, rs);
}

void setup() {
  Wire.begin();
  delay(50);
  nibble(3, 0); delay(5);
  nibble(3, 0); nibble(2, 0);
  lcdByte(0x28); lcdByte(0x0c); lcdByte(1); delay(2);
  const char *message = "Arduino LCD";
  for (int i = 0; message[i]; i++) lcdByte(message[i], 1);
}

void loop() { delay(1000); }
