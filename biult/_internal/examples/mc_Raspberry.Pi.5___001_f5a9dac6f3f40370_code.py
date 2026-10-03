"""Code assigned to the user's Przykładowy LCD project (RPLCD API)."""
from RPLCD.i2c import CharLCD
from time import sleep

lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1,
              cols=16, rows=2, charmap='A00')
lcd.write_string('ElectroSchem')
lcd.cursor_pos = (1, 0)
lcd.write_string('LCD dziala!')
sleep(5)
lcd.cursor_pos = (0,0)
lcd.write_string('             ')
lcd.cursor_pos = (1,0)
lcd.write_string('             ')
sleep(5)
lcd.cursor_pos = (0,0)
lcd.write_string('Jebać Żydów')
lcd.cursor_pos = (1,0)
lcd.write_string("ęóąśłżźćń")
while True:
    sleep(1)
