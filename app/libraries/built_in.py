"""Katalog elementów i ich elektrycznych wyprowadzeń.

Identyfikator biblioteczny nigdy nie zależy od wybranego języka. Nie wolno
zmieniać istniejących slugów: zapisane projekty ELS odwołują się właśnie do nich.
Geometria symbolu jest schematowa, a numer pinu oznacza wyprowadzenie fizyczne.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from app.libraries.pin_catalog import CATALOG


@dataclass(frozen=True)
class PinSpec:
    number: str
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class LibraryItem:
    id: str
    name: str
    category: str
    name_en: str = ""
    reference_prefix: str = "Cmp"
    symbol: str = "module"
    pins: tuple[PinSpec, ...] = ()
    width: float = 80
    height: float = 40
    variant: str = ""
    source_url: str = ""
    default_unit: str = ""
    verified: bool = False
    pin_scope: str = ""
    show_pin_numbers: bool = True


_RAW_LIBRARY: dict[str, list[str]] = {
    "Elementy pasywne": ["Rezystor", "Kondensator Ceramiczny", "Kondensator Elektrolityczny", "Kondensator Tantalowy", "Potencjometr Obrotowy", "Potencjometr Suwakowy", "Cewka Indukcyjna", "Kwarc Rezonator 16MHz", "Kwarc Rezonator 8MHz", "Fotorezystor LDR", "Termistor NTC", "Enkoder Obrotowy"],
    "Półprzewodniki": ["Dioda Prostownicza 1N4007", "Dioda Zenera", "Dioda LED 3mm", "Dioda LED 5mm", "Dioda RGB", "Dioda Schottky", "Tranzystor NPN BC547", "Tranzystor PNP BC557", "Tranzystor N-MOSFET IRF540N", "Tranzystor P-MOSFET", "Tyrystor", "Triak", "Optoizolator PC817"],
    "Zasilanie i połączenia": ["Stabilizator Liniowy LM7805", "Stabilizator Liniowy LM7812", "Stabilizator AMS1117-3.3", "Bateria 9V", "Koszyk na Akumulator 18650", "Akumulator Li-Po 3.7V", "Złącze Goldpin Męski", "Złącze Goldpin Żeński", "Terminale Śrubowe ARK 2-pin", "Terminale Śrubowe ARK 3-pin", "Szyna Zasilania VCC", "Szyna Zasilania +5V", "Szyna Zasilania +3.3V", "Szyna Zasilania +12V", "Masa GND", "Moduł Ładowania TP4056", "Przetwornik DC-DC Step-Down LM2596", "Przetwornik DC-DC Step-Up MT3608", "Konwerter Poziomów Logicznych"],
    "Układy i sterowniki": ["Układ Scalony NE555", "Układ Scalony LM358", "Bramka Logiczna 74HC00", "Bramka Logiczna 74HC04", "Bramka Logiczna 74HC02", "Bramka Logiczna 74HC08", "Bramka Logiczna 74HC14", "Bramka Logiczna 74HC32", "Bramka Logiczna 74HC86", "Układ Logiczny CD4093BE", "Bramka AND", "Bramka OR", "Bramka NOT", "Bramka NAND", "Bramka NOR", "Bramka XOR", "Bramka XNOR", "Przerzutnik 74HC74", "Rejestr Przesuwny 74HC595", "Ekspander Portów MCP23017", "Ekspander Portów MCP23008", "MCP2008", "Przetwornik ADC ADS1115", "Potencjometr Cyfrowy MCP41010", "Generator Sygnałowy XR2206", "Mostek H L298N", "Sterownik Silników Krokowych A4988", "Sterownik Silników Krokowych TMC2208"],
    "Moduły i interfejsy": ["Przycisk Tact Switch", "Przełącznik Suwakowy", "Przełącznik Dźwigniowy", "Przekaźnik Elektromechaniczny 5V", "Buzzer Piezoelektryczny Aktywny", "Buzzer Pasywny", "Nadajnik Podczerwieni", "Czujnik Podczerwieni", "Moduł Zasilania Stykowej", "Wyświetlacz OLED 0.96 I2C 128x64", "Wyświetlacz LCD 16x2 I2C", "Wyświetlacz LCD 16x2 I2C LCM1602", "Waveshare E-Paper Shield 2.13", "Wyświetlacz TFT 1.8 SPI", "Matryca LED 8x8 MAX7219", "Moduł Przekaźnika 1-kanałowy", "Moduł Przekaźnika 4-kanałowy", "Moduł Bluetooth HC-05", "Moduł Wi-Fi ESP8266 ESP-01", "Klawiatura Membranowa 4x4", "Czytnik Kart SD", "Zegar Czasu Rzeczywistego RTC DS3231", "Moduł RFID RC522"],
    "Czujniki": ["Czujnik Odległości HC-SR04", "Czujnik Ruchu PIR HC-SR501", "Czujnik Temperatury DHT11", "Czujnik Temperatury DHT22", "Czujnik Temperatury DS18B20", "Czujnik Natężenia Światła BH1750", "Czujnik Wilgotności Gleby", "Czujnik Gazu MQ-2", "Czujnik Jakości Powietrza BME280", "Akcelerometr MPU6050", "Moduł GPS NEO-6M", "Czujnik Płomienia", "Czujnik Dźwięku MAX9814", "Czujnik Dźwięku Iduino ST1146"],
    "Mikrokontrolery i SBC": ["Seeed Studio XIAO ESP32-S3 Sense (z kamerą OV3660)", "Arduino Uno R3", "Arduino Nano", "Arduino Mega 2560", "Arduino Leonardo", "Raspberry Pi Pico", "Raspberry Pi Pico W", "Raspberry Pi Zero 2 W", "Raspberry Pi 4 Model B", "Raspberry Pi 5", "ESP32 DevKitC", "ESP32-S3 NodeMCU", "STM32 Nucleo-F401RE", "Teensy 4.1", "Microbit V2", "Banana Pi M5", "Orange Pi 3 LTS"],
    "Napędy": ["Silnik Krokowy NEMA 17", "Serwomechanizm SG90", "Serwomechanizm MG996R"],
    "Własne": [],
}


_RAW_LIBRARY["Napędy"].append("Serwomechanizm EF90D 360° (praca ciągła)")
_RAW_LIBRARY["Moduły i interfejsy"].extend(["Łącznik ON/OFF", "Żarówka"])
_RAW_LIBRARY["Zasilanie i połączenia"].append("Źródło napięcia przemiennego")
_RAW_LIBRARY["Półprzewodniki"].append("Tranzystor NPN PN2222")
_RAW_LIBRARY["Zasilanie i połączenia"].append("Konwerter Poziomów Logicznych Iduino ST1167")
_RAW_LIBRARY["Układy i sterowniki"].append("Przetwornik ADC MCP3008")
_RAW_LIBRARY["Układy i sterowniki"].extend(["Input", "Output"])
_RAW_LIBRARY["Moduły i interfejsy"].append("Moduł Przekaźnika 1-kanałowy z optoizolacją 5V")
from app.libraries.inventory_parts import install as install_inventory
from app.libraries.pin_catalog import add as add_catalog, terminals
for category,name in install_inventory(CATALOG,add_catalog,terminals):
    _RAW_LIBRARY[category].append(name)

# Starsze projekty zachowują definicje i stabilne identyfikatory; porządkowanie
# menu nigdy nie usuwa symboli, do których odwołuje się istniejący plik ELS.
HIDDEN_NAMES = {"Konwerter Poziomów Logicznych", "Akumulator Li-Po 3.7V", "Złącze Goldpin Męski", "Złącze Goldpin Żeński", "Układ MCP2008 (niezweryfikowany)",
                "Wyświetlacz LCD 16x2 I2C", "Moduł Przekaźnika 1-kanałowy"}


def _identifier(category: str, name: str) -> str:
    """Tworzy prosty stabilny identyfikator bez zależności zewnętrznych."""
    source = f"{category}-{name}".lower()
    return "".join(character if character.isalnum() else "-" for character in source).strip("-")


def _make_item(category: str, name: str, data: dict, library_id: str = "") -> LibraryItem:
    """Przelicza deklarację pinów na punkty siatki, bez zależności od Qt.

    Krótkie moduły mają jeden rząd pinów pod prostokątem, jak na szkicu.
    Duże układy mają dwa boki; numeracja nie jest zamieniana na kolejność
    graficzną. Wszystkie końcówki są wielokrotnością 20 jednostek sceny.
    """
    symbol = data.get("symbol", "module")
    raw_pins = data.get("pins", ["1", "2"])
    if isinstance(raw_pins, str):
        raw_pins = raw_pins.split("|")
    width, height = data.get("width", 80), data.get("height", 40)
    pins: list[PinSpec] = []
    explicit = bool(raw_pins) and isinstance(raw_pins[0], dict) and "x" in raw_pins[0]
    module = symbol in ("module", "ic", "connector", "relay", "rgb", "motor", "opto")
    # 92 styki Mega rozłożone wyłącznie po bokach tworzyły element wyższy
    # niż cała A4. Cztery boki zachowują raster 5 mm bez pomijania pinów.
    four_sides = module and not explicit and len(raw_pins) > 64
    if not explicit and module:
        count = len(raw_pins)
        if count <= 8:
            width = max(120, ceil((count * 40 + 40) / 40) * 40)
            height = 80
        elif four_sides:
            side_count = ceil(count / 4)
            width = height = ceil((side_count * 20 + 60) / 40) * 40
        else:
            # Każda strona potrzebuje osobnego miejsca na nazwy pinów;
            # nie ściskamy napisu do starego dwupinowego prostokąta.
            longest = max((len(p.get("name", "")) if isinstance(p, dict) else len(p) for p in raw_pins), default=4)
            width = max(240, ceil((longest * 12 + 100) / 40) * 40)
            height = ceil((ceil(count / 2) * 20 + 60) / 40) * 40
    for index, raw in enumerate(raw_pins):
        number = str(raw.get("number", index + 1)) if isinstance(raw, dict) else str(index + 1)
        pin_name = str(raw.get("name", number)) if isinstance(raw, dict) else str(raw)
        if explicit:
            x, y = float(raw["x"]), float(raw["y"])
        elif four_sides:
            side_count = ceil(len(raw_pins) / 4)
            side, row = divmod(index, side_count)
            along = -width / 2 + 40 + row * 20
            # Kolejność rysowania nie jest numerem nóżki; zachowujemy numer
            # z wejściowej definicji również po przejściu na kolejny bok.
            x, y = ((-width / 2, along), (along, height / 2),
                    (width / 2, -along), (-along, -height / 2))[side]
        elif module and len(raw_pins) <= 8:
            x, y = -width / 2 + 40 + index * 40, height / 2
        elif module:
            half = ceil(len(raw_pins) / 2)
            x = -width / 2 if index < half else width / 2
            row = index if index < half else len(raw_pins) - 1 - index
            y = -height / 2 + 40 + row * 20
        else:
            x, y = (-40, 0) if index == 0 else (40, 0)
        pins.append(PinSpec(number, pin_name, x, y))
    return LibraryItem(
        id=library_id or _identifier(category, name), name=data.get("display_name", name), category=category,
        # AI i edytor użytkownika zapisują pełną nazwę pola. Starsze wpisy
        # katalogu używają skrótu prefix; oba formaty są zgodne przy odczycie.
        name_en=data.get("name_en", name), reference_prefix=data.get("reference_prefix", data.get("prefix", "Cmp")),
        symbol=symbol, pins=tuple(pins), width=width, height=height,
        variant=data.get("variant", "Generic schematic symbol"),
        source_url=data.get("source", ""), default_unit=data.get("unit", ""),
        verified=data.get("verified", False), pin_scope=data.get("scope", "All numbered terminals of the stated variant"),
        show_pin_numbers=bool(data.get("show_pin_numbers", True)),
    )


BUILT_IN_ITEMS = [_make_item(category, name, CATALOG[name])
                  for category, names in _RAW_LIBRARY.items() for name in names]
ITEM_BY_ID = {item.id: item for item in BUILT_IN_ITEMS}
AVAILABLE_ITEMS = [item for item in BUILT_IN_ITEMS if item.name not in HIDDEN_NAMES]

# Dawny szablon usuwamy z menu, nie z odczytu starych projektów. Zachowanie
# definicji pozwala zobaczyć i poprawić już zapisany element zamiast go zgubić.
_LEGACY_TEMPLATE_ID = _identifier("Własne", "Szablon Elementu Customowego")
_LEGACY_TEMPLATE = _make_item("Własne", "Szablon Elementu Customowego", {
    "name_en": "Legacy custom component template", "prefix": "CusEle",
    "pins": "1|2", "variant": "Legacy two-terminal template; edit or replace with your custom definition",
}, _LEGACY_TEMPLATE_ID)


def item_name(item: LibraryItem, language: str = "en") -> str:
    return item.name if language.lower().startswith("pl") else (item.name_en or item.name)


def validate_custom_definition(entry: dict) -> dict:
    """Sprawdza dane z edytora/ELS, nie ufając samemu rozszerzeniu pliku.

    Ten sam kontrakt geometrii obowiązuje dla ręcznego edytora i AI. Zwracamy
    kopię z uzupełnionymi polami, bez zmieniania danych należących do projektu.
    ``ValueError`` jest celowy: okno Otwórz może pokazać czytelny błąd zamiast
    awarii głęboko wewnątrz QPainter lub tworzenia niewidocznego symbolu.
    """
    if not isinstance(entry, dict):
        raise ValueError("Custom component definition must be an object")
    data = dict(entry)
    for field in ("id", "name"):
        text = data.get(field)
        if not isinstance(text, str) or not text.strip() or len(text) > 200 or "\x00" in text:
            raise ValueError(f"Invalid custom component {field}")
    data.setdefault("name_en", data["name"])
    data.setdefault("reference_prefix", data.get("prefix", "Cus"))
    data.setdefault("symbol", "module")
    if data["symbol"] != "module":
        raise ValueError("Custom components must use a module body")
    for field in ("name_en", "reference_prefix"):
        text = data[field]
        if not isinstance(text, str) or not text.strip() or len(text) > 200 or "\x00" in text:
            raise ValueError(f"Invalid custom component {field}")
    if not data["reference_prefix"].isprintable() or data["reference_prefix"] != data["reference_prefix"].strip():
        raise ValueError("Custom reference prefix must not contain control characters or outer whitespace")
    for field in ("width", "height"):
        value = data.get(field)
        if (isinstance(value, bool) or not isinstance(value, (float, int)) or
                not isfinite(value) or not 40 <= value <= 2000 or value % 40):
            raise ValueError("Custom dimensions must be 40..2000 and multiples of 40")
    pins = data.get("pins")
    if not isinstance(pins, list) or not 1 <= len(pins) <= 256:
        raise ValueError("Custom component requires 1..256 pins")
    seen_numbers, seen_positions = set(), set()
    copied_pins = []
    for raw in pins:
        if not isinstance(raw, dict):
            raise ValueError("Custom pin must be an object")
        pin = dict(raw)
        for field in ("name", "number"):
            text = pin.get(field)
            if not isinstance(text, str) or not text.strip() or len(text) > 100 or "\x00" in text:
                raise ValueError(f"Invalid custom pin {field}")
        for field in ("x", "y"):
            value = pin.get(field)
            if (isinstance(value, bool) or not isinstance(value, (float, int)) or
                    not isfinite(value) or value % 20):
                raise ValueError("Custom pins must be finite and aligned to the grid")
        x, y = pin["x"], pin["y"]
        hw, hh = data["width"] / 2, data["height"] / 2
        if abs(x) > hw or abs(y) > hh or (abs(x) != hw and abs(y) != hh):
            raise ValueError("Custom pins must lie on the component boundary")
        if pin["number"] in seen_numbers or (x, y) in seen_positions:
            raise ValueError("Custom pin numbers and positions must be unique")
        seen_numbers.add(pin["number"])
        seen_positions.add((x, y))
        copied_pins.append(pin)
    data["pins"] = copied_pins
    # Dodatkowe notatki/opis działania pozostają tekstem, nigdy kodem.
    for field in ("description", "behavior", "variant", "source", "scope"):
        if field in data and (not isinstance(data[field], str) or len(data[field]) > 10000):
            raise ValueError(f"Invalid custom component {field}")
    return data


def get_definition(library_id: str, custom_components=None) -> LibraryItem | None:
    """Własne symbole są danymi projektu, a nie wykonywalnym kodem Pythona."""
    if library_id in ITEM_BY_ID:
        return ITEM_BY_ID[library_id]
    if library_id == _LEGACY_TEMPLATE_ID:
        return _LEGACY_TEMPLATE
    entries = custom_components or []
    if isinstance(entries, dict):
        entries = [dict(value, id=key) for key, value in entries.items() if isinstance(value, dict)]
    for entry in entries:
        if isinstance(entry, LibraryItem) and entry.id == library_id:
            return entry
        if isinstance(entry, dict) and entry.get("id") == library_id:
            data = validate_custom_definition(entry)
            data.setdefault("variant", "User-defined element")
            return _make_item("Własne", str(entry.get("name", "Custom")), data, library_id)
    return None
