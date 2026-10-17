"""USB help for the educational connector model, not a footprint pinout."""
USB2_URL="https://www.usb.org/document-library/usb-20-specification"
USBC_URL="https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf"

def is_usb_port(definition): return definition.name.startswith("Port USB")

def explanation(definition,language):
    kind=definition.name.removeprefix("Port USB ")
    if language=="pl":
        text=f"Gniazdo USB {kind}. VBUS przenosi zasilanie, GND jest powrotem zasilania, a D+ i D- stanowią parę danych USB 2.0. SHIELD to ekran metalowej obudowy, nie dodatkowe źródło napięcia.\n\nW ElectroSchem gniazdo samo nie zasila układu: podłącz końcówkę kabla do zasilanej kostki lub płytki, a obciążenie do VBUS i GND. Typ końcówki wybierasz we właściwościach kabla. Nie podłączaj VBUS do GPIO 3,3 V. Numery w tabeli są numerami symbolu, nie uniwersalną numeracją pól lutowniczych.\n\n"
        if kind=="C": text+="USB-C jest odwracalne. Nazwy A1…A12 i B1…B12 identyfikują dwie strony złącza. VBUS i GND są wspólne w modelu. CC1/CC2 wykrywają orientację i rolę złącza; TX/RX to pary szybkich danych, SBU to linie pomocnicze.\n\n"
        elif kind in {"Mini-B","Micro-B"}: text+="ID służy do określania roli w USB OTG. Nie jest przewodem zasilającym.\n\n"
        return text+"Symulator odwzorowuje zasilanie i przewody, ale nie pakiety danych, enumerację, USB OTG, tryby alternatywne ani negocjację USB Power Delivery. Dla USB-C model używa 5 V bez negocjacji wyższych napięć."
    text=f"USB {kind} socket. VBUS carries power, GND is its return, D+/D- form the USB 2.0 data pair, and SHIELD is the metal shell.\n\nThis socket is passive: plug a cable into a powered supply or board and connect the load to VBUS/GND. Choose each plug type in cable properties. Never connect VBUS to a 3.3 V GPIO. Table numbers belong to the schematic symbol, not a universal PCB footprint.\n\n"
    if kind=="C": text+="USB-C is reversible. A1…A12/B1…B12 identify the two contact rows. VBUS and GND contacts share their respective nets in the model. CC detects orientation/role; TX/RX are high-speed pairs and SBU are auxiliary signals.\n\n"
    elif kind in {"Mini-B","Micro-B"}: text+="ID identifies the USB OTG role, not a power conductor.\n\n"
    return text+"Simulation covers power and conductors, not packets, enumeration, OTG, alternate modes or USB-PD negotiation. USB-C uses a 5 V educational supply without higher-voltage negotiation."

def pin_role(pin,language):
    label=pin.name.split(".",1)[0]
    roles={"VBUS":("Supply conductor, nominal 5 V in this model; all VBUS contacts share a net.","Przewód zasilania, nominalnie 5 V w modelu; styki VBUS są wspólne."),
        "GND":("Power return and signal reference; all GND contacts share a net.","Powrót zasilania i masa sygnałów; styki GND są wspólne."),
        "D+":("Positive member of the USB 2.0 differential data pair; not a supply pin.","Dodatnia linia różnicowej pary danych USB 2.0; nie służy do zasilania."),
        "D−":("Negative member of the USB 2.0 differential data pair; not ground.","Ujemna linia różnicowej pary danych USB 2.0; nie jest masą."),
        "ID":("USB OTG role-identification contact; not emulated.","Styk identyfikacji roli USB OTG; funkcja nieemulowana."),
        "SHIELD":("Metal connector shell/cable screen; grounding depends on the hardware design.","Metalowa obudowa i ekran kabla; sposób połączenia z masą zależy od konstrukcji urządzenia.")}
    if label.startswith("CC"): role=("Configuration channel: orientation, connection and role/current advertisement; negotiation is not emulated.","Kanał konfiguracji: orientacja, wykrycie połączenia i informacje o roli/prądzie; bez emulacji negocjacji.")
    elif label.startswith(("TX","RX")): role=("High-speed differential data pair, named by transmitter/receiver role; data is not emulated.","Linia szybkiej różnicowej pary danych nadajnika/odbiornika; dane nie są emulowane.")
    elif label.startswith("SBU"): role=("Sideband-use contact for alternate modes; not emulated.","Linia pomocnicza trybów alternatywnych; funkcja nieemulowana.")
    else: role=roles.get(label,("Connector contact; verify the exact part drawing.","Styk złącza; sprawdź rysunek konkretnej części."))
    return role[language=="pl"]
