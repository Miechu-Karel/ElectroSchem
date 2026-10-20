"""Polish text using the simulator's UTF-8 LCD extension (16x2)."""
from RPLCD.i2c import CharLCD
from time import sleep

lcd=CharLCD(i2c_expander='PCF8574',address=0x27,port=1,cols=16,rows=2)
lcd.write_string('Zażółć gęślą')
lcd.cursor_pos=(1,0)
lcd.write_string('jaźń ĄĆĘŁŃÓŚŹŻ')
while True:
    sleep(1)
