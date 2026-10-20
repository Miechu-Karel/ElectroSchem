"""Próbkowane interfejsy SPI. Funkcje są czyste względem poprzedniego stanu.

MNA może wywołać je wiele razy w jednym kroku Newtona; zbocze jest
zatwierdzane dopiero wraz z całym krokiem symulacji przez extended.finish.
"""


def mcp3008(previous, cs, clock, data, channels, reference):
    state=dict(previous)
    if cs:
        state.update(spi_count=0,spi_command=0,spi_out=None)
    else:
        count=state.get("spi_count",0)
        command=state.get("spi_command",0)
        if clock and not previous.get("spi_clock",False):
            if count or data:
                count+=1
                if count<=5: command=(command<<1)|int(data)
            state.update(spi_count=count,spi_command=command)
        if not clock and previous.get("spi_clock",False):
            if count==6:
                channel=command&7
                signal=channels[channel]
                if not command&8: signal-=channels[channel^1]
                code=max(0,min(1023,int(1024*signal/max(reference,1e-9))))
                state.update(spi_code=code,spi_out=False)
            elif 7<=count<=16:
                state["spi_out"]=bool(state.get("spi_code",0)&(1<<(16-count)))
            elif 17<=count<=25:
                state["spi_out"]=bool(state.get("spi_code",0)&(1<<(count-16)))
            elif count>25: state["spi_out"]=False
    state.update(spi_clock=clock,spi_cs=cs)
    return state


def mcp41010(previous, cs, clock, data):
    state=dict(previous)
    state.setdefault("wiper",128)
    if not cs:
        if previous.get("spi_cs",True): state.update(spi_count=0,spi_word=0)
        if clock and not previous.get("spi_clock",False):
            state["spi_count"]=state.get("spi_count",0)+1
            state["spi_word"]=((state.get("spi_word",0)<<1)|int(data))&65535
    elif not previous.get("spi_cs",True):
        count=state.get("spi_count",0)
        word=state.get("spi_word",0)
        if count and count%16==0 and (word>>8)&1:
            command=(word>>12)&3
            if command==1: state.update(wiper=word&255,shutdown=False)
            elif command==2: state["shutdown"]=True
    state.update(spi_cs=cs,spi_clock=clock)
    return state
