"""Schematic-relevant additions from the user's inventory; not stock tracking.

Camera and DSI display deliberately excluded. Semantic module terminal labels
do not assert a physical connector order; verify a board revision before wiring.
"""
def install(catalog,add,terminals):
    parts=[]
    def part(category,name,en,pins,**kwargs):
        add(name,en,pins,**kwargs); parts.append((category,name))
    part("Czujniki","Czujnik gestów Grove PAJ7620U2","Grove PAJ7620U2 Gesture Sensor","SCL|SDA|VCC|GND",
         prefix="s_PAJ7620U2__",source="https://wiki.seeedstudio.com/Grove-Gesture_v1.0/",variant="Grove I2C connector; signal order, not package pin numbering")
    part("Czujniki","Joystick Iduino ST1079","Iduino ST1079 Joystick","GND|VCC|VRx|VRy|SW",prefix="s_ST1079__",
         variant="Two potentiometers and push switch; verify header order")
    part("Czujniki","Odbiornik IR Grove 38 kHz","Grove 38 kHz IR Receiver","SIG|NC|VCC|GND",prefix="s_Grove.IR__",
         source="https://wiki.seeedstudio.com/Grove-Infrared_Receiver/",variant="Grove connector; 38 kHz demodulated output")
    part("Moduły i interfejsy","Moduł nadajnika IR 3-pin","3-pin IR Transmitter Module","VCC|GND|DAT",prefix="oth_IR.TX.Module__",
         variant="Semantic module signals; verify physical order and driver polarity")
    part("Czujniki","Moduł DHT11 3-pin","DHT11 3-pin Module","VCC|DATA|GND",prefix="s_DHT11.Module__",
         variant="3-pin carrier, not the bare 4-pin sensor; verify physical order")
    part("Moduły i interfejsy","Matryca RGB WS2812B 16x16","WS2812B 16x16 RGB Matrix","5V|GND|DIN|DOUT",prefix="oth_WS2812B.16x16__",
         variant="256 LEDs, logical power/data endpoints; verify carrier connectors")
    part("Półprzewodniki","Dioda RGB wspólna anoda","Common Anode RGB LED",terminals((1,"R",-80,-40),(2,"A",80,0),(3,"G",-80,0),(4,"B",-80,40)),
         prefix="LED",symbol="rgb",width=160,height=120,variant="4-lead common-anode RGB LED; verify colour pin order")
    part("Elementy pasywne","Fotorezystor GL5528","GL5528 Photoresistor","1|2",prefix="oth_GL5528__",symbol="ldr",unit="Ω",
         variant="GL5528 photoresistor; reference resistance is user-configurable")
    part("Półprzewodniki","Transoptor 4N35","4N35 Optocoupler","A|K|NC|E|C|B",prefix="oth_4N35__",symbol="ic",
         source="https://www.vishay.com/docs/81181/4n35.pdf",verified=True,variant="Vishay DIP-6, with base connection")
    part("Zasilanie i połączenia","Zasilacz Raspberry Pi USB-C 27 W","Raspberry Pi USB-C 27 W Supply","VBUS|GND",prefix="oth_RPi.27W__",symbol="module",unit="V",
         variant="5.1 V DC output abstraction; not a USB-C pinout or USB PD negotiator")
    part("Zasilanie i połączenia","Gniazdo Raspberry Pi 2x20","Raspberry Pi 2x20 Socket","|".join(str(i) for i in range(1,41)),symbol="connector",
         variant="40 independent contacts, physical header numbering; no built-in power sources")
    part("Zasilanie i połączenia","Listwa Goldpin 1x40","1x40 Pin Header","|".join(str(i) for i in range(1,41)),symbol="connector",
         variant="40 independent contacts; verify connector orientation")
    part("Moduły i interfejsy","Moduł kamery urządzenia","Device Camera Preview","VCC|GND",prefix="Camera",width=160,height=100,
         variant="Local host-camera preview abstraction, not a physical USB/CSI pinout or camera protocol emulator")
    return parts
