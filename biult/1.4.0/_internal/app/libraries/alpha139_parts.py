"""Named IC packages. Pin numbers are package-specific, never module headers.

Datasheet links are part of the catalogue; educational models are not SPICE
macromodels and protocol-only parts explicitly expose a supply envelope.
"""
TI='https://www.ti.com/lit/ds/symlink/'
ADI='https://www.analog.com/media/en/technical-documentation/data-sheets/'
MC='https://ww1.microchip.com/downloads/en/DeviceDoc/'
# chip: pins in physical order, source, package, educational function
SPECS={
 'NE567':('OUT_FILTER|LOOP_FILTER|IN|VCC|TIMING_R|TIMING_RC|GND|OUT','https://www.mikrocontroller.net/attachment/17488/NE567_SE567_2.pdf','PDIP-8 / SOIC-8','protocol'),
 'TL072':('OUT1|IN1−|IN1+|V−|IN2+|IN2−|OUT2|V+',TI+'tl072.pdf','PDIP-8 / SOIC-8','opamp'),
 'LM386':('GAIN1|IN−|IN+|GND|OUT|VCC|BYPASS|GAIN8',TI+'lm386.pdf','PDIP-8 / SOIC-8','audio'),
 'NE556':('1DISCH|1THRES|1CONT|1RESET|1OUT|1TRIG|GND|2TRIG|2OUT|2RESET|2CONT|2THRES|2DISCH|VCC',TI+'ne556.pdf','PDIP-14 / SOIC-14','dual_timer'),
 'ICL7660':('NC|CAP+|GND|CAP−|VOUT|LV|OSC|V+', 'https://www.renesas.com/en/doc/datasheet/icl7660.pdf','PDIP-8 / SOIC-8','inverter'),
 'MAX232':('C1+|V+|C1−|C2+|C2−|V−|T2OUT|R2IN|R2OUT|T2IN|T1IN|R1OUT|R1IN|T1OUT|GND|VCC',TI+'max232.pdf','PDIP-16 / SOIC-16','rs232'),
 'CD4017':('Q5|Q1|Q0|Q2|Q6|Q7|Q3|VSS|Q8|Q4|Q9|CARRY|INHIBIT|CLK|RESET|VDD',TI+'cd4017b.pdf','PDIP-16 / SOIC-16','counter'),
 '74HC165':('/LOAD|CLK|E|F|G|H|/QH|GND|QH|SER|A|B|C|D|INHIBIT|VCC',TI+'sn74hc165.pdf','PDIP-16 / SOIC-16','parallel_shift'),
 '74HC138':('A|B|C|/G2A|/G2B|G1|/Y7|GND|/Y6|/Y5|/Y4|/Y3|/Y2|/Y1|/Y0|VCC',TI+'sn74hc138.pdf','PDIP-16 / SOIC-16','decoder'),
 'CD4511':('B|C|/LT|/BI|LE|D|A|VSS|e|d|c|b|a|g|f|VDD',TI+'cd4511b.pdf','PDIP-16 / SOIC-16','seven_segment'),
 'CD4011':('1A|1B|1Y|2Y|2A|2B|VSS|3A|3B|3Y|4Y|4A|4B|VDD',TI+'cd4011b.pdf','PDIP-14 / SOIC-14','nand'),
 'ULN2003A':('1B|2B|3B|4B|5B|6B|7B|GND|COM|7C|6C|5C|4C|3C|2C|1C',TI+'uln2003a.pdf','PDIP-16 / SOIC-16','darlington'),
 'IR2101':('VCC|HIN|LIN|COM|LO|VS|HO|VB','https://www.infineon.com/assets/row/public/documents/24/49/infineon-ir2101-ds-en.pdf','PDIP-8 / SOIC-8','gate_driver'),
 'TC4420':('VDD|IN|NC|GND|GND|OUT|OUT|VDD',MC+'21419D.pdf','PDIP-8 / SOIC-8','gate_driver'),
 'DS18B20':('GND|DQ|VDD',ADI+'DS18B20.pdf','TO-92, front/flat face pin order','protocol'),
 'MAX485':('RO|/RE|DE|DI|GND|A|B|VCC',ADI+'MAX1487-MAX491.pdf','PDIP-8 / SOIC-8','rs485'),
 'MCP2515':('TXCAN|RXCAN|CLKOUT|/TX0RTS|/TX1RTS|/TX2RTS|OSC2|OSC1|VSS|/RX1BF|/RX0BF|/INT|SCK|SI|SO|/CS|/RESET|VDD',MC+'MCP2515-Stand-Alone-CAN-Controller-with-SPI-20001801J.pdf','PDIP-18 / SOIC-18','protocol'),
 'PCA9685':('|'.join([*(f'A{i}' for i in range(5)),*(f'LED{i}' for i in range(8)),'VSS',*(f'LED{i}' for i in range(8,16)),'/OE','A5','EXTCLK','SCL','SDA','VDD']),'https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf','TSSOP-28 (PW), not QFN numbering','protocol'),
 'CH340G':('GND|TXD|RXD|V3|D+|D−|XI|XO|/CTS|/DSR|/RI|/DCD|/DTR|/RTS|R232|VCC','https://www.wch-ic.com/downloads/CH340DS1_PDF.html','SOIC-16, G variant','protocol'),
 'CP2102':('|'.join(['DCD','RI','GND','D+','D−','VDD','REGIN','VBUS','/RST','NC.10','/SUSPEND','SUSPEND',*(f'NC.{i}' for i in range(13,23)),'/CTS','/RTS','RXD','TXD','DSR','DTR']),'https://www.silabs.com/documents/public/data-sheets/CP2102-9.pdf','QFN-28 classic CP2102; perimeter pins, ground pad not drawn','protocol'),
 'LM7809':('IN|GND|OUT','https://www.st.com/resource/en/datasheet/l78.pdf','TO-220, front view','regulator'),
 'LM7905':('GND|IN|OUT',TI+'lm79.pdf','TO-220, front view','negative_regulator'),
 'LM7912':('GND|IN|OUT',TI+'lm79.pdf','TO-220, front view','negative_regulator'),
 'XL4015':('GND|FB|SW|VC|VIN','https://www.xlsemi.com/datasheet/XL4015-EN.pdf','TO-263-5, tab = SW','protocol'),
 'TPS61030':('SW|SW|PGND|PGND|PGND|VBAT|LBI|SYNC|EN|LBO|GND|FB|VOUT|VOUT|VOUT|NC',TI+'tps61030.pdf','TSSOP-16 PWP; PowerPAD to PGND, not drawn','protocol'),
 'MCP73831':('STAT|VSS|VBAT|VDD|PROG',MC+'20001984g.pdf','SOT-23-5, not DFN','protocol'),
 'DS3231':('32kHz|VCC|/INT/SQW|/RST|NC.5|NC.6|NC.7|NC.8|NC.9|NC.10|NC.11|NC.12|GND|VBAT|SDA|SCL',ADI+'DS3231.pdf','SOIC-16, bare chip (not RTC module)','protocol'),
 'DS1307':('X1|X2|VBAT|GND|SDA|SCL|SQW/OUT|VCC',ADI+'DS1307.pdf','PDIP-8 / SOIC-8','protocol'),
 'AT24C256':('A0|A1|A2|GND|SDA|SCL|WP|VCC','https://www.microchip.com/en-us/product/AT24C256C','SOIC-8 / PDIP-8 family; verify suffix','protocol'),
 'W25Q128':('/CS|DO/IO1|/WP/IO2|GND|DI/IO0|CLK|/HOLD/IO3|VCC','https://www.winbond.com/hq/product/code-storage-flash-memory/serial-nor-flash/?__locale=en&partNo=W25Q128JV','W25Q128JV SOIC-8; pin 7 differs by suffix','protocol'),
}

