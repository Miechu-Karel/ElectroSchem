"""Educational IC models; protocol-only packages intentionally stay passive."""
from types import SimpleNamespace
from app.libraries.alpha139_parts import SPECS


def linearize(d, volts, ground, time, dt):
    from app.simulation.extended import Branch, linearize as extended
    p, n = d.parameters, d.parameters['pins']
    chip = p['name'].removeprefix('Układ Scalony ')
    function = SPECS[chip][3]
    low = next((n[x] for x in ('GND','VSS','COM','PGND','V−') if x in n), ground)
    high = next((n[x] for x in ('VCC','VDD','VIN','VBAT','V+') if x in n), low)
    branches, trial = [], dict(d.state)
    def v(a, b=low): return volts.get(a,0)-volts.get(b,0)
    def branch(a,b,g,offset=0,controls=None):
        item=Branch(a,b,g,offset,controls or {}); branches.append(item); return item
    def bit(label): return v(n[label]) > max(1, v(high)*.5)
    enabled=v(high)>1
    # Every unused input remains high impedance, never a hidden power source.
    for node in set(d.nodes): branch(node,low,1e-12)
    branch(high,low,1e-12,p['sim_load_current'] if enabled else 0)
    def drive(label, state, active=True):
        branch(n[label],high if state else low,.04 if enabled and active else 1e-12)
    trial['powered']=enabled
    if function == 'opamp':
        for i in (1,2):
            plus,minus,out=n[f'IN{i}+'],n[f'IN{i}−'],n[f'OUT{i}']
            target=p['sim_gain']*v(plus,minus)
            if not enabled: branch(out,low,1e-12)
            elif target <= volts.get(low,0): branch(out,low,.04)
            elif target >= volts.get(high,0): branch(out,high,.04)
            else: branch(out,ground,.04,0,{plus:-.04*p['sim_gain'],minus:.04*p['sim_gain']})
    elif function == 'audio':
        target=max(0,min(v(high),v(high)*.5+p['sim_gain']*v(n['IN+'],n['IN−'])))
        branch(n['OUT'],low,.04 if enabled else 1e-12,-.04*target if enabled else 0)
    elif function == 'dual_timer':
        for channel in (1,2):
            pins={label:n[f'{channel}{label}'] for label in ('DISCH','THRES','CONT','RESET','OUT','TRIG')}
            pins.update(GND=low,VCC=high)
            child=SimpleNamespace(parameters={**p,'pins':pins},kind='timer555',state=d.state.get(f'timer{channel}',{}))
            items,state=extended(child,volts,ground,time,dt)
            branches.extend(items); trial[f'timer{channel}']=state
    elif function == 'nand':
        for i in range(1,5): drive(f'{i}Y',not(bit(f'{i}A') and bit(f'{i}B')))
    elif function == 'decoder':
        address=sum(int(bit(label))<<i for i,label in enumerate('ABC'))
        active=bit('G1') and not bit('/G2A') and not bit('/G2B')
        for i in range(8): drive(f'/Y{i}',not(active and address==i))
    elif function in {'counter','parallel_shift'}:
        rising=bit('CLK') and not d.state.get('clock',False)
        trial['clock']=bit('CLK')
        if function=='counter':
            count=0 if bit('RESET') else d.state.get('count',0)
            if not bit('RESET') and rising and not bit('INHIBIT') and enabled: count=(count+1)%10
            trial['count']=count
            for i in range(10): drive(f'Q{i}',count==i)
            drive('CARRY',count<5)
        else:
            shift=d.state.get('shift',0)
            if not bit('/LOAD'): shift=sum(int(bit(label))<<i for i,label in enumerate('ABCDEFGH'))
            elif rising and not bit('INHIBIT') and enabled: shift=((shift<<1)|int(bit('SER')))&255
            trial['shift']=shift; drive('QH',bool(shift&128)); drive('/QH',not bool(shift&128))
    elif function=='seven_segment':
        code=d.state.get('code',0) if bit('LE') else sum(int(bit(label))<<i for i,label in enumerate('ABCD'))
        trial['code']=code
        patterns=('abcdef','bc','abdeg','abcdg','bcfg','acdfg','acdefg','abc','abcdefg','abcdfg')
        pattern=patterns[code] if code<10 else ''
        if not bit('/LT'): pattern='abcdefg'
        if not bit('/BI'): pattern=''
        for label in 'abcdefg': drive(label,label in pattern)
    elif function=='darlington':
        for i in range(1,8):
            branch(n[f'{i}B'],low,1/2700)
            branch(n[f'{i}C'],low,.2 if v(n[f'{i}B'])>.7 else 1e-12)
            if v(n[f'{i}C'],n['COM'])>.7: branch(n[f'{i}C'],n['COM'],.1,-.07)
    elif function=='gate_driver':
        if chip=='TC4420': drive('OUT',bit('IN'))
        else:
            drive('LO',bit('LIN'))
            branch(n['HO'],n['VB'] if bit('HIN') else n['VS'],.04 if enabled and v(n['VB'],n['VS'])>1 else 1e-12)
    elif function=='rs485':
        drive('A',bit('DI'),bit('DE')); drive('B',not bit('DI'),bit('DE'))
        drive('RO',v(n['A'],n['B'])>.2,not bit('/RE'))
    elif function=='rs232':
        level=min(7,max(0,v(high)*2))
        for i in (1,2):
            branch(n[f'T{i}OUT'],low,.04 if enabled else 1e-12,.04*level*(1 if bit(f'T{i}IN') else -1) if enabled else 0)
            drive(f'R{i}OUT',v(n[f'R{i}IN'])<0)
    elif function in {'regulator','negative_regulator','inverter'}:
        source=n['IN'] if 'IN' in n else high
        negative=function in {'negative_regulator','inverter'}
        supply=v(source)
        target=(-abs(supply) if function=='inverter' else -float(chip[-2:]) if negative else 9)
        available=max(0,abs(supply)-(0 if function=='inverter' else 2))
        target=max(-available,min(available,target))
        active=supply< -2 if function=='negative_regulator' else supply>1
        out=n['VOUT'] if function=='inverter' else n['OUT']
        output=branch(out,low,.1 if active else 1e-12,-.1*target if active else 0)
        # Input power equals output power in this averaged, lossless envelope.
        if active:
            ratio=target/supply
            branch(source,low,0,-ratio*output.offset,{out:-ratio*output.g,low:ratio*output.g})
        trial['powered']=active
    return branches,trial


def finish(d, branches, trial, volts, result, dt, translate):
    chip=d.parameters['name'].removeprefix('Układ Scalony ')
    if SPECS[chip][3]=='dual_timer':
        n=d.parameters['pins']
        for channel in (1,2):
            trial[f'timer{channel}']['timer_inputs']={label:volts.get(n[f'{channel}{label}'],0)-volts.get(n['GND'],0) for label in ('CONT','TRIG','THRES','RESET')}
    result.currents[d.component.id]=sum(b.current(volts) for b in branches if b.a==d.parameters['pins'].get('VCC',-1))
    text=translate('Supply only; protocol not emulated','Tylko zasilanie; protokół nieemulowany') if SPECS[chip][3]=='protocol' else translate('Educational IC model','Edukacyjny model scalaka')
    result.readings[d.component.id]=text
    d.state=trial
