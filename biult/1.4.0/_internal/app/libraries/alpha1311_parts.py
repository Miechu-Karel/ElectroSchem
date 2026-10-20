"""Alpha11 educational lab supply and single-contact jumper connectors."""
def install(add,terminals):
    parts=[]
    def part(name,en,pins,**kw):
        add(name,en,pins,**kw); parts.append(('Zasilanie i połączenia',name))
    part('Zasilacz laboratoryjny','Laboratory Power Supply',terminals(('1','+',-80,0),('2','−',80,0)),symbol='module',width=160,height=80,unit='V',variant='Educational CV/CC source; editable output voltage, current limit, frequency and waveform')
    part('Goldpin żeński','Female Gold Pin',terminals(('TOP','TOP',-40,0),('BOTTOM','BOTTOM',40,0)),symbol='goldpin',width=80,height=40,variant='Single female plug contact and PCB end, internally connected')
    contacts=[]
    for row in range(10):
        for bank,columns in (('L',range(-140,-40,20)),('R',range(60,160,20))):
            for column,x in enumerate(columns): contacts.append((f'{bank}{row+1}.{column+1}',f'{bank}{row+1}.{column+1}',x,-100+20*row))
        for rail,x in (('RL',-180),('RR',180)): contacts.append((f'{rail}.{row+1}',f'{rail}.{row+1}',x,-100+20*row))
    part('Płytka stykowa','Breadboard',terminals(*contacts),symbol='breadboard',width=440,height=280,variant='Mini breadboard: 10 rows, two independent banks of five connected holes; two independent continuous power rails. Female jumper contacts only.')
    for name,en in (('Kabel Męsko-Żeński','Male-Female Jumper Cable'),('Kabel Żeńsko-Żeński','Female-Female Jumper Cable'),('Kabel Męsko-Męski','Male-Male Jumper Cable')):
        part(name,en,terminals(('A','A',-80,0),('B','B',80,0)),symbol='connector',width=200,height=80,variant='Movable single-conductor jumper plugs; opposite-gender Goldpin contacts only')
    return parts

def behavior(d):
    from app.libraries.simulation_catalog import Behavior,P
    if d.name=='Płytka stykowa':
        return Behavior('connector',note_en='Five holes per row and bank are connected. The centre trench isolates the banks. Each side rail is continuous and independent. Plug male jumper ends into holes; no drawn wires.',note_pl='Pięć otworów w jednym rzędzie i banku jest zwarte. Rowek rozdziela banki. Każda boczna szyna jest ciągła i niezależna. Otwory przyjmują męskie końcówki kabelków, nie rysowane przewody.')
    if d.name=='Zasilacz laboratoryjny':
        return Behavior('lab_source',(P('sim_max_current','Current limit','Limit prądu','A','1 A',minimum=.001,maximum=100),P('sim_frequency','Frequency','Częstotliwość','Hz','50 Hz',minimum=.001,maximum=1e6),P('sim_waveform','Waveform','Kształt fali',default='dc',choices=(('dc','DC','Stały'),('sine','Sine','Sinusoida'),('square','Square','Prostokąt'),('triangle','Triangle','Trójkąt'),('sawtooth','Sawtooth','Piła')))),primary_unit='V',note_en='Voltage setpoint (AC RMS), current compliance limit. Ideal educational CV/CC output, not a certified supply.',note_pl='Nastawa napięcia (dla AC: RMS) i ograniczenie prądowe. Edukacyjne idealne źródło CV/CC, nie model certyfikowanego zasilacza.')
    if d.name in {'Goldpin żeński','Kabel Męsko-Żeński','Kabel Żeńsko-Żeński','Kabel Męsko-Męski'}:
        return Behavior('connector',note_en='Passive single conductor; drag plugs to opposite-gender Goldpin contacts.',note_pl='Pasywny pojedynczy przewodnik; przeciągaj końcówki na goldpiny przeciwnej płci.')
