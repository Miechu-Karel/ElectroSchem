"""Explicit educational reference, not a generated or certified hardware design."""
from app.libraries.built_in import AVAILABLE_ITEMS
from app.services.power_requirements import requirements

OUTPUTS=((3.3,1.5),(5.,1.5),(9.,1.5),(12.,1.5),(25.,1.))

def matches(prompt):
    req=requirements(prompt)
    return bool(req and [(o['voltage_V'],o['current_A']) for o in req['outputs']]==list(OUTPUTS))

def commands():
    ids={d.name:d.id for d in AVAILABLE_ITEMS}; lines=[]
    def add(name,key,x,y,**fields):
        import shlex
        args=dict(type=ids[name],id=key,x=x,y=y,**fields)
        lines.append('ADD_COMPONENT '+' '.join(f'{k}={shlex.quote(str(v))}' for k,v in args.items()))
    def prop(key,name,value):
        import shlex
        lines.append(f'SET_PROPERTY id={key} property={name} value={shlex.quote(str(value))}')
    def connect(a,ai,b,bi): lines.append(f'CONNECT from={a} from_pin={ai} to={b} to_pin={bi}')
    add('Zasilacz laboratoryjny','PD20',180,100,value=20,unit='V',display_name='PD 20 V / 5 A')
    prop('PD20','sim_max_current','5 A')
    add('Port USB C','USB_IN',240,370)
    connect('PD20',0,'USB_IN',3); connect('PD20',1,'USB_IN',0)
    add('Masa GND','GND',60,600); connect('USB_IN',0,'GND',0)
    add('Goldpin','J_GND',1420,820,display_name='GND')
    add('Masa GND','GND_OUT',1420,960)
    lines.append('ROTATE_COMPONENT id=J_GND angle=90'); connect('GND_OUT',0,'J_GND',1)
    for i,(voltage,current) in enumerate(OUTPUTS):
        x,y=((480+280*i,420) if i<4 else (700,820)); key=f'CV{i}'
        add('Przetwornica DC-DC Step-Up' if voltage>20 else 'Przetwornica DC-DC Step-Down',key,x,y,display_name=f'{5 if i==0 else voltage:g} V / {current:g} A capacity')
        # For 3.3 V demonstrate a converter feeding a regulator with manageable dropout.
        prop(key,'sim_output_voltage',f'{5 if i==0 else voltage:g} V')
        prop(key,'sim_max_current',f'{current:g} A'); prop(key,'sim_efficiency','0.9')
        add('Masa GND',f'GND{i}',x-20,y+120)
        connect('USB_IN',3,key,0); connect(f'GND{i}',0,key,1)
        out,pin=key,2
        if i==0:
            add('Stabilizator regulowany DC','REG33',480,660,display_name='3.3 V / 1.5 A')
            for name,value in (('sim_output_voltage','3.3 V'),('sim_dropout','0.5 V'),('sim_max_current','1.5 A')): prop('REG33',name,value)
            add('Masa GND','GND_REG',480,780)
            connect(key,2,'REG33',0); connect('GND_REG',0,'REG33',1); out,pin='REG33',2
        add('Goldpin',f'J{i}',x+40,y+(440 if i==0 else 200),display_name=f'{voltage:g} V / {current:g} A')
        lines.append(f'ROTATE_COMPONENT id=J{i} angle=270'); connect(out,pin,f'J{i}',1)
    return '\n'.join(lines)

def summary(language='en'):
    if language=='pl':
        return ('Wbudowany wzorzec edukacyjny: wspólna masa, oddzielne wyjścia 3,3/5/9/12/25 V na goldpinach. '
                'Założenie: USB-C PD 100 W, ustalone 20 V / 5 A. Negocjacja PD nie jest symulowana. '
                '68,95 W na wyjściach; z uwzględnieniem strat stabilizatora i 90% sprawności przetwornic około 79,45 W wejściowych. '
                '1,5 A / 1 A to wydajności znamionowe modeli, NIE aktywne ograniczenie prądu wyjściowego. '
                'Stabilizator 3,3 V rozprasza do 2,55 W; wymagane sprawdzenie chłodzenia i rzeczywistych parametrów części. '
                'To nie projekt gotowego urządzenia ani gwarancja bezpieczeństwa. Zmiany dopiero po Akceptuj.')
    return ('Built-in educational reference: common GND, separate 3.3/5/9/12/25 V goldpin outputs. '
            'Assumes already negotiated USB-C PD 100 W, 20 V / 5 A; no PD negotiation simulation. '
            '68.95 W output, approximately 79.45 W input including regulator/converter losses. '
            'Ratings are NOT active output current limiting. The 3.3 V regulator dissipates up to 2.55 W; '
            'real parts and cooling need verification. Not a certified hardware design. Accept is required.')
