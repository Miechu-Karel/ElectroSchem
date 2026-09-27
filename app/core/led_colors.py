"""Stałe klucze kolorów ELS; etykiety zależą od języka interfejsu."""
LED_COLORS = (
    ("red", "Red", "Czerwony"), ("green", "Green", "Zielony"),
    ("blue", "Blue", "Niebieski"), ("yellow", "Yellow", "Żółty"),
    ("orange", "Orange", "Pomarańczowy"), ("white", "White", "Biały"),
    ("ir", "Infrared (IR)", "Podczerwony (IR)"),
)


def color_key(value):
    text = str(value).strip().casefold()
    for key, en, pl in LED_COLORS:
        if text in {key, en.casefold(), pl.casefold()}:
            return key
    if text in {"infrared", "podczerwony", "podczerwień"}:
        return "ir"
    return ""


def color_label(value, language):
    key = color_key(value)
    return next((pl if language == "pl" else en for k, en, pl in LED_COLORS if k == key), str(value))
