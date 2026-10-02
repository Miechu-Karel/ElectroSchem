"""Podkategorie menu niezależne od stabilnych identyfikatorów plików ELS.

Przeniesienie urządzenia w menu nie zmienia jego kategorii zapisanej w ID.
Funkcja zwraca parę etykiet EN/PL; jedna definicja ma jedną ścieżkę menu.
"""
import re

def secondary_locations(item):
    if item.symbol in {"led","rgb","ldr","opto"} or "4N35" in item.name:
        return [("Moduły i interfejsy",("Light and infrared","Światło i podczerwień"))]
    if item.name.startswith("Stabilizator"):
        return [("Układy i sterowniki",("Analog and mixed-signal ICs","Układy analogowe i mieszane"))]
    return []


def library_sort_key(item):
    """Stable, language-independent grouping; never changes saved IDs."""
    categories = ("Elementy pasywne", "Półprzewodniki", "Zasilanie i połączenia",
                  "Układy i sterowniki", "Moduły i interfejsy", "Czujniki",
                  "Mikrokontrolery i SBC", "Napędy", "Własne")
    groups = ("Passive components", "Semiconductors", "Power and connectors",
              "Logic gates", "Logic ICs", "GPIO expanders",
              "Analog-to-digital converters", "Analog and mixed-signal ICs", "Motor drivers",
              "Buttons and switches", "Relays", "Displays", "Buzzers", "Light and infrared",
              "Communication and other modules", "Environment", "Motion, distance and location",
              "Sound", "Arduino", "Raspberry Pi", "ESP32", "Other", "Motors and servos")
    families = ("Rezystor", "Potencjometr", "Fotorezystor", "Termistor", "Kondensator",
                "Cewka", "Kwarc", "Enkoder", "Dioda Prostownicza", "Dioda Schottky",
                "Dioda Zenera", "Dioda LED", "Dioda RGB", "Tranzystor NPN", "Tranzystor PNP",
                "Tranzystor N-MOSFET", "Tranzystor P-MOSFET", "Tyrystor", "Triak", "Optoizolator",
                "Bateria", "Koszyk", "Źródło", "Szyna", "Masa", "Stabilizator", "Moduł Ładowania",
                "Przetwornik DC-DC", "Konwerter", "Terminale", "Input", "Output",
                "Bramka AND", "Bramka NAND", "Bramka OR", "Bramka NOR", "Bramka XOR",
                "Bramka XNOR", "Bramka NOT", "Łącznik", "Przełącznik", "Przycisk", "Klawiatura")
    group = subgroup(item)[0]
    family = next((i for i,prefix in enumerate(families) if item.name.startswith(prefix)),len(families))
    natural = tuple((0,int(part)) if part.isdigit() else (1,part.casefold())
                    for part in re.split(r"(\d+)",item.name_en or item.name))
    return (categories.index(item.category) if item.category in categories else len(categories),
            groups.index(group) if group in groups else len(groups), family, natural)


def subgroup(item):
    name, category = item.name, item.category
    if category == "Mikrokontrolery i SBC":
        if "ESP32" in name:
            return "ESP32", "ESP32"
        for brand in ("Arduino", "Raspberry Pi"):
            if brand in name:
                label = "Seeed Studio XIAO" if brand == "Seeed" else ("micro:bit" if brand == "Microbit" else brand)
                return label, label
        return "Other", "Inne"
    if category == "Układy i sterowniki":
        if item.symbol.startswith("gate_") or name in {"Input", "Output"}:
            return "Logic gates", "Bramki logiczne"
        if "74HC" in name or "CD4093" in name:
            return "Logic ICs", "Układy logiczne"
        if "Ekspander" in name:
            return "GPIO expanders", "Ekspandery portów"
        if "ADC" in name:
            return "Analog-to-digital converters", "Przetworniki analogowo-cyfrowe"
        if "Silników" in name or "Mostek H" in name:
            return "Motor drivers", "Sterowniki silników"
        if "niezweryfikowany" in name:
            return "Unverified parts", "Układy niezweryfikowane"
        return "Analog and mixed-signal ICs", "Układy analogowe i mieszane"
    if category == "Czujniki":
        if any(word in name for word in ("Temperatury", "Wilgotności", "Gazu", "Powietrza")):
            return "Environment", "Środowisko"
        if any(word in name for word in ("Odległości", "Ruchu", "MPU6050", "GPS")):
            return "Motion, distance and location", "Ruch, odległość i pozycja"
        if "Dźwięku" in name:
            return "Sound", "Dźwięk"
        return "Light and infrared", "Światło i podczerwień"
    if category == "Moduły i interfejsy":
        if any(word in name for word in ("Wyświetlacz", "E-Paper", "Matryca")):
            return "Displays", "Wyświetlacze"
        if "Przekaźnik" in name:
            return "Relays", "Przekaźniki"
        if "Podczerwieni" in name or name == "Żarówka":
            return "Light and infrared", "Światło i podczerwień"
        if any(word in name for word in ("Przycisk", "Przełącznik", "Klawiatura", "Łącznik")):
            return "Buttons and switches", "Przyciski i przełączniki"
        if "Buzzer" in name:
            return "Buzzers", "Buzzery"
        return "Communication and other modules", "Komunikacja i pozostałe moduły"
    if category == "Napędy":
        return "Motors and servos", "Silniki i serwa"
    return {
        "Elementy pasywne": ("Passive components", "Elementy pasywne"),
        "Półprzewodniki": ("Semiconductors", "Półprzewodniki"),
        "Zasilanie i połączenia": ("Power and connectors", "Zasilanie i połączenia"),
    }.get(category, ("Other", "Pozostałe"))
