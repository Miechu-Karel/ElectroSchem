"""Mapa płytek i silników. Planowany backend NIE oznacza obsługi płytki.

SBC uruchamiają cały system z obrazem dysku; nie można traktować ich jak
ATmega z plikiem HEX. Trzymamy te rozróżnienia w danych, a nie w obietnicach UI.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EmulatorProfile:
    engine: str
    ready: bool
    voltage: float
    reason_en: str
    reason_pl: str


AVR = EmulatorProfile("avr8js", True, 5,
    "ATmega328P: real .ino compilation, HEX, GPIO, timers, UART, Wire writes to wired PCF8574 LCD. No I2C reads, SPI devices or analog ADC coupling.",
    "ATmega328P: kompilacja prawdziwych .ino, HEX, GPIO, timery, UART, zapis Wire do podłączonego LCD PCF8574. Bez odczytów I2C, urządzeń SPI i sprzężenia analogowego ADC.")
PICO = EmulatorProfile("rp2040js", True, 3.3,
    "RP2040: UF2, core 0, GPIO, UART. SDK firmware may require an external boot ROM. No Wi-Fi, USB host or second-core coupling.",
    "RP2040: UF2, rdzeń 0, GPIO, UART. Firmware SDK może wymagać zewnętrznego ROM. Bez Wi-Fi, hosta USB i sprzężenia drugiego rdzenia.")


def unavailable(engine, en, pl):
    return EmulatorProfile(engine, False, 0, en, pl)


PROFILES = {
    "Arduino Uno R3": AVR, "Arduino Nano": AVR,
    "Arduino Mega 2560": unavailable("avr8js / ATmega2560", "ATmega2560 peripheral map not integrated.", "Mapa peryferiów ATmega2560 nie jest zintegrowana."),
    "Arduino Leonardo": unavailable("AVR / ATmega32U4", "ATmega32U4 and USB backend not integrated.", "Brak integracji ATmega32U4 i USB."),
    "Raspberry Pi Pico": PICO,
    "Raspberry Pi Pico W": PICO,
    "ESP32 DevKitC": unavailable("Espressif QEMU", "Requires ESP32 QEMU and a GPIO co-simulation adapter.", "Wymaga QEMU ESP32 i adaptera współsymulacji GPIO."),
    "ESP32-S3 NodeMCU": unavailable("Espressif QEMU (S3)", "Requires ESP32-S3 QEMU and a GPIO adapter.", "Wymaga QEMU ESP32-S3 i adaptera GPIO."),
    "Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)": unavailable("Espressif QEMU (S3)", "S3 board, GPIO and OV3660 camera model not integrated.", "Brak integracji płytki S3, GPIO i kamery OV3660."),
    "STM32 Nucleo-F401RE": unavailable("Renode / STM32", "Exact F401RE board/peripheral adapter not integrated.", "Brak adaptera dokładnej płytki i peryferiów F401RE."),
    "Teensy 4.1": unavailable("i.MX RT1062", "No integrated RT1062 board backend.", "Brak zintegrowanego backendu płytki RT1062."),
    "Microbit V2": unavailable("Renode / nRF52833", "V2 board/peripheral adapter not integrated.", "Brak adaptera płytki i peryferiów V2."),
    "Raspberry Pi Zero 2 W": unavailable("QEMU / BCM2710", "Requires a board model, OS image and GPIO bridge; not integrated.", "Wymaga modelu płytki, obrazu systemu i mostu GPIO; brak integracji."),
    "Raspberry Pi 4 Model B": unavailable("QEMU / BCM2711", "Requires an OS image and GPIO co-simulation bridge; not integrated.", "Wymaga obrazu systemu i mostu współsymulacji GPIO; brak integracji."),
    "Raspberry Pi 5": unavailable("BCM2712 / RP1", "No integrated board and RP1 peripheral model.", "Brak zintegrowanego modelu płytki i peryferiów RP1."),
    "Banana Pi M5": unavailable("Amlogic S905X3", "No integrated board backend or OS image.", "Brak backendu płytki i obrazu systemu."),
    "Orange Pi 3 LTS": unavailable("Allwinner H6", "No integrated board backend or OS image.", "Brak backendu płytki i obrazu systemu."),
}


def profile_for(definition):
    return PROFILES.get(definition.name) if definition else None


def gpio_name(pin_name, engine):
    """Aliasy nagłówków tej samej fizycznej nóżki mają jeden sygnał GPIO."""
    import re
    name = pin_name.split("/")[0]
    if engine == "avr8js":
        if name in {"SDA", "SCL", "MISO", "MOSI", "SCK"}:
            return {"SDA":"A4", "SCL":"A5", "MISO":"D12", "MOSI":"D11", "SCK":"D13"}[name]
        return name if re.fullmatch(r"D(?:[0-9]|1[0-3])|A[0-5]", name) else None
    return name if re.fullmatch(r"GP(?:[0-9]|[12][0-9])", name) else None
