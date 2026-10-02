# Parsed by ElectroSchem's GPIO interpreter; never imported by host Python.
from gpiozero import LED
from time import sleep

led = LED(12)
while True:
    led.on()
    sleep(0.5)
    led.off()
    sleep(0.5)
