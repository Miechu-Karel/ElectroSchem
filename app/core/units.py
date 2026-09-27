"""Rozpoznawanie przedrostków SI bez konwersji przez niedokładny float."""
import re
from decimal import Decimal, InvalidOperation, localcontext

_NUMBER = r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?"
_UNITS = {"ohm": "Ω", "ohms": "Ω", "om": "Ω", "ω": "Ω", "Ω": "Ω",
          "f": "F", "h": "H", "v": "V", "a": "A", "hz": "Hz", "w": "W", "": ""}
_PREFIXES = dict(zip(range(-30, 31, 3), ("q", "r", "y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E", "Z", "Y", "R", "Q")))
_POWERS = {prefix: power for power, prefix in _PREFIXES.items()}


def split_unit(unit):
    """Rozpoznaje przedrostek bez mylenia farada F z femto f."""
    unit = unit.strip().replace("μ", "µ").replace("u", "µ")
    if unit.lower() in _UNITS:
        return 0, _UNITS[unit.lower()]
    if unit[:1] in _POWERS and unit[1:].lower() in _UNITS:
        return _POWERS[unit[0]], _UNITS[unit[1:].lower()]
    raise ValueError("Unknown unit / Nieznana jednostka")

def parse_value(text: str, default_unit: str = "") -> tuple[str, str]:
    """1k (Ω) -> ('1', 'kΩ'); 4k7 -> ('4.7', 'kΩ'); 100nF -> ('100','nF')."""
    text = text.strip().replace("μ", "µ")
    if not text:
        return "", default_unit
    default_power, base = split_unit(default_unit)
    shorthand = re.fullmatch(r"([+-]?\d+)([RkMmunpµ])(\d+)", text)
    explicit_base = False
    if shorthand:
        left, prefix, right = shorthand.groups()
        explicit_base = prefix == "R"
        text = left + "." + right + ("" if prefix == "R" else prefix)
    match = re.fullmatch(rf"({_NUMBER})\s*([qryzafpnuµmkKMGTPEZYRQ]?)([A-Za-zΩΩ]*)", text)
    if not match:
        raise ValueError("Use a number and SI unit, e.g. 300, 1k, 4.7uF / Podaj liczbę i jednostkę SI")
    number, prefix, suffix = match.groups()
    prefix = {"u": "µ", "K": "k"}.get(prefix, prefix)
    # Pole właściwości przechowuje osobno liczbę i jednostkę. Ponowne OK na
    # wartości „1” przy jednostce „kΩ” nie może zmieniać jej na 1 Ω.
    unit = _UNITS.get(suffix.lower()) if suffix else base
    if unit is None:
        raise ValueError("Unknown unit / Nieznana jednostka")
    try:
        decimal = Decimal(number.replace(",", "."))
        if not decimal.is_finite() or abs(decimal.adjusted()) > 99:
            raise InvalidOperation
    except InvalidOperation as error:
        raise ValueError("Invalid numeric value / Niepoprawna wartość") from error
    # Skalujemy wartość fizyczną, a nie samą liczbę: 1000 mV = 1 V.
    # Decimal chroni małe pojemności przed błędami binarnego float.
    power = _POWERS[prefix] if prefix else (0 if suffix or explicit_base else default_power)
    with localcontext() as context:
        context.prec = max(32, len(decimal.as_tuple().digits) + 8)
        physical = decimal.scaleb(power)
        engineering = max(-30, min(30, (physical.adjusted() // 3) * 3)) if physical else 0
        if not unit:  # Liczba bez jednostki nie dostaje arbitralnej jednostki SI.
            engineering = power
        decimal = physical.scaleb(-engineering)
    normalized = format(decimal, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized, (_PREFIXES[engineering] if unit else "") + unit

def default_unit_for(library_id: str) -> str:
    from app.libraries.built_in import get_definition
    definition = get_definition(library_id)
    return getattr(definition, "default_unit", "") if definition else ""
