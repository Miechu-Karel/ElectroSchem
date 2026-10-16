"""Raspberry Pi + PCF8574/HD44780 LCD using the real RPLCD API.

On hardware: enable I2C and install RPLCD/smbus2; verify wiring and levels.
"""
from RPLCD.i2c import CharLCD
from time import sleep

lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1,
              cols=16, rows=2, charmap='A00')
lcd.write_string('ElectroSchem')
lcd.cursor_pos = (1, 0)
lcd.write_string('LCD dziala!')

while True:
    sleep(1)
