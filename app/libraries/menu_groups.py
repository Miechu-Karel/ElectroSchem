"""Podkategorie menu niezależne od stabilnych identyfikatorów plików ELS.

Przeniesienie urządzenia w menu nie zmienia jego kategorii zapisanej w ID.
Funkcja zwraca parę etykiet EN/PL; jedna definicja ma jedną ścieżkę menu.
"""


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
        if item.symbol.startswith("gate_"):
            return "Logic gates — individual symbols", "Bramki logiczne — pojedyncze symbole"
        if "74HC" in name or "CD4093" in name:
            return "Logic ICs — complete packages", "Układy logiczne — pełne obudowy"
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
        if "Podczerwieni" in name:
            return "Light and infrared", "Światło i podczerwień"
        if any(word in name for word in ("Przycisk", "Przełącznik", "Klawiatura")):
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
