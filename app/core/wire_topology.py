"""Merge deliberate collinear cable overlaps; a crossing alone never joins."""
from collections import defaultdict
from math import hypot
from app.core.models import Wire,new_id

EPS=1e-6
def point(p): return tuple(round(float(v),5) for v in p)
def overlap(a,b,c,d):
    dx,dy=b[0]-a[0],b[1]-a[1]; length=hypot(dx,dy)
    if length<EPS or any(abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))>EPS*length for p in (c,d)): return 0.
    low,high=sorted(((p[0]-a[0])*dx/length+(p[1]-a[1])*dy/length for p in (c,d)))
    return max(0,min(length,high)-max(0,low))

def merge_overlaps(sheet,seeds=(),minimum=20):
    """Split/deduplicate the edited cables' overlap groups, retaining anchors.

    Old, unedited overlapping drawings are not silently rewired. The common
    stretch becomes a real shared net, as requested for newly overlapping cables.
    """
    if not seeds: return False
    wires=list(sheet.wires); parents=list(range(len(wires))); affected=set()
    def root(i):
        while parents[i]!=i: parents[i]=parents[parents[i]]; i=parents[i]
        return i
    paths=[list(map(point,w.points or [(w.start_x,w.start_y),(w.end_x,w.end_y)])) for w in wires]
    segments=[(i,a,b) for i,path in enumerate(paths) for a,b in zip(path,path[1:]) if a!=b]
    for at,(i,a,b) in enumerate(segments):
        for j,c,d in segments[at+1:]:
            if i!=j and overlap(a,b,c,d)>minimum+EPS:
                parents[root(i)]=root(j); affected.update((i,j))
    groups=defaultdict(list)
    for i in affected: groups[root(i)].append(i)
    groups={k:indices for k,indices in groups.items() if any(wires[i].id in seeds for i in indices)}
    if not groups: return False
    replacements={}; deleted=set()
    for indices in groups.values():
        vertices={p for i in indices for p in paths[i]}; anchors=defaultdict(list); junctions=defaultdict(set)
        outside={point((getattr(w,s+'_x'),getattr(w,s+'_y'))) for j,w in enumerate(wires) if j not in indices for s in ('start','end')}
        for i in indices:
            w=wires[i]
            for side in ('start','end'):
                p=point((getattr(w,side+'_x'),getattr(w,side+'_y')))
                cid=getattr(w,side+'_component_id')
                if cid:
                    anchor=(cid,getattr(w,side+'_pin_index'),getattr(w,side+'_pin_number'))
                    if anchor not in anchors[p]: anchors[p].append(anchor)
                jid=getattr(w,side+'_junction_id')
                if jid: junctions[p].add(jid)
        edges=defaultdict(set)
        for i,a,b in segments:
            if i not in indices: continue
            dx,dy=b[0]-a[0],b[1]-a[1]; square=dx*dx+dy*dy
            split=[]
            for p in vertices:
                t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/square
                if -EPS<=t<=1+EPS and abs(dx*(p[1]-a[1])-dy*(p[0]-a[0]))<=EPS*hypot(dx,dy): split.append((t,p))
            split=[p for _,p in sorted(split)]
            for c,d in zip(split,split[1:]):
                if c!=d: edges[tuple(sorted((c,d)))].add(i)
        while True:
            adjacent=defaultdict(list)
            for edge in edges:
                for p in edge: adjacent[p].append(edge)
            removed=False
            for p,incident in adjacent.items():
                if len(incident)!=2 or p in anchors or p in junctions or p in outside: continue
                first,second=incident; a=next(q for q in first if q!=p); b=next(q for q in second if q!=p)
                if a==b or abs((p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0]))>EPS: continue
                owners=edges.pop(first)|edges.pop(second); edges[tuple(sorted((a,b)))].update(owners)
                removed=True; break
            if not removed: break
        degree=defaultdict(int)
        for edge in edges:
            for p in edge: degree[p]+=1
        nodes={p:(sorted(junctions[p])[0] if junctions.get(p) else new_id()) for p in degree if degree[p]>=3 or junctions.get(p)}
        created=[]
        for (a,b),owners in edges.items():
            group_ids={wires[i].group_id for i in owners}
            wire=Wire(*a,*b,points=[list(a),list(b)],group_id=next(iter(group_ids)) if len(group_ids)==1 else None)
            for side,p in (('start',a),('end',b)):
                if anchors.get(p):
                    cid,index,number=anchors[p][0]
                    setattr(wire,side+'_component_id',cid); setattr(wire,side+'_pin_index',index); setattr(wire,side+'_pin_number',number)
                setattr(wire,side+'_junction_id',nodes.get(p))
            created.append(wire)
        # Coincident legacy internal contacts may not have public XY pins.
        for p,items in anchors.items():
            for extra in items[1:]:
                first=items[0]
                created.append(Wire(*p,*p,points=[list(p),list(p)],start_component_id=first[0],start_pin_index=first[1],start_pin_number=first[2],end_component_id=extra[0],end_pin_index=extra[1],end_pin_number=extra[2]))
        replacements[min(indices)]=created; deleted.update(indices)
    sheet.wires=[item for i,w in enumerate(wires) for item in (replacements.get(i,[]) if i in deleted else [w])]
    return True
