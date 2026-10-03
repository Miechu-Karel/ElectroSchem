"""Single-language presentation of legacy and new diagnostic messages."""
PAIRS = (
    ("Detach the assigned code before assigning another source file.","Odłącz przypisany kod przed przypisaniem innego pliku."),
    ("Arduino .ino compilation/emulation supports Uno R3 and classic Nano only.","Kompilacja i emulacja Arduino .ino obsługuje tylko Uno R3 i klasyczne Nano."),
    ("Arduino CLI is missing. Install arduino-cli and the arduino:avr core.","Brak Arduino CLI. Zainstaluj arduino-cli i rdzeń arduino:avr."),
    ("Assign an existing Arduino .ino sketch first.","Najpierw przypisz istniejący szkic Arduino .ino."),
    ("Arduino compilation timed out","Przekroczono czas kompilacji Arduino"),
    ("Arduino compilation failed","Kompilacja Arduino nie powiodła się"),
    ("Unsupported Python import: ","Nieobsługiwany import Pythona: "),
    ("Unsupported simulated Python API: ","Nieobsługiwane symulowane API Pythona: "),
    ("No circuit is connected to the I2C API","Do API I2C nie podłączono obwodu"),
    ("Emulator timeout","Przekroczony czas emulatora"),
    ("Install Node.js and run npm ci --ignore-scripts in app/simulation/emulators","Zainstaluj Node.js i uruchom npm ci --ignore-scripts w app/simulation/emulators"),
    ("Emulator response too large","Odpowiedź emulatora jest zbyt duża"),
    ("Invalid emulator response","Niepoprawna odpowiedź emulatora"),
    ("Emulator process exited unexpectedly","Proces emulatora zakończył się nieoczekiwanie"),
    ("Invalid Intel HEX record","Niepoprawny rekord Intel HEX"),
    ("Invalid HEX checksum/length","Niepoprawna suma kontrolna lub długość HEX"),
    ("Firmware exceeds ATmega328P flash","Firmware przekracza pamięć flash ATmega328P"),
    ("Unsupported HEX record","Nieobsługiwany rekord HEX"),
    ("Incomplete/empty HEX","Niekompletny lub pusty HEX"),
    ("Invalid UF2 length","Niepoprawna długość UF2"),
    ("Invalid UF2 magic","Niepoprawny nagłówek UF2"),
    ("UF2 is not RP2040 firmware","UF2 nie zawiera firmware dla RP2040"),
    ("Invalid UF2 block/address","Niepoprawny blok lub adres UF2"),
    ("Firmware must be a file smaller than 16 MiB","Firmware musi być plikiem mniejszym niż 16 MiB"),
    ("ADC circuit coupling is not implemented in this alpha","Połączenie ADC z obwodem nie jest zaimplementowane w tej wersji alfa"),
    ("RP2040 boot ROM must be a 16 KiB binary","Boot ROM RP2040 musi być plikiem binarnym o rozmiarze 16 KiB"),
    ("Firmware requires RP2040 boot ROM: assign a legally obtained 16 KiB ROM binary","Firmware wymaga boot ROM RP2040: przypisz legalnie uzyskany plik binarny ROM o rozmiarze 16 KiB"),
    ("Firmware breakpoint / unsupported instruction","Punkt przerwania firmware lub nieobsługiwana instrukcja"),
    ("Unsupported engine","Nieobsługiwany silnik"), ("Request too large","Żądanie jest zbyt duże"),
    ("Load firmware first","Najpierw wczytaj firmware"),("Invalid time slice","Niepoprawny odcinek czasu"),
    ("Unknown command","Nieznane polecenie"),
    ("The sheet is empty","Arkusz jest pusty"), ("no simulation model","brak modelu symulacji"),
    ("Circuit","Obwód"), ("Reset or resume healthy circuits","Zresetuj lub wznów sprawne obwody"),
    ("Component does not fit this sheet; choose a larger paper size.","Element nie mieści się na arkuszu; wybierz większy format."),
    ("The selection does not fit here. Move the cursor into the drawing area.","Zaznaczenie nie mieści się tutaj. Przenieś kursor w obszar rysunku."),
    ("Unknown component in clipboard","Nieznany element w schowku"),("Unknown component","Nieznany element"),
    ("Invalid ELS object","Niepoprawny obiekt ELS"),("Incomplete ELS object","Niekompletny obiekt ELS"),
    ("Invalid project ID","Niepoprawne ID projektu"),
    ("Code folder must be an absolute path","Folder kodów musi mieć bezwzględną ścieżkę"),
    ("Component is not programmable","Element nie obsługuje programowania"),
    ("Choose a Python .py or Arduino .ino source file","Wybierz plik źródłowy Python .py lub Arduino .ino"),
    ("Unsupported ELS version","Nieobsługiwana wersja ELS"),("Invalid sheet size","Niepoprawny format arkusza"),
    ("Invalid ElectroSchem package","Niepoprawny pakiet ELS"),("ELS document exceeds size limit","Zbyt duży dokument"),
    ("Unsupported ELS package version","Nieobsługiwana wersja pakietu ELS"),("Inconsistent ELS versions","Niezgodne wersje wewnątrz ELS"),
    ("Damaged ELS file","Uszkodzony plik ELS"),("Unknown unit","Nieznana jednostka"),
    ("Use a number and SI unit, e.g. 300, 1k, 4.7uF","Podaj liczbę i jednostkę SI"),
    ("Invalid numeric value","Niepoprawna wartość"),("Singular circuit","Obwód osobliwy"),
    ("Unstable solution","Niestabilne rozwiązanie"),
    ("floating nodes or conflicting voltage sources","niepodłączone węzły lub sprzeczne źródła napięcia"),
    ("Unknown component anchor","Nieznane przyłączenie elementu"),("Invalid pin anchor","Błędne przyłączenie pinu"),
    ("Time step must be 0.1 ns … 10 ms","Krok czasowy musi wynosić od 0,1 ns do 10 ms"),
    ("Expected ","Oczekiwano "),("GPIO source too large","Kod GPIO jest zbyt duży"),
    ("GPIO source is too large","Kod GPIO jest zbyt duży"),("Board has no GND pin","Płytka nie ma pinu GND"),
    ("GPIO voltage outside model limits","Napięcie GPIO poza zakresem modelu"),
    ("GPIO overload (>40 mA model limit)","Przeciążenie GPIO (limit modelu: 40 mA)"),
    ("GPIO subset currently supports positional arguments only","Tryb GPIO obsługuje tylko argumenty pozycyjne"),
    ("Only simulated GPIO/time imports are supported","Obsługiwane są tylko importy symulowanych modułów GPIO i czasu"),
    ("Unsupported GPIO syntax","Nieobsługiwana składnia GPIO"),("Unknown GPIO pin","Nieznany pin GPIO"),
    ("Unknown GPIO variable","Nieznana zmienna GPIO"),("Unsupported GPIO expression at line","Nieobsługiwane wyrażenie GPIO w wierszu"),
    ("GPIO program must sleep/yield; instruction limit reached","Program GPIO musi oddawać sterowanie przez sleep; przekroczono limit instrukcji"),
    ("GPIO loop must sleep/yield","Pętla GPIO musi oddawać sterowanie przez sleep"),
    ("sleep must be positive and finite","Czas sleep musi być dodatni i skończony"),
    ("Unsupported GPIO call","Nieobsługiwane wywołanie GPIO"),("Unsupported GPIO statement","Nieobsługiwana instrukcja GPIO"),
    ("Assigned source file is missing","Nie znaleziono przypisanego pliku kodu"),
    ("No programmable GPIO pins in this definition","Definicja nie ma programowalnych pinów GPIO"),
    ("Code destination already exists; existing files were kept","Docelowy plik kodu już istnieje; zachowano istniejące pliki"),
    ("Invalid ELS document","Niepoprawny dokument ELS"),("Invalid sheet list","Niepoprawna lista arkuszy"),
    ("Invalid sheet ID/name","Niepoprawny identyfikator lub nazwa arkusza"),("Invalid sheet","Niepoprawny arkusz"),
    ("Too many document objects","Zbyt wiele obiektów w dokumencie"),("Duplicate/invalid object ID","Powtórzony lub niepoprawny identyfikator obiektu"),
    ("Invalid coordinate","Niepoprawna współrzędna"),("Invalid component labels","Niepoprawne podpisy elementu"),
    ("Invalid component","Niepoprawny element"),("Invalid label visibility","Niepoprawna widoczność podpisu"),
    ("Unsupported rotation","Nieobsługiwany obrót"),("Invalid wire points","Niepoprawne punkty przewodu"),
    ("Invalid wire point","Niepoprawny punkt przewodu"),("Invalid pin index","Niepoprawny indeks pinu"),
    ("Invalid connection identifier","Niepoprawny identyfikator połączenia"),("Invalid project library/counters","Niepoprawna biblioteka lub liczniki projektu"),
    ("Invalid reference counter","Niepoprawny licznik oznaczeń"),("Invalid metadata","Niepoprawne metadane"),
    ("Invalid custom library","Niepoprawna biblioteka własna"),("Duplicate custom component ID","Powtórzony identyfikator własnego elementu"),
    ("Not an ElectroSchem project","To nie jest projekt ElectroSchem"),("Settings could not be saved.","Nie udało się zapisać ustawień."),
)


def localize(message,language):
    text=str(message)
    for en,pl in sorted(PAIRS,key=lambda p:len(p[0]),reverse=True):
        text=text.replace(en+" / "+pl,pl if language=="pl" else en)
    if language=="pl":
        for en,pl in sorted(PAIRS,key=lambda p:len(p[0]),reverse=True):
            # Restrict substitutions to diagnostics; identifiers are preserved
            # by using phrases rather than splitting arbitrary '/' characters.
            if en=="Circuit": text=text.replace("Circuit: ","Obwód: ")
            else: text=text.replace(en,pl)
    else:
        for en,pl in sorted(PAIRS,key=lambda p:len(p[1]),reverse=True):
            if en=="Circuit": text=text.replace("Obwód: ","Circuit: ")
            else: text=text.replace(pl,en)
    return text
