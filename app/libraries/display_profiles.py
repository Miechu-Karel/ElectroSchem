"""Simulator-only presentation; these dimensions do not change pin geometry."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayProfile:
    kind: str
    columns: int
    rows: int
    panel_width: int
    panel_height: int


DISPLAY_PROFILES = {
    "Wyświetlacz OLED 0.96 I2C 128x64": DisplayProfile("oled",128,64,320,180),
    "Wyświetlacz TFT 1.8 SPI": DisplayProfile("tft",128,160,240,300),
    "Waveshare E-Paper Shield 2.13": DisplayProfile("epaper",250,122,340,190),
    "Matryca LED 8x8 MAX7219": DisplayProfile("led_matrix",8,8,220,220),
    "Matryca RGB WS2812B 16x16": DisplayProfile("rgb_matrix",16,16,300,300),
}


def display_profile(definition):
    return DISPLAY_PROFILES.get(definition.name)
