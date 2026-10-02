"""Krótka pomoc offline: opis funkcji, nie model symulacyjny ani porada montażowa."""
from app.libraries.built_in import item_name

# Para EN/PL pozwala utrzymać treść niezależną od identyfikatorów w ELS.
SYMBOL_INFO = {
    "spst": ("An ON/OFF switch opens or closes a single electrical path. Click it in the simulation sandbox to toggle the contact.", "Łącznik ON/OFF rozwiera lub zwiera jeden tor elektryczny. W sandboxie symulacji kliknij go, aby przełączyć styk."),
    "lamp": ("An incandescent lamp emits light when current heats its filament. The alpha simulator approximates it using its hot resistance, derived from rated power and voltage.", "Żarówka świeci, gdy prąd nagrzewa włókno. Symulator alfa przybliża ją rezystancją gorącego włókna wyznaczoną z mocy i napięcia znamionowego."),
    "ac_source": ("An AC voltage source periodically reverses polarity. The simulation uses a sine wave whose RMS voltage and frequency are adjustable.", "Źródło napięcia przemiennego okresowo zmienia biegunowość. Symulacja używa sinusoidy z ustawianym napięciem skutecznym RMS i częstotliwością."),
    "resistor": ("A resistor limits current and produces a voltage drop. Its resistance is measured in ohms.", "Rezystor ogranicza prąd i powoduje spadek napięcia. Jego rezystancję podaje się w omach."),
    "capacitor": ("A capacitor stores charge. It is used for filtering, decoupling and timing; capacitance and rated voltage are separate parameters.", "Kondensator gromadzi ładunek. Służy m.in. do filtrowania, odsprzęgania i odmierzania czasu; pojemność i napięcie znamionowe to osobne parametry."),
    "polar_capacitor": ("A polarised capacitor stores charge and must be connected with the correct polarity. Observe its voltage rating.", "Kondensator polaryzowany gromadzi ładunek. Wymaga poprawnej biegunowości i nieprzekraczania napięcia znamionowego."),
    "potentiometer": ("A potentiometer is a resistive track with two ends and a movable wiper (third terminal). It works as an adjustable voltage divider; using the wiper and one end gives a variable resistance.", "Potencjometr ma ścieżkę oporową z dwoma końcami oraz ruchomy suwak (trzeci zacisk). Działa jako regulowany dzielnik napięcia; suwak i jeden koniec pozwalają uzyskać zmienną rezystancję."),
    "inductor": ("An inductor stores energy in a magnetic field and opposes changes in current.", "Cewka magazynuje energię w polu magnetycznym i przeciwdziała zmianom prądu."),
    "diode": ("A diode conducts mainly in one direction, from anode to cathode when forward biased.", "Dioda przewodzi głównie w jednym kierunku: od anody do katody przy polaryzacji przewodzenia."),
    "zener": ("A Zener diode is designed to operate in reverse breakdown, for voltage references or limiting.", "Dioda Zenera może pracować w przebiciu zaporowym, np. jako odniesienie lub ogranicznik napięcia."),
    "schottky": ("A Schottky diode uses a metal-semiconductor junction, typically giving a lower forward voltage and fast switching.", "Dioda Schottky’ego ma złącze metal–półprzewodnik; zwykle zapewnia mały spadek napięcia przewodzenia i szybkie przełączanie."),
    "led": ("An LED emits light when forward current flows. It needs current limiting; infrared LEDs emit invisible infrared light.", "LED emituje światło podczas przepływu prądu w kierunku przewodzenia. Wymaga ograniczenia prądu; LED IR emituje niewidzialną podczerwień."),
    "rgb": ("An RGB LED contains separate red, green and blue emitters. Their brightness can be combined to obtain different colours; it has no single fixed colour setting.", "LED RGB zawiera osobne diody czerwoną, zieloną i niebieską. Zmiana ich jasności pozwala mieszać kolory — nie jest to dioda o jednym wybieranym kolorze."),
    "npn": ("An NPN bipolar transistor uses base current to control collector current. It can amplify signals or operate as a switch.", "Tranzystor bipolarny NPN wykorzystuje prąd bazy do sterowania prądem kolektora. Może wzmacniać sygnały lub pracować jako przełącznik."),
    "logic_input": ("Click in the simulation to switch this ideal logic source between 0 V and 5 V.", "Kliknij w symulacji, aby przełączyć idealne źródło logiczne między 0 V i 5 V."),
    "logic_output": ("Shows LOW/HIGH relative to the implicit logic ground. It does not short the signal to ground.", "Pokazuje LOW/HIGH względem wewnętrznej masy logicznej. Nie zwiera sygnału do masy."),
    "pnp": ("A PNP bipolar transistor controls emitter-collector current through the base, with polarities opposite to an NPN transistor.", "Tranzystor bipolarny PNP steruje prądem emiter–kolektor przez bazę; biegunowości są przeciwne do tranzystora NPN."),
    "nmos": ("An N-channel MOSFET controls drain-source conduction using gate-source voltage.", "MOSFET z kanałem N steruje przewodzeniem dren–źródło napięciem bramka–źródło."),
    "pmos": ("A P-channel MOSFET controls drain-source conduction using a gate voltage negative relative to its source.", "MOSFET z kanałem P steruje przewodzeniem dren–źródło napięciem bramki ujemnym względem źródła."),
    "switch": ("Pressing this normally-open button closes the contact. In this four-pin model, pins 1/3 and 2/4 are internally paired.", "Wciśnięcie przycisku normalnie otwartego zwiera styk. W tym modelu czteropinowym pary 1/3 i 2/4 są połączone wewnętrznie."),
    "spdt": ("This switch connects the common terminal to one of two alternative contacts.", "Przełącznik łączy wspólny zacisk z jednym z dwóch pozostałych styków."),
    "relay": ("Current through the coil moves a mechanical contact. COM switches between NC (normally closed) and NO (normally open).", "Prąd cewki przestawia mechaniczny styk. COM przełącza się pomiędzy NC (normalnie zwartym) i NO (normalnie rozwartym)."),
    "opto": ("An optocoupler transfers a signal using light between an LED and a detector, providing galvanic separation between input and output.", "Transoptor przenosi sygnał światłem między LED a detektorem, zapewniając separację galwaniczną wejścia i wyjścia."),
    "battery": ("A battery or cell supplies DC electrical energy. Observe polarity and the specified voltage.", "Bateria lub akumulator dostarcza energii elektrycznej prądu stałego. Istotne są biegunowość i napięcie."),
    "crystal": ("A quartz resonator provides a stable frequency reference when used with a suitable oscillator circuit.", "Rezonator kwarcowy zapewnia stabilne odniesienie częstotliwości w odpowiednim układzie generatora."),
    "thermistor": ("An NTC thermistor decreases its resistance as temperature rises.", "Termistor NTC zmniejsza rezystancję wraz ze wzrostem temperatury."),
    "ldr": ("A photoresistor changes resistance with illumination; more light usually reduces resistance.", "Fotorezystor zmienia rezystancję pod wpływem światła; większe oświetlenie zwykle zmniejsza rezystancję."),
    "power": ("A supply symbol identifies the named power rail on the schematic.", "Symbol zasilania oznacza wskazaną szynę napięcia na schemacie."),
    "ground": ("Ground marks the circuit's reference potential; it is not necessarily protective earth.", "Masa oznacza potencjał odniesienia obwodu; nie musi oznaczać uziemienia ochronnego."),
    "thyristor": ("A thyristor is triggered by its gate and can remain conducting until current drops below the holding current.", "Tyrystor jest wyzwalany bramką i może pozostać włączony, aż prąd spadnie poniżej prądu podtrzymania."),
    "triac": ("A triac is a bidirectional thyristor-type switch, commonly used to control AC current.", "Triak jest dwukierunkowym elementem przełączającym typu tyrystorowego, często używanym do sterowania prądem przemiennym."),
}


