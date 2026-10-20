"""Stable rising-edge acquisition with a fixed horizontal timebase."""
from math import isfinite

def automatic_duration(samples,fallback):
    data=[(t,v) for t,v in samples if isfinite(t) and isfinite(v)]
    if len(data)<4: return fallback
    recent=[p for p in data if p[0]>=data[-1][0]-max(.5,2*fallback)]
    for window in (recent,data):
        lo=min(v for _,v in window); hi=max(v for _,v in window)
        if hi-lo<1e-8: return fallback
        level=(lo+hi)/2; edges=[]
        for (ta,va),(tb,vb) in zip(window,window[1:]):
            if va<=level<vb and tb>ta: edges.append(ta+(tb-ta)*(level-va)/(vb-va))
        if len(edges)<2: continue
        periods=[b-a for a,b in zip(edges[-4:],edges[-3:])] if len(edges)>=4 else [edges[-1]-edges[-2]]
        period=sum(periods)/len(periods)
        return max(.000008,min(800.,4*period)) if period>0 else fallback
    return fallback

def acquire(samples, duration, bounds, autoscale=False):
    data=[(t,v) for t,v in samples if isfinite(t) and isfinite(v)]
    if not data: return [],bounds
    end=data[-1][0]; cutoff=end-duration
    recent=[(t,v) for t,v in data if t>=end-2*duration]
    lo=min(v for _,v in recent); hi=max(v for _,v in recent)
    level=(lo+hi)/2; start=max(data[0][0],cutoff)
    # Use the last complete rising-edge frame, interpolating the trigger instant.
    if hi-lo>1e-8:
        for (ta,va),(tb,vb) in zip(data,data[1:]):
            if va<=level<vb and tb>ta:
                crossing=ta+(tb-ta)*(level-va)/(vb-va)
                if crossing<=cutoff: start=crossing
    selected=[]
    for (ta,va),(tb,vb) in zip(data,data[1:]):
        if ta<=start<tb: selected.append((0.,va+(vb-va)*(start-ta)/(tb-ta)))
    selected.extend((t-start,v) for t,v in data if start<=t<=start+duration)
    if len(selected)>1800:
        stride=max(1,len(selected)//900); selected=selected[::stride]+[selected[-1]]
    if autoscale:
        pad=max((hi-lo)*.12,.05); bounds=(lo-pad,hi+pad)
    return selected,bounds
