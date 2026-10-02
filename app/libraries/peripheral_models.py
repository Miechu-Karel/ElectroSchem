"""Explicit educational models, not full firmware/protocol emulators."""
from app.libraries.simulation_catalog import P,approximate,CONTACT

# Closed allowlist: unknown/custom modules must not silently become a load.
ENVELOPE_NAMES={
    "Moduł Ładowania TP4056","Przetwornik ADC ADS1115","Generator Sygnałowy XR2206",
    "Moduł Zasilania Stykowej","Wyświetlacz OLED 0.96 I2C 128x64",
    "Waveshare E-Paper Shield 2.13","Wyświetlacz TFT 1.8 SPI","Matryca LED 8x8 MAX7219",
    "Moduł Bluetooth HC-05","Moduł Wi-Fi ESP8266 ESP-01","Czytnik Kart SD",
    "Zegar Czasu Rzeczywistego RTC DS3231","Moduł RFID RC522",
    "Czujnik Temperatury DHT11","Czujnik Temperatury DHT22","Czujnik Temperatury DS18B20",
    "Czujnik Natężenia Światła BH1750","Czujnik Jakości Powietrza BME280",
    "Akcelerometr MPU6050","Moduł GPS NEO-6M","Czujnik gestów Grove PAJ7620U2",
    "Moduł DHT11 3-pin","Matryca RGB WS2812B 16x16"}

def peripheral_behavior(d):
    name=d.name
    if name=="Moduł kamery urządzenia":
        return approximate("peripheral_envelope",[
            P("sim_nominal_voltage","Model supply voltage","Napięcie zasilania modelu","V","5 V"),
            P("sim_load_current","Model supply current","Prąd zasilania modelu","A","10 mA"),
            P("sim_stimulus","Preview stimulus","Bodziec podglądu",default="0")],
            en="Local live device-camera preview after explicit session consent. Power envelope only; no USB/CSI protocol or firmware camera API. No recording or networking.",
            pl="Lokalny podgląd kamery urządzenia po jawnej zgodzie w sesji. Tylko model zasilania; bez protokołu USB/CSI i API kamery w firmware. Bez nagrywania i sieci.")
    if "4N35" in name:
        return approximate("opto",[P("sim_forward_voltage","Input forward voltage","Napięcie przewodzenia wejścia","V","1.2 V"),P("sim_ctr","Current transfer ratio","Współczynnik CTR",default="1")],en="LED/phototransistor CTR model with accessible base and emitter; no bandwidth model.",pl="Model LED/fototranzystora z CTR, dostępną bazą i emiterem; bez modelu pasma.")
    if "ST1079" in name:
        return approximate("joystick",[P("sim_x","X position (0-1)","Położenie X (0-1)",default="0.5",minimum=0,maximum=1),P("sim_y","Y position (0-1)","Położenie Y (0-1)",default="0.5",minimum=0,maximum=1),CONTACT],en="Two 10 kΩ potentiometers and a switch to GND. External pull-up required on SW.",pl="Dwa potencjometry 10 kΩ i przycisk do GND. SW wymaga zewnętrznego podciągnięcia.")
    if name=="Odbiornik IR Grove 38 kHz":
        return approximate("ir_receiver",[CONTACT],en="Manually supplied demodulated active-low signal; no optical carrier/remote protocol.",pl="Ręcznie zadany zdemodulowany sygnał aktywny niski; bez nośnej optycznej/protokołu pilota.")
    if name=="Moduł nadajnika IR 3-pin":
        return approximate("ir_transmitter",en="Powered active-high driver indicator and 220 Ω emitter load; no optical propagation or carrier generation.",pl="Zasilany wskaźnik sterownika aktywnego wysokim i obciążenie emitera 220 Ω; bez propagacji optycznej i generowania nośnej.")
    if name=="Zasilacz Raspberry Pi USB-C 27 W":
        return approximate("dc",[P("sim_max_current","Current limit","Limit prądu","A","5 A")],"V",en="Ideal 5.1 V DC source with overcurrent fault; no USB PD negotiation.",pl="Idealne źródło DC 5,1 V z błędem przeciążenia; bez negocjacji USB PD.")
    if "LCD 16x2 I2C" in name:
        return approximate("lcd_i2c",[P("sim_address","I2C address (decimal)","Adres I2C (dziesiętnie)",default="39",minimum=0,maximum=127),P("sim_text_encoding","Simulation text encoding","Kodowanie tekstu w symulacji",default="utf-8",choices=(("utf-8","UTF-8","UTF-8"),("windows-1250","Windows-1250","Windows-1250")))],en="PCF8574 write/ACK + HD44780 4-bit text subset. Mapping P0=RS,P1=RW,P2=E,P3=backlight,P4..7=data. Simulator UTF-8/Windows-1250 extension supports Polish text; real LCD character ROMs differ. No reads/custom CGRAM glyphs; sample every SCL edge, use pull-ups.",pl="Zapis/ACK PCF8574 i tekstowy podzbiór HD44780 w trybie 4-bit. P0=RS,P1=RW,P2=E,P3=podświetlenie,P4..7=dane. Rozszerzenie symulatora UTF-8/Windows-1250 obsługuje polskie znaki; pamięci znaków prawdziwych LCD różnią się. Bez odczytu/własnych znaków CGRAM; próbkuj każde zbocze SCL, użyj podciągnięć.")
    if "Ekspander Portów" in name:
        return approximate("gpio_manual",[P("sim_output_mask","Output-enable bit mask","Maska bitowa wyjść",default="0",minimum=0,maximum=65535),P("sim_gpio_mask","Output-value bit mask","Maska bitowa stanów wyjść",default="0",minimum=0,maximum=65535)],en="Educational manual GPIO direction/value masks. Electrical pin outputs work; I2C register configuration/interrupts are not emulated.",pl="Edukacyjne ręczne maski kierunku i wartości GPIO. Wyjścia elektryczne działają; konfiguracja rejestrów I2C i przerwania nie są emulowane.")
    if name in ENVELOPE_NAMES:
        return approximate("peripheral_envelope",[
            P("sim_nominal_voltage","Model supply voltage","Napięcie zasilania modelu","V","3.3 V" if any(x in name for x in ("ESP8266","RC522","BME280","E-Paper")) else "5 V"),
            P("sim_load_current","Model supply current","Prąd zasilania modelu","A","10 mA"),
            P("sim_stimulus","External stimulus / preview value","Bodziec / wartość podglądu",default="0",minimum=-1e6,maximum=1e6)],
            en="Electrical envelope ONLY: editable resistive supply load, supply faults, interface edge counter and stimulus preview. No protocol/register/firmware, image, storage, RF or charging emulation; signal pins remain high-impedance. Model parameters are not hardware ratings.",
            pl="TYLKO model elektryczny zasilania: regulowane obciążenie rezystancyjne, awarie napięcia, licznik zboczy i podgląd bodźca. Bez emulacji protokołu/rejestrów/firmware, obrazu, pamięci, radia i ładowania; piny sygnałowe mają wysoką impedancję. Parametry modelu nie są danymi sprzętu.")
    return None