def install(add,terminals):
    result=[]
    for chip,(pins,source,package,function) in SPECS.items():
        name='Układ Scalony '+chip
        add(name,chip+' IC',pins,symbol='ic',prefix='ic_'+chip+'__',source=source,variant=package,scope='Pins of the specified package; verify suffix and exposed pads before hardware use',verified=False)
        result.append(('Układy i sterowniki',name))
    return result

def behavior(definition):
    chip=definition.name.removeprefix('Układ Scalony ')
    if chip not in SPECS or not definition.name.startswith('Układ Scalony '): return None
    from app.libraries.simulation_catalog import P,approximate
    function=SPECS[chip][3]
    params=[P('sim_load_current','Quiescent model current','Prąd spoczynkowy modelu','A','7 mA' if chip=='NE567' else '1 mA')]
    if function in {'opamp','audio'}: params.append(P('sim_gain','Educational gain','Wzmocnienie modelu',default='20' if chip=='LM386' else '100000'))
    notes={
      'opamp':('Dual rail-clipped amplifier; no bandwidth, slew rate or common-mode model.','Dwa wzmacniacze ograniczone szynami; bez pasma, slew-rate i zakresu common-mode.'),
      'audio':('Rail-clipped gain stage centred at half supply. GAIN capacitor, audio bandwidth and loudspeaker mechanics are not modelled.','Wzmacniacz ograniczony szynami, wyjście wokół połowy zasilania. Bez modelu kondensatora GAIN, pasma audio i głośnika.'),
      'dual_timer':('Two comparator/latch timers with RESET, control divider and discharge contacts. No propagation delay.','Dwa timery komparator/przerzutnik, RESET, dzielnik CONT i rozładowanie. Bez opóźnień.'),
      'inverter':('Averaged negative-voltage source powered by the positive rail. Flying-capacitor ripple and OSC/LV behaviour are not simulated.','Uśrednione odwracanie napięcia, zasilane z dodatniej szyny. Bez tętnień i działania OSC/LV.'),
      'rs232':('Instantaneous logic/RS232 level translation; no UART frames or charge-pump capacitor transient.','Natychmiastowa translacja poziomów; bez ramek UART i stanów przejściowych pompy ładunku.'),
      'rs485':('Differential transmitter and receiver, DE and active-low RE; no UART frames or collision arbitration.','Różnicowy nadajnik i odbiornik, DE i aktywne-nisko RE; bez ramek UART i arbitrażu.'),
      'protocol':('Supply envelope only. Protocol/registers, memory contents, USB/CAN communication, PWM registers, switching power stages and charging are NOT emulated for this chip.','Wyłącznie model zasilania. Protokoły/rejestry, zawartość pamięci, komunikacja USB/CAN, rejestry PWM, stopień impulsowy i ładowanie NIE są emulowane dla tego scalaka.'),
    }
    en,pl=notes.get(function,('Ideal logic or averaged power model, finite output resistance. No propagation or thermal model.','Idealna logika lub uśredniony model zasilania, skończona rezystancja wyjścia. Bez opóźnień i modelu termicznego.'))
    if chip=='NE567':
        en='Supply load only; PLL, tone detection, timing R/C and filter dynamics are NOT emulated.'
        pl='Wyłącznie obciążenie zasilania; PLL, wykrywanie tonu, obwód R/C i dynamika filtrów NIE są emulowane.'
    return approximate('catalog_ic',params,en=en,pl=pl)
