"""Kontrakt katalogu: rzeczywiste zaciski, stabilne ID i geometria bez Qt.

Testy struktury nie zastępują sprawdzania datasheetu. Dlatego sprawdzamy
oddzielnie wybrane fizyczne numery i zakres modelowanych złączy, a wpis bez
potwierdzonego źródła nie dostaje automatycznie znacznika verified.
"""
from copy import deepcopy
from math import isfinite
import unittest

from app.libraries.built_in import (
    BUILT_IN_ITEMS, ITEM_BY_ID, get_definition, item_name,
    validate_custom_definition,
)
from app.libraries.pin_catalog import CATALOG, electronic_prefix


BY_NAME = {item.name: item for item in BUILT_IN_ITEMS}


class CatalogTests(unittest.TestCase):
    def test_original_library_is_complete_without_custom_placeholder(self):
        self.assertEqual(len(BUILT_IN_ITEMS), 134)
        self.assertEqual(len(ITEM_BY_ID), 134)
        self.assertEqual(set(BY_NAME), {data.get("display_name", name) for name, data in CATALOG.items()})
        self.assertFalse(any(item.category == "Własne" for item in BUILT_IN_ITEMS))
        # Stary zapis nadal daje się otworzyć, ale szablon nie trafia do menu.
        legacy = get_definition("własne-szablon-elementu-customowego")
        self.assertIsNotNone(legacy)
        self.assertNotIn(legacy.id, ITEM_BY_ID)

    def test_every_pin_is_unique_finite_on_grid_and_inside_selection(self):
        for item in BUILT_IN_ITEMS:
            with self.subTest(item=item.name):
                self.assertTrue(item.pins)
                self.assertEqual(item.width % 40, 0)
                self.assertEqual(item.height % 40, 0)
                self.assertEqual(len({pin.number for pin in item.pins}), len(item.pins))
                self.assertEqual(len({(pin.x, pin.y) for pin in item.pins}), len(item.pins))
                for pin in item.pins:
                    self.assertTrue(pin.number.strip())
                    self.assertTrue(pin.name.strip())
                    self.assertTrue(isfinite(pin.x) and isfinite(pin.y))
                    self.assertEqual(pin.x % 20, 0)
                    self.assertEqual(pin.y % 20, 0)
                    self.assertLessEqual(abs(pin.x), item.width / 2)
                    self.assertLessEqual(abs(pin.y), item.height / 2)

    def test_large_board_counts_and_fit_are_not_two_pin_placeholders(self):
        expected = {
            "Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)": 14,
            "Arduino Uno R3": 38, "Arduino Nano": 30,
            "Arduino Mega 2560": 92, "Arduino Leonardo": 38,
            "Raspberry Pi Pico": 40, "Raspberry Pi Pico W": 40,
            "Raspberry Pi Zero 2 W": 40, "Raspberry Pi 4 Model B": 40,
            "Raspberry Pi 5": 40, "ESP32 DevKitC": 38,
            "ESP32-S3 NodeMCU": 44, "STM32 Nucleo-F401RE": 76,
            "Teensy 4.1": 48, "Microbit V2": 25,
            "Banana Pi M5": 40, "Orange Pi 3 LTS": 26,
        }
        for name, count in expected.items():
            with self.subTest(name=name):
                item = BY_NAME[name]
                self.assertEqual(len(item.pins), count)
                self.assertLessEqual(item.width, 560)
                self.assertLessEqual(item.height, 560)
                self.assertTrue(item.pin_scope)
        for name in ("Arduino Mega 2560", "STM32 Nucleo-F401RE"):
            item = BY_NAME[name]
            self.assertTrue(any(p.y == -item.height/2 for p in item.pins))
            self.assertTrue(any(p.y == item.height/2 for p in item.pins))
            self.assertTrue(any(p.x == -item.width/2 for p in item.pins))
            self.assertTrue(any(p.x == item.width/2 for p in item.pins))

    def test_sensor_and_ic_pin_counts(self):
        expected = {
            "Czujnik Odległości HC-SR04": 4, "Czujnik Ruchu PIR HC-SR501": 3,
            "Czujnik Temperatury DHT11": 4, "Czujnik Temperatury DHT22": 4,
            "Czujnik Temperatury DS18B20": 3, "Czujnik Natężenia Światła BH1750": 5,
            "Czujnik Wilgotności Gleby": 4, "Czujnik Gazu MQ-2": 4,
            "Czujnik Jakości Powietrza BME280": 6, "Akcelerometr MPU6050": 8,
            "Moduł GPS NEO-6M": 4, "Czujnik Płomienia": 4,
            "Czujnik Dźwięku MAX9814": 5, "Układ Scalony NE555": 8,
            "Układ Scalony LM358": 8, "Bramka Logiczna 74HC00": 14,
            "Bramka Logiczna 74HC04": 14, "Przerzutnik 74HC74": 14,
            "Rejestr Przesuwny 74HC595": 16, "Ekspander Portów MCP23017": 28,
            "Przetwornik ADC ADS1115": 10, "Potencjometr Cyfrowy MCP41010": 8,
            "Generator Sygnałowy XR2206": 16, "Mostek H L298N": 15,
            "Sterownik Silników Krokowych A4988": 16,
            "Sterownik Silników Krokowych TMC2208": 16,
        }
        for name, count in expected.items():
            with self.subTest(name=name):
                self.assertEqual(len(BY_NAME[name].pins), count)

    def test_selected_physical_pin_labels(self):
        expected = {
            "Tranzystor NPN BC547": {"1": "C", "2": "B", "3": "E"},
            "Tranzystor PNP BC557": {"1": "C", "2": "B", "3": "E"},
            "Optoizolator PC817": {"1": "A", "2": "K", "3": "E", "4": "C"},
            "Czujnik Temperatury DS18B20": {"1": "GND", "2": "DQ", "3": "VDD"},
            "Układ Scalony NE555": {"1": "GND", "3": "OUT", "8": "VCC"},
            "Raspberry Pi Pico": {"1": "GP0", "30": "RUN", "40": "VBUS"},
            "Teensy 4.1": {"L.1": "GND", "L.24": "D32", "R.1": "VIN", "R.24": "D33"},
            "Microbit V2": {"1": "P3", "2": "P0", "21": "P19/SCL", "25": "GND"},
            "Banana Pi M5": {"3": "GPIOX_17/SDA", "40": "GPIOAO_4"},
            "Orange Pi 3 LTS": {"3": "PD26/SDA", "11": "PD24/UART3_RX", "26": "PL8"},
        }
        for name, labels in expected.items():
            actual = {pin.number: pin.name for pin in BY_NAME[name].pins}
            for number, label in labels.items():
                with self.subTest(name=name, pin=number):
                    self.assertEqual(actual[number], label)

    def test_human_prefixes_follow_the_accepted_scheme(self):
        self.assertEqual(BY_NAME["Rezystor"].reference_prefix, "Res")
        self.assertEqual(BY_NAME["Kondensator Elektrolityczny"].reference_prefix, "EleCap")
        self.assertEqual(BY_NAME["Dioda LED 3mm"].reference_prefix, "LED")
        self.assertEqual(BY_NAME["Czujnik Odległości HC-SR04"].reference_prefix, "s_HC-SR04__")
        self.assertEqual(BY_NAME["Układ Scalony NE555"].reference_prefix, "ic_NE555__")
        self.assertEqual(BY_NAME["Arduino Uno R3"].reference_prefix, "mc_Arduino Uno R3___")
        for item in BUILT_IN_ITEMS:
            with self.subTest(item=item.name):
                prefix = item.reference_prefix
                if not prefix.startswith(("s_", "ic_", "mc_", "oth_")) and prefix != "LED":
                    self.assertEqual(prefix, electronic_prefix(item.name_en))
                self.assertTrue(prefix.isprintable())

    def test_source_flags_and_english_names_are_not_faked(self):
        for item in BUILT_IN_ITEMS:
            with self.subTest(item=item.name):
                self.assertTrue(item.name_en.strip())
                self.assertTrue(item.variant.strip())
                self.assertIsInstance(item.verified, bool)
                if item.verified:
                    self.assertTrue(item.source_url.startswith("https://"))
                self.assertEqual(item_name(item, "pl"), item.name)
                self.assertEqual(item_name(item, "en"), item.name_en)
        self.assertNotIn("kamerą", BY_NAME["Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)"].name_en)
        self.assertFalse(BY_NAME["Dioda RGB"].verified)  # Colour lead order varies.
        self.assertFalse(BY_NAME["ESP32-S3 NodeMCU"].verified)  # Not a single board revision.

    @staticmethod
    def custom():
        return dict(id="custom-test", name="Test", name_en="Test", reference_prefix="Tes",
                    symbol="module", width=120, height=80,
                    pins=[dict(number="1", name="VCC", x=-60, y=0),
                          dict(number="2", name="GND", x=60, y=0)])

    def test_custom_definition_and_legacy_prefix_are_resolved(self):
        entry = self.custom()
        original = deepcopy(entry)
        definition = get_definition(entry["id"], [entry])
        self.assertEqual(definition.reference_prefix, "Tes")
        self.assertEqual(entry, original)
        entry["prefix"] = "Old"
        del entry["reference_prefix"]
        self.assertEqual(get_definition(entry["id"], [entry]).reference_prefix, "Old")

    def test_invalid_custom_geometry_and_prefix_are_rejected(self):
        changes = [
            ("width", 81), ("height", float("nan")),
            ("reference_prefix", ""), ("reference_prefix", "X\nInjected"),
            ("reference_prefix", " X"), ("reference_prefix", 123),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                entry = self.custom()
                entry[field] = value
                with self.assertRaises(ValueError):
                    get_definition(entry["id"], [entry])
        for field, value in (("x", float("inf")), ("x", 30), ("y", 0)):
            entry = self.custom()
            if field == "y":
                entry["pins"][1] = dict(entry["pins"][0])
            else:
                entry["pins"][0][field] = value
            with self.assertRaises(ValueError):
                validate_custom_definition(entry)


if __name__ == "__main__":
    unittest.main()
