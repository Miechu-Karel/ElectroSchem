"""Prefer compact orthogonal AI routes outside other symbols and labels."""
from math import hypot
from PySide6.QtCore import QPointF
from PySide6.QtGui import QTransform
from app.canvas.component_item import ComponentItem
from app.canvas.page import route_allowed
from app.canvas.routing import overlap_allowed, overlap_length, safe_route
from app.libraries.built_in import get_instance_definition


def route(project, sheet, a, b, endpoints=()):
    from app.services.layout_review import _intersects_rect
    obstacles=[]; endpoint_rects={}
    def clear_overlaps(points):
        # A short common pin stub is unavoidable for a fan-out. Outside that
        # one-cell terminal region, retain the half-cell overlap restriction.
        for wire in sheet.wires:
            old=[QPointF(*p) for p in wire.points] or [QPointF(wire.start_x,wire.start_y),QPointF(wire.end_x,wire.end_y)]
            for c,d in zip(points,points[1:]):
                for e,f in zip(old,old[1:]):
                    length=overlap_length(c,d,e,f)
                    if length<=10.000001: continue
                    shared=next((p for p in (a,b) if p in (c,d) and p in (old[0],old[-1])),None)
                    if shared is None or length>20.000001: return False
        return True
    for component in sheet.components:
        definition=get_instance_definition(component,project.custom_components)
        rect=ComponentItem.selection_rect(definition,show_name=component.show_name)
        rect=QTransform().rotate(component.rotation).mapRect(rect).translated(component.x,component.y)
        if component.id in endpoints:
            # The selectable envelope includes pin stubs and captions. Using
            # it as a solid obstacle traps ports inside their own symbol.
            body=ComponentItem.symbol_rect(definition)
            if definition.symbol in {'module','ic','connector'}: body=body.adjusted(20,0,-20,-20)
            rect=QTransform().rotate(component.rotation).mapRect(body).translated(component.x,component.y)
            endpoint_rects[component.id]=rect
        # Endpoint pins lie on the envelope edge; approach them from outside,
        # never enter a module through its body just to reach the far-side pin.
        obstacles.append(rect.adjusted(2,2,-2,-2) if component.id in endpoints else rect.adjusted(-8,-8,8,8))
    # Finite lanes around symbols and existing wires, never a random detour.
    xs={a.x()-20,a.x()+20,b.x()-20,b.x()+20}; ys={a.y()-20,a.y()+20,b.y()-20,b.y()+20}
    for rect in obstacles:
        xs.update((round(rect.left()/20)*20-20,round(rect.right()/20)*20+20))
        ys.update((round(rect.top()/20)*20-20,round(rect.bottom()/20)*20+20))
    for wire in sheet.wires:
        for x,y in wire.points:
            xs.update((x-20,x+20)); ys.update((y-20,y+20))
    def lead(point,key):
        rect=endpoint_rects.get(key)
        if rect is None: return point
        _,dx,dy=min(((abs(point.x()-rect.left()),-20,0),(abs(point.x()-rect.right()),20,0),
                     (abs(point.y()-rect.top()),0,-20),(abs(point.y()-rect.bottom()),0,20)))
        return point+QPointF(dx,dy)
    aa=lead(a,endpoints[0]) if endpoints else a
    bb=lead(b,endpoints[1]) if endpoints else b
    candidates=[]
    for start,end in ((a,b),(aa,bb)):
        prefix=[] if start==a else [a]; suffix=[] if end==b else [b]
        candidates.extend((prefix+[start,QPointF(end.x(),start.y()),end]+suffix,
                           prefix+[start,QPointF(start.x(),end.y()),end]+suffix))
        for x in sorted(xs,key=lambda x:abs(x-(a.x()+b.x())/2))[:32]:
            candidates.append(prefix+[start,QPointF(x,start.y()),QPointF(x,end.y()),end]+suffix)
        for y in sorted(ys,key=lambda y:abs(y-(a.y()+b.y())/2))[:32]:
            candidates.append(prefix+[start,QPointF(start.x(),y),QPointF(end.x(),y),end]+suffix)
    best=None; best_score=float('inf')
    for points in candidates:
        points=[p for i,p in enumerate(points) if i==0 or p!=points[i-1]]
        if not route_allowed(sheet,points) or not clear_overlaps(points): continue
        parts=list(zip(points,points[1:]))
        if any(_intersects_rect(c,d,rect) for c,d in parts for rect in obstacles): continue
        score=sum(hypot(d.x()-c.x(),d.y()-c.y()) for c,d in parts)+40*max(0,len(parts)-1)
        for wire in sheet.wires:
            old=[QPointF(*p) for p in wire.points] or [QPointF(wire.start_x,wire.start_y),QPointF(wire.end_x,wire.end_y)]
            for c,d in parts:
                for e,f in zip(old,old[1:]):
                    if c.x()==d.x() and e.y()==f.y() and min(e.x(),f.x())<c.x()<max(e.x(),f.x()) and min(c.y(),d.y())<e.y()<max(c.y(),d.y()): score+=160
                    elif c.y()==d.y() and e.x()==f.x() and min(c.x(),d.x())<e.x()<max(c.x(),d.x()) and min(e.y(),f.y())<c.y()<max(e.y(),f.y()): score+=160
        if score<best_score: best,best_score=points,score
    if best is not None: return best
    # Sparse orthogonal visibility graph: several bends can be necessary to
    # leave a port on its actual side, instead of a diagonal through the body.
    from heapq import heappush,heappop
    from app.canvas.page import drawing_contains
    axes_x=sorted(set(sorted(xs,key=lambda x:min(abs(x-a.x()),abs(x-b.x())))[:26])|{a.x(),b.x(),aa.x(),bb.x()})
    axes_y=sorted(set(sorted(ys,key=lambda y:min(abs(y-a.y()),abs(y-b.y())))[:26])|{a.y(),b.y(),aa.y(),bb.y()})
    start=(axes_x.index(a.x()),axes_y.index(a.y()),0); target=(axes_x.index(b.x()),axes_y.index(b.y()))
    costs={start:0.}; parents={}; queue=[(0.,start)]; cache={}; found=None; closed=set(); crossing_cost={}
    for _ in range(6000):
        if not queue: break
        _,state=heappop(queue); x,y,axis=state
        if state in closed: continue
        closed.add(state)
        if (x,y)==target: found=state; break
        for xx,yy,next_axis in ((x-1,y,1),(x+1,y,1),(x,y-1,2),(x,y+1,2)):
            if not 0<=xx<len(axes_x) or not 0<=yy<len(axes_y): continue
            c=QPointF(axes_x[x],axes_y[y]); d=QPointF(axes_x[xx],axes_y[yy]); key=tuple(sorted(((x,y),(xx,yy))))
            if key not in cache:
                cache[key]=drawing_contains(sheet,d) and route_allowed(sheet,[c,d]) and clear_overlaps([c,d]) and not any(_intersects_rect(c,d,rect) for rect in obstacles)
            if not cache[key]: continue
            if key not in crossing_cost:
                penalty=0
                for wire in sheet.wires:
                    old=[QPointF(*p) for p in wire.points] or [QPointF(wire.start_x,wire.start_y),QPointF(wire.end_x,wire.end_y)]
                    for e,f in zip(old,old[1:]):
                        # Count proper crossings, not shared endpoints/junctions.
                        cross=lambda u,v: u.x()*v.y()-u.y()*v.x()
                        r,s=d-c,f-e; determinant=cross(r,s)
                        if abs(determinant)>1e-9:
                            t,u=cross(e-c,s)/determinant,cross(e-c,r)/determinant
                            if 1e-6<t<1-1e-6 and 1e-6<u<1-1e-6: penalty+=160
                crossing_cost[key]=penalty
            new=(xx,yy,next_axis); value=costs[state]+abs(d.x()-c.x())+abs(d.y()-c.y())+(40 if axis and axis!=next_axis else 0)+crossing_cost[key]
            if value>=costs.get(new,float('inf')): continue
            costs[new]=value; parents[new]=state
            heappush(queue,(value+abs(d.x()-b.x())+abs(d.y()-b.y()),new))
    if found:
        points=[]
        while True:
            points.append(QPointF(axes_x[found[0]],axes_y[found[1]]))
            if found==start: break
            found=parents[found]
        points.reverse(); compact=[]
        for point in points:
            if len(compact)>1 and ((compact[-2].x()==compact[-1].x()==point.x()) or (compact[-2].y()==compact[-1].y()==point.y())): compact[-1]=point
            else: compact.append(point)
        return compact
    # Impossible legacy geometry remains flagged in the readability report.
    return safe_route(sheet,a,b)