def explanation(definition, language="en", custom=None):
    pl = language == "pl"
    name, symbol = definition.name, definition.symbol
    if name=="Moduł kamery urządzenia":
        return ("Lokalny podgląd obrazu z kamery komputera w symulacji. Uruchomienie wymaga jawnej zgody w oknie kamery. Stop lub zamknięcie okna zwalnia kamerę i cofa zgodę. Obraz pozostaje tylko w pamięci; nie jest nagrywany ani wysyłany. VCC i GND są umownymi zaciskami modelu zasilania, nie fizycznym złączem USB/CSI. Nie emuluje sterownika kamery w kodzie płytki." if pl else
                "Local live computer-camera preview in simulation. Starting requires explicit consent in the camera dialog. Stop or closing releases the camera and revokes consent. Frames remain in memory, without recording or transmission. VCC/GND are abstract power-model terminals, not a USB/CSI connector pinout. This does not emulate a board firmware camera driver.")
    if name=="Transoptor 4N35":
        return ("LED steruje światłem fototranzystorem przy separacji elektrycznej. A/K to wejście LED, C/E to kolektor i emiter, B pozwala zmieniać pracę bazy, a NC jest niepodłączony." if pl else "An LED optically drives an electrically isolated phototransistor. A/K are the LED input, C/E are collector/emitter, B exposes the base, and NC is unconnected.")
    if name=="Zasilacz Raspberry Pi USB-C 27 W":
        return ("Zasilacz dostarcza energię przez USB-C. Symbol upraszcza go do wyjścia VBUS i masy GND; model daje 5,1 V i zgłasza przekroczenie ustawionego prądu. Nie negocjuje USB PD." if pl else "A USB-C supply powers a device. This symbol exposes only VBUS and GND; its model supplies 5.1 V and reports the configured current limit. USB PD is not negotiated.")
    if name=="Gniazdo Raspberry Pi 2x20":
        return ("Złącze ma 40 niezależnych styków, odpowiadających fizycznym numerom złącza Raspberry Pi. Samo nie generuje napięcia i nie łączy pinów ze sobą." if pl else "The socket has 40 independent contacts numbered like the Raspberry Pi physical header. It neither generates voltage nor connects contacts together.")
    if name=="Moduł nadajnika IR 3-pin":
        return ("Sterownik diody podczerwonej: VCC/GND zasila moduł, DAT steruje emisją. Sygnał nośny i kodowanie pilota muszą pochodzić ze sterownika; uproszczony model pokazuje aktywność wejścia." if pl else "An infrared LED driver: VCC/GND provide power and DAT controls emission. A controller supplies carrier/remote encoding; the simplified model indicates input activity.")
    if name=="Matryca RGB WS2812B 16x16":
        return ("256 adresowalnych diod RGB. DIN odbiera szeregowe dane kolorów, DOUT przekazuje dalsze dane, a 5V/GND zasila matrycę. Model alfa8 obejmuje tylko obciążenie zasilania i licznik zmian sygnału, nie dekoduje kolorów." if pl else "256 addressable RGB LEDs. DIN receives serial colour data, DOUT forwards downstream data, and 5V/GND power the matrix. The alfa8 model only represents supply loading and signal transitions, not colour decoding.")
    if custom:
        notes = "\n\n".join(str(custom.get(k, "")).strip() for k in ("description", "behavior") if custom.get(k))
        return notes or ("Element użytkownika. Nie dodano jeszcze opisu działania." if pl else "User-defined component. No operating description has been provided.")
    if symbol.startswith("gate_"):
        rules = {
            "and": ("Output is 1 only when all inputs are 1.", "Wyjście ma stan 1 tylko wtedy, gdy wszystkie wejścia mają stan 1."),
            "or": ("Output is 1 when at least one input is 1.", "Wyjście ma stan 1, gdy co najmniej jedno wejście ma stan 1."),
            "not": ("Output is the inverse of the input.", "Wyjście jest negacją wejścia."),
            "nand": ("The inverse of AND: output is 0 only when all inputs are 1.", "Negacja AND: wyjście ma stan 0 tylko wtedy, gdy wszystkie wejścia mają stan 1."),
            "nor": ("The inverse of OR: output is 1 only when all inputs are 0.", "Negacja OR: wyjście ma stan 1 tylko wtedy, gdy wszystkie wejścia mają stan 0."),
            "xor": ("For two inputs, output is 1 when the inputs differ.", "Dla dwóch wejść wyjście ma stan 1, gdy stany wejść są różne."),
            "xnor": ("For two inputs, output is 1 when the inputs are equal.", "Dla dwóch wejść wyjście ma stan 1, gdy stany wejść są jednakowe."),
        }
        return rules[symbol[5:]][pl]
    if symbol in SYMBOL_INFO:
        return SYMBOL_INFO[symbol][pl]
    # Kolejność szczegółowych nazw ma znaczenie: serwo nie jest zwykłym silnikiem,
    # a aktywny buzzer ma generator, którego nie ma buzzer pasywny.
    descriptions = [
        ("74HC00", "Four independent two-input NAND gates in one IC package.", "Cztery niezależne, dwuwejściowe bramki NAND w jednej obudowie."),
        ("74HC04", "Six independent NOT gates (inverters). Each channel has one A input and one Y output: A=0 gives Y=1, A=1 gives Y=0. All six gates share VCC and GND. Supply range: 2 to 6 V. Do not leave unused CMOS inputs floating.", "Sześć niezależnych bramek NOT (inwerterów). Każdy kanał ma wejście A i wyjście Y: A=0 daje Y=1, A=1 daje Y=0. Wszystkie bramki mają wspólne zasilanie VCC i GND. Zakres zasilania: od 2 do 6 V. Nieużywane wejścia CMOS nie powinny pozostawać niepodłączone."),
        ("74HC02", "Four two-input NOR gates: output is high only when both inputs are low.", "Cztery dwuwejściowe bramki NOR: wyjście ma stan wysoki tylko przy obu wejściach niskich."),
        ("74HC08", "Four two-input AND gates: output is high only when both inputs are high.", "Cztery dwuwejściowe bramki AND: wyjście ma stan wysoki tylko przy obu wejściach wysokich."),
        ("74HC14", "Six Schmitt-trigger inverters. Hysteresis gives different switching thresholds for rising and falling input voltage.", "Sześć inwerterów Schmitta. Histereza daje różne progi przełączania przy rosnącym i malejącym napięciu wejściowym."),
        ("74HC32", "Four two-input OR gates: output is high when at least one input is high.", "Cztery dwuwejściowe bramki OR: wyjście ma stan wysoki, gdy co najmniej jedno wejście jest wysokie."),
        ("74HC86", "Four two-input XOR gates: output is high when the input states differ.", "Cztery dwuwejściowe bramki XOR: wyjście ma stan wysoki, gdy stany wejść się różnią."),
        ("CD4093", "Four NAND gates with Schmitt-trigger inputs. Input hysteresis improves switching with slowly varying signals.", "Cztery bramki NAND z wejściami Schmitta. Histereza wejściowa ułatwia przełączanie przy wolnozmiennych sygnałach."),
        ("74HC74", "Two D flip-flops store an input bit on a clock edge; separate preset and clear inputs override the stored state.", "Dwa przerzutniki D zapamiętują bit wejściowy przy zboczu zegara; osobne wejścia ustawiania i zerowania wymuszają stan."),
        ("74HC595", "A serial-in, parallel-out shift register stores bits shifted by a clock; a latch transfers them together to the outputs.", "Rejestr przesuwny szeregowo-równoległy zapamiętuje bity taktowane zegarem; zatrzask przenosi je razem na wyjścia."),
        ("MCP41010", "A digital potentiometer selects its wiper position using commands rather than a mechanical knob.", "Potencjometr cyfrowy ustawia pozycję suwaka poleceniami zamiast mechanicznym pokrętłem."),
        ("XR2206", "A function-generator IC produces periodic waveforms; external components set its operating frequency and waveform parameters.", "Układ generatora funkcyjnego wytwarza przebiegi okresowe; elementy zewnętrzne ustalają częstotliwość i parametry przebiegu."),
        ("L298N", "A dual H-bridge drives current through loads in either direction, for example to reverse DC motors.", "Podwójny mostek H steruje przepływem prądu obciążenia w obu kierunkach, np. zmieniając kierunek obrotu silnika DC."),
        ("Sterownik Silników Krokowych", "A stepper driver sequences winding currents in response to step/direction control and provides current control appropriate to its variant.", "Sterownik silnika krokowego ustala sekwencję prądów uzwojeń według sygnałów kroku/kierunku i reguluje prąd zgodnie z możliwościami wariantu."),
        ("HC-SR04", "An ultrasonic distance sensor measures the travel time of a transmitted pulse and its returning echo.", "Ultradźwiękowy czujnik odległości mierzy czas przelotu wysłanego impulsu i powrotu echa."),
        ("PIR", "A passive infrared motion sensor detects changes in infrared radiation within its field of view.", "Pasywny czujnik ruchu PIR wykrywa zmiany promieniowania podczerwonego w swoim polu widzenia."),
        ("DHT", "This digital sensor measures temperature and relative humidity and sends the readings to a controller.", "Czujnik cyfrowy mierzy temperaturę i wilgotność względną, a wyniki przesyła do sterownika."),
        ("DS18B20", "A digital thermometer communicates temperature readings over the 1-Wire interface.", "Termometr cyfrowy przesyła pomiary temperatury przez interfejs 1-Wire."),
        ("BH1750", "An ambient-light sensor converts illumination into a digital reading sent over I2C.", "Czujnik oświetlenia zamienia natężenie światła na odczyt cyfrowy przesyłany przez I2C."),
        ("Wilgotności Gleby", "A soil-moisture sensor estimates moisture from changes in electrical properties near its probe; calibration depends on soil and sensor type.", "Czujnik wilgotności gleby szacuje wilgotność na podstawie zmian właściwości elektrycznych przy sondzie; kalibracja zależy od gleby i typu czujnika."),
        ("MQ-2", "A heated semiconductor gas sensor changes resistance in response to several gases. It is not a selective gas analyser.", "Podgrzewany półprzewodnikowy czujnik gazów zmienia rezystancję pod wpływem różnych gazów. Nie jest selektywnym analizatorem gazu."),
        ("BME280", "Measures temperature, relative humidity and air pressure. Despite the catalogue name, it does not directly measure gas concentration or air quality.", "Mierzy temperaturę, wilgotność względną i ciśnienie. Mimo nazwy katalogowej nie mierzy bezpośrednio stężenia gazów ani jakości powietrza."),
        ("MPU6050", "Combines a three-axis accelerometer and three-axis gyroscope to measure acceleration and angular velocity.", "Łączy trójosiowy akcelerometr i trójosiowy żyroskop, mierząc przyspieszenie i prędkość kątową."),
        ("GPS", "A satellite-navigation receiver estimates position and time from signals received from navigation satellites.", "Odbiornik nawigacji satelitarnej wyznacza położenie i czas na podstawie sygnałów satelitów."),
        ("Płomienia", "An optical flame sensor responds to radiation in its sensitivity band; other light sources may also trigger it.", "Optyczny czujnik płomienia reaguje na promieniowanie w swoim zakresie czułości; inne źródła światła też mogą go pobudzić."),
        ("MAX9814", "A microphone amplifier with automatic gain control amplifies audio while adjusting gain to the signal level.", "Wzmacniacz mikrofonowy z automatyczną regulacją wzmocnienia wzmacnia dźwięk i dostosowuje wzmocnienie do poziomu sygnału."),
        ("ST1146", "A microphone sound-sensor module converts sound into an electrical signal for detection by a controller.", "Moduł czujnika dźwięku z mikrofonem zamienia dźwięk na sygnał elektryczny do odczytu przez sterownik."),
        ("Podczerwieni", "An infrared receiver detects incoming infrared radiation and produces an electrical output according to its variant.", "Odbiornik podczerwieni wykrywa padające promieniowanie IR i wytwarza wyjściowy sygnał elektryczny zgodnie ze swoim wariantem."),
        ("TP4056", "A linear charger controls the charging current and voltage for a single lithium-ion cell; protection features depend on the module variant.", "Ładowarka liniowa reguluje prąd i napięcie ładowania pojedynczego ogniwa litowo-jonowego; zabezpieczenia zależą od wariantu modułu."),
        ("Step-Down", "A switching buck converter uses an inductor and controlled switching to obtain a lower DC voltage.", "Przetwornica obniżająca buck wykorzystuje cewkę i sterowane przełączanie do uzyskania niższego napięcia stałego."),
        ("Step-Up", "A switching boost converter stores energy in an inductor and releases it to obtain a higher DC voltage.", "Przetwornica podwyższająca boost magazynuje energię w cewce i przekazuje ją na wyjście o wyższym napięciu."),
        ("Poziomów Logicznych", "A logic level converter adapts digital signal voltages between devices; it does not power the load like a DC/DC converter.", "Konwerter poziomów dopasowuje napięcia sygnałów cyfrowych między urządzeniami; nie zasila obciążenia jak przetwornica DC/DC."),
        ("Enkoder", "A rotary encoder generates pulses as it turns. The relative timing of channels A and B indicates direction.", "Enkoder obrotowy wytwarza impulsy podczas obracania. Wzajemna kolejność sygnałów A i B określa kierunek."),
        ("Bluetooth", "A Bluetooth module exchanges data over a short-range wireless radio link and exposes a host interface.", "Moduł Bluetooth wymienia dane przez bezprzewodowe łącze radiowe krótkiego zasięgu i udostępnia interfejs do sterownika."),
        ("ESP8266", "A Wi-Fi microcontroller module can run firmware and communicate over a wireless network.", "Moduł mikrokontrolera Wi-Fi może wykonywać program i komunikować się przez sieć bezprzewodową."),
        ("RFID", "An RFID reader exchanges radio signals with compatible tags to read identification or stored data.", "Czytnik RFID wymienia sygnały radiowe ze zgodnymi znacznikami, aby odczytać identyfikator lub zapisane dane."),
        ("Klawiatura", "A matrix keypad connects row and column lines when a key is pressed; scanning identifies the pressed key.", "Klawiatura matrycowa zwiera linię wiersza i kolumny po naciśnięciu przycisku; skanowanie pozwala ustalić który klawisz wciśnięto."),
        ("Kart SD", "An SD interface connects a controller to a memory card for storing and reading data.", "Interfejs SD łączy sterownik z kartą pamięci do zapisywania i odczytywania danych."),
        ("RTC", "A real-time clock maintains time and date, typically with backup power when the main circuit is off.", "Zegar czasu rzeczywistego utrzymuje czas i datę, zwykle z zasilaniem podtrzymującym po wyłączeniu głównego obwodu."),
        ("E-Paper", "An electronic-paper display changes the visible image by electrically moving particles; the image can remain without continuous refresh.", "Wyświetlacz e-paper zmienia obraz przez elektryczne przemieszczanie cząstek; obraz może pozostawać bez ciągłego odświeżania."),
        ("Matryca LED", "A matrix display lights selected row/column intersections; its driver scans and controls the LEDs.", "Matryca zapala wybrane punkty na przecięciach wierszy i kolumn; sterownik skanuje i steruje diodami."),
        ("Moduł Zasilania Stykowej", "A breadboard power module supplies its rails from an external source through onboard regulation and jumpers.", "Moduł zasilający płytkę stykową zasila jej szyny ze źródła zewnętrznego przez wbudowaną regulację i zworki."),
        ("Goldpin", "A pin header provides a detachable electrical connection between wires or circuit boards.", "Złącze goldpin zapewnia rozłączne połączenie elektryczne przewodów lub płytek."),
        ("Terminale", "Screw terminals clamp wires to create removable electrical connections.", "Złącza śrubowe zaciskają przewody, tworząc rozłączne połączenia elektryczne."),
        ("Koszyk", "A battery holder mechanically holds the cell and connects its positive and negative contacts.", "Koszyk utrzymuje ogniwo mechanicznie i udostępnia jego styki dodatni oraz ujemny."),
        ("ST1167", "Converts UART logic levels between 3.3 V and 5 V. RXI→RXO paths convert high to low; TXI↔TXO paths are bidirectional. It is not a power supply converter.", "Dopasowuje poziomy logiczne UART 3,3 V i 5 V. Tory RXI→RXO obniżają poziom, a TXI↔TXO są dwukierunkowe. Nie jest przetwornicą zasilającą."),
        ("EF90D", "A continuous-rotation servo: control pulses set rotation speed and direction, not shaft angle.", "Serwo pracy ciągłej: impulsy sterują prędkością i kierunkiem obrotu, a nie kątem wału."),
        ("Serwomechanizm", "A servo uses position feedback and a controller to move towards the position commanded by control pulses.", "Serwomechanizm wykorzystuje sprzężenie zwrotne i sterownik, aby ustawić pozycję zadaną impulsami sterującymi."),
        ("Silnik Krokowy", "A stepper motor moves in steps as its windings are energised in sequence; it needs a suitable driver.", "Silnik krokowy wykonuje kroki przy sekwencyjnym zasilaniu uzwojeń; wymaga odpowiedniego sterownika."),
        ("Buzzer Pasywny", "A passive buzzer needs an alternating drive signal to produce sound.", "Buzzer pasywny wymaga zmiennego sygnału sterującego do wytworzenia dźwięku."),
        ("Buzzer", "An active buzzer includes an oscillator and produces sound when powered as specified.", "Buzzer aktywny zawiera generator i wydaje dźwięk po podaniu przewidzianego zasilania."),
        ("ADC", "An analogue-to-digital converter represents an input voltage as a digital number relative to a reference voltage.", "Przetwornik analogowo-cyfrowy zamienia napięcie wejściowe na liczbę cyfrową względem napięcia odniesienia."),
        ("Ekspander", "A GPIO expander adds input/output pins controlled over a serial interface.", "Ekspander GPIO udostępnia dodatkowe wejścia i wyjścia sterowane przez interfejs szeregowy."),
        ("NE555", "A timer IC that can generate pulses, delays or oscillations using external resistors and capacitors.", "Układ czasowy, który wraz z rezystorami i kondensatorami może generować impulsy, opóźnienia lub oscylacje."),
        ("LM358", "A dual operational amplifier that amplifies the difference between its input voltages using an external feedback circuit.", "Podwójny wzmacniacz operacyjny wzmacniający różnicę napięć wejściowych w układzie z zewnętrznym sprzężeniem zwrotnym."),
        ("Przekaźnik", "A relay module uses a control input to switch separate contacts; supply, input polarity and contact ratings depend on the variant.", "Moduł przekaźnika steruje oddzielnymi stykami za pomocą wejścia sterującego. Zasilanie, polaryzacja wejścia i obciążalność zależą od wariantu."),
        ("Wyświetlacz", "A display presents information received from a controller through its specified interface.", "Wyświetlacz prezentuje dane otrzymane od sterownika przez wskazany interfejs."),
        ("Stabilizator", "A voltage regulator maintains a target output voltage within its input, current and thermal limits.", "Stabilizator utrzymuje zadane napięcie wyjściowe w granicach dopuszczalnego napięcia wejściowego, prądu i temperatury."),
    ]
    for token, en, polish in descriptions:
        if token == "Poziomów Logicznych" and "ST1167" in name:
            continue
        if token in name:
            return polish if pl else en
    category = definition.category
    if category == "Mikrokontrolery i SBC":
        return ("Programowalna płytka sterująca lub komputer jednopłytkowy. Wykonuje program i komunikuje się z otoczeniem przez udostępnione złącza; ich zakres jest opisany w wariancie." if pl else
                "A programmable controller board or single-board computer. It runs software and communicates through the exposed connectors described by this variant.")
    if category == "Czujniki":
        return ("Czujnik przetwarza mierzoną wielkość na sygnał elektryczny lub dane. Sprawdź interfejs, zasilanie i opis konkretnego wariantu w dokumentacji." if pl else
                "A sensor converts a measured quantity into an electrical signal or data. Check the interface, supply and exact variant in its documentation.")
    return ("Element: " if pl else "Component: ") + item_name(definition, language) + "\n\n" + (
        "Szczegółowego opisu działania nie dodano jeszcze do biblioteki. Wariant i zakres wyprowadzeń poniżej identyfikują model; pełne działanie opisuje dokumentacja producenta." if pl else
        "A detailed operating explanation is not yet available in the library. The variant and terminal scope below identify this model; consult its manufacturer documentation for full operation.")
