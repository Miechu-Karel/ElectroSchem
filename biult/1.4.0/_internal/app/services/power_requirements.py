"""Conservative numeric checks for explicitly specified multi-output USB requests."""
import re

def requirements(prompt):
    text=prompt.casefold()
    if 'usb' not in text: return None
    # Only recognise the explicit 'each except X' notation. Never guess currents
    # from arbitrary prose or interpret input voltage as an output specification.
    split=re.search(r'(?:każde|każdy|each)\s+(?:oprócz|poza|except)\s*(\d+(?:[.,]\d+)?)\s*v\b',text)
    if split is None: return None
    voltages=list(dict.fromkeys(float(v.replace(',','.')) for v in re.findall(r'(\d+(?:[.,]\d+)?)\s*v\b',text[:split.start()])))
    amps=[float(v.replace(',','.')) for v in re.findall(r'(\d+(?:[.,]\d+)?)\s*a\b',text[split.end():])]
    exception=float(split[1].replace(',','.'))
    if len(voltages)<2 or len(amps)<2 or exception not in voltages or min(amps[:2])<=0: return None
    outputs=[{'voltage_V':v,'current_A':amps[1] if v==exception else amps[0]} for v in voltages]
    watts=sum(o['voltage_V']*o['current_A'] for o in outputs)
    return {'outputs':outputs,'output_power_W':round(watts,6),'minimum_input_W_at_90_percent':round(watts/.9,6),
            'rules':['Use the explicitly agreed input, not an undersized default.','USB-C PD negotiation is NOT simulated.','Goldpin TOP accepts jumpers only; draw to BOTTOM.','Current ratings are NOT hard current limiting.']}

def validate_plan(plan,request):
    req=requirements(request)
    if not req or plan['questions']: return
    tasks=' '.join(t['task']+' '+t['check'] for t in plan['tasks']).casefold()
    if 'ams1117' in tasks and any(o['voltage_V']==3.3 and o['current_A']>1 for o in req['outputs']):
        raise ValueError('AMS1117 is not a 1.5 A output solution; use a suitably rated converter.')
    for voltage,current in re.findall(r'(\d+(?:[.,]\d+)?)\s*v\s*[/,]\s*(\d+(?:[.,]\d+)?)\s*a\b',tasks):
        if float(voltage.replace(',','.'))==5 and float(current.replace(',','.'))<=10:
            raise ValueError(f'Undersized 5 V input: outputs require {req["output_power_W"]:g} W before losses.')
