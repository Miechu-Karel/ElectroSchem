"""User-facing names/functions, independent of permanent library IDs."""
# chip: English function, Polish function, menu family
INFO={
 'TL072':('Dual JFET operational amplifier','Podwójny wzmacniacz operacyjny JFET','amplifier'),
 'LM358':('Dual operational amplifier','Podwójny wzmacniacz operacyjny','amplifier'),
 'LM324':('Quad operational amplifier','Poczwórny wzmacniacz operacyjny','amplifier'),
 'LM386':('Audio power amplifier','Wzmacniacz mocy audio','amplifier'),
 'LM393':('Dual open-collector comparator','Podwójny komparator z otwartym kolektorem','amplifier'),
 'NE555':('Timer','Timer','timer'), 'NE556':('Dual timer','Podwójny timer','timer'),
 'NE567':('PLL tone decoder','Dekoder tonu PLL','timer'),
 'ICL7660':('Charge-pump voltage inverter','Pompa ładunku odwracająca napięcie','power'),
 'MAX232':('TTL/RS-232 transceiver','Transceiver TTL/RS-232','communication'),
 'MAX485':('RS-485 transceiver','Transceiver RS-485','communication'),
 'CD4017':('Decade counter with decoded outputs','Licznik dekadowy z dekodowanymi wyjściami','counter'),
 '74HC165':('8-bit parallel-in serial-out shift register','Rejestr przesuwny 8-bit, wejście równoległe / wyjście szeregowe','counter'),
 '74HC595':('8-bit serial-in parallel-out shift register','Rejestr przesuwny 8-bit, wejście szeregowe / wyjście równoległe','counter'),
 '74HC74':('Dual D flip-flop','Podwójny przerzutnik D','counter'),
 '74HC138':('3-to-8 decoder, active-low outputs','Dekoder 3 na 8, wyjścia aktywne nisko','decoder'),
 'CD4511':('BCD latch and seven-segment driver','Zatrzask BCD i sterownik wyświetlacza 7-segmentowego','decoder'),
 'CD4011':('Quad two-input NAND gate','Cztery bramki NAND 2-wejściowe','gates'),
 'CD4066':('Quad bilateral analog switch','Cztery dwukierunkowe klucze analogowe','analog'),
 'ULN2003A':('Seven-channel Darlington driver','Siedmiokanałowy driver Darlingtona','driver'),
 'IR2101':('High-side and low-side MOSFET gate driver','Driver bramek MOSFET high-side / low-side','driver'),
 'TC4420':('Non-inverting MOSFET gate driver','Nieodwracający driver bramki MOSFET','driver'),
 'DS18B20':('1-Wire digital thermometer','Termometr cyfrowy 1-Wire','sensor'),
 'MCP2515':('SPI CAN controller','Kontroler CAN z interfejsem SPI','communication'),
 'PCA9685':('16-channel I2C PWM controller','Kontroler PWM 16-kanałowy I2C','driver'),
 'CH340G':('USB-UART bridge','Mostek USB-UART','communication'),
 'CP2102':('USB-UART bridge','Mostek USB-UART','communication'),
 'LM7809':('Positive 9 V linear regulator','Stabilizator liniowy dodatni 9 V','power'),
 'LM7905':('Negative −5 V linear regulator','Stabilizator liniowy ujemny −5 V','power'),
 'LM7912':('Negative −12 V linear regulator','Stabilizator liniowy ujemny −12 V','power'),
 'XL4015':('Buck converter IC','Scalak przetwornicy obniżającej buck','power'),
 'TPS61030':('Boost converter IC','Scalak przetwornicy podwyższającej boost','power'),
 'MCP73831':('Single-cell Li-ion/Li-Po charger','Ładowarka jednego ogniwa Li-ion/Li-Po','power'),
 'DS3231':('Temperature-compensated I2C real-time clock','Zegar RTC I2C z kompensacją temperatury','clock'),
 'DS1307':('I2C real-time clock','Zegar RTC I2C','clock'),
 'AT24C256':('256-kbit I2C EEPROM','Pamięć EEPROM 256 kbit I2C','memory'),
 'W25Q128':('128-Mbit SPI NOR flash','Pamięć flash NOR 128 Mbit SPI','memory'),
}
FAMILIES={
 'amplifier':('Amplifiers and comparators','Wzmacniacze i komparatory'),
 'timer':('Timers and tone decoders','Timery i dekodery tonu'),
 'counter':('Counters, registers and flip-flops','Liczniki, rejestry i przerzutniki'),
 'decoder':('Decoders and display drivers','Dekodery i sterowniki wyświetlaczy'),
 'gates':('Logic ICs','Układy logiczne'),
 'analog':('Analog switches and mixed-signal ICs','Klucze analogowe i układy mieszane'),
 'driver':('Output and gate drivers','Drivery wyjść i bramek'),
 'communication':('Communication ICs','Układy komunikacyjne'),
 'power':('Power management ICs','Układy zarządzania zasilaniem'),
 'sensor':('Sensor ICs','Scalaki czujników'),
 'clock':('Real-time clock ICs','Zegary RTC'),
 'memory':('Memory ICs','Pamięci'),
}

def chip(definition):
    # Only ICs, not an existing module bearing the same chip designation.
    if definition.category!='Układy i sterowniki': return None
    return next((key for key in INFO if definition.name.endswith(' '+key)),None)

def label(definition,language):
    key=chip(definition)
    if key is None: return None
    return key+' — '+INFO[key][1 if language.startswith('pl') else 0]

def description(definition,language):
    key=chip(definition)
    if key is None: return None
    from app.libraries.simulation_catalog import behavior_for
    model=behavior_for(definition)
    pl=language.startswith('pl')
    return label(definition,language)+'\n\n'+('Wyprowadzenia odnoszą się do obudowy podanej poniżej, nie gotowego modułu. Zasilanie i interfejs sprawdź w dokumentacji producenta.\n\nOgraniczenia symulacji: ' if pl else 'Pins refer to the package below, not a ready-made module. Verify supply and interface in manufacturer documentation.\n\nSimulation limits: ')+(model.note_pl if pl else model.note_en)
