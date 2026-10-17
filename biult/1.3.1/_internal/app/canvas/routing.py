"""Grid router with a maximum half-cell collinear cable overlap."""
from heapq import heappop, heappush
from itertools import count
from math import hypot, sqrt
from PySide6.QtCore import QPointF
from app.canvas.page import route_allowed,title_block_rect,GRID_STEP,page_rect,drawing_contains

def _compact_collinear(points):
    result=[]
    for point in points:
        p=QPointF(point)
        if result and result[-1]==p:
            continue
        while len(result)>=2:
            a,b=result[-2:]; ab=b-a; bp=p-b
            cross=ab.x()*bp.y()-ab.y()*bp.x()
            dot=ab.x()*bp.x()+ab.y()*bp.y()
            if abs(cross)>1e-6 or dot<0:
                break
            result.pop()
        result.append(p)
    return result

def overlap_length(a,b,c,d):
    dx,dy=b.x()-a.x(),b.y()-a.y(); length=hypot(dx,dy)
    if length<1e-8: return 0.
    if any(abs(dx*(p.y()-a.y())-dy*(p.x()-a.x()))>1e-6*length for p in (c,d)): return 0.
    positions=sorted(((p.x()-a.x())*dx/length+(p.y()-a.y())*dy/length for p in (c,d)))
    return max(0,min(length,positions[1])-max(0,positions[0]))

def overlap_allowed(sheet,points,exclude=()):
    points=_compact_collinear(points)
    for wire in sheet.wires:
        if wire.id in exclude: continue
        old=[QPointF(*p) for p in wire.points] if wire.points else [QPointF(wire.start_x,wire.start_y),QPointF(wire.end_x,wire.end_y)]
        old=_compact_collinear(old)
        for a,b in zip(points,points[1:]):
            if any(overlap_length(a,b,c,d)>GRID_STEP/2+1e-6 for c,d in zip(old,old[1:])): return False
    return True

def diagonal_route(a,b):
    dx,dy=b.x()-a.x(),b.y()-a.y()
    if abs(dx)<.001 or abs(dy)<.001 or abs(abs(dx)-abs(dy))<.001: return [a,b]
    # Consume the shorter axis with a true 45° diagonal; the remaining leg
    # is horizontal or vertical. The reverse candidate places that diagonal
    # at the other end when it gives a cleaner route around nearby symbols.
    step=min(abs(dx),abs(dy))
    middle=QPointF(a.x()+(step if dx>0 else -step),a.y()+(step if dy>0 else -step))
    return [a,middle,b]

def safe_route(sheet,a,b,exclude=()):
    block=title_block_rect(sheet); corner=QPointF(block.left()-GRID_STEP,block.top()-GRID_STEP)
    def candidates():
        yield diagonal_route(a,b); yield list(reversed(diagonal_route(b,a)))
        yield diagonal_route(a,corner)[:-1]+diagonal_route(corner,b)
        directions=((1,0),(0,1),(-1,0),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))
        for distance in (20,40,60,80):
            for x,y in directions:
                aa=a+QPointF(x*distance,y*distance)
                for xx,yy in directions:
                    bb=b+QPointF(xx*distance,yy*distance)
                    yield [a]+diagonal_route(aa,bb)+[b]
    def route_length(points):
        points=_compact_collinear(points)
        return sum(hypot(y.x()-x.x(),y.y()-x.y()) for x,y in zip(points,points[1:]))

    def tie_break(points):
        # Length is the primary criterion. Prefer fewer bends only when two
        # legal paths are equally long; bend aesthetics must never add distance.
        points=_compact_collinear(points); directions=[]
        for first,last in zip(points,points[1:]):
            dx,dy=last.x()-first.x(),last.y()-first.y(); length=hypot(dx,dy)
            if length>1e-8: directions.append((round(dx/length,6),round(dy/length,6)))
        bends=max(0,len(directions)-1)
        return (route_length(points),bends,len(directions))

    direct=[points for points in (diagonal_route(a,b),list(reversed(diagonal_route(b,a))))
            if route_allowed(sheet,points) and overlap_allowed(sheet,points,exclude)]
    if direct:
        return min(direct,key=tie_break)

    best=None; best_score=None
    for points in candidates():
        points=_compact_collinear(points)
        if not route_allowed(sheet,points) or not overlap_allowed(sheet,points,exclude): continue
        candidate_score=tie_break(points)
        if best_score is None or candidate_score<best_score:
            best,best_score=points,candidate_score
    # The handcrafted paths above provide a quick legal upper bound. Search
    # the complete 8-direction grid beneath that bound so a nearby detour is
    # not overlooked in favour of the old, distant corner route. A* uses the
    # exact octilinear lower bound and checks every edge against page and wire
    # overlap constraints. This pathfinding only runs when both direct routes
    # are blocked, so ordinary mouse-move previews stay cheap.
    def octile(point):
        dx,dy=abs(point.x()-b.x()),abs(point.y()-b.y())
        return max(dx,dy)+(sqrt(2)-1)*min(dx,dy)

    bounds=page_rect(sheet)
    step_size=GRID_STEP/2
    directions=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
    start=(0,0,-1)
    serial=count()
    queue=[(octile(a),0.,0, next(serial),start)]
    costs={start:(0.,0)}
    parents={}
    while queue:
        estimate,distance,bends,_,state=heappop(queue)
        limit=best_score[0] if best_score is not None else float('inf')
        if distance>limit+1e-6 or estimate>limit+1e-6:
            break
        if costs.get(state)!=(distance,bends):
            continue
        ix,iy,last_direction=state
        point=QPointF(a.x()+ix*step_size,a.y()+iy*step_size)

        connector=diagonal_route(point,b)
        if route_allowed(sheet,connector):
            prefix=[]; cursor=state
            while cursor!=start:
                prefix.append(QPointF(a.x()+cursor[0]*step_size,a.y()+cursor[1]*step_size))
                cursor=parents[cursor]
            prefix.reverse(); route=_compact_collinear([QPointF(a)]+prefix+connector[1:])
            if overlap_allowed(sheet,route,exclude):
                score=tie_break(route)
                if best_score is None or score<best_score:
                    best,best_score=route,score

        for direction,(sx,sy) in enumerate(directions):
            nx,ny=ix+sx,iy+sy
            next_point=QPointF(a.x()+nx*step_size,a.y()+ny*step_size)
            if not bounds.contains(next_point) or not drawing_contains(sheet,next_point):
                continue
            edge=[point,next_point]
            if not route_allowed(sheet,edge) or not overlap_allowed(sheet,edge,exclude):
                continue
            if last_direction==direction:
                previous=QPointF(a.x()+(ix-sx)*step_size,a.y()+(iy-sy)*step_size)
                if not overlap_allowed(sheet,[previous,point,next_point],exclude):
                    continue
            step=step_size*(sqrt(2) if sx and sy else 1)
            next_bends=bends+int(last_direction>=0 and last_direction!=direction)
            next_state=(nx,ny,direction)
            next_cost=(distance+step,next_bends)
            if next_cost>=costs.get(next_state,(float('inf'),float('inf'))):
                continue
            costs[next_state]=next_cost; parents[next_state]=state
            heappush(queue,(next_cost[0]+octile(next_point),next_cost[0],next_bends,next(serial),next_state))
    return _compact_collinear(best) if best else None

def editor_route(sheet,a,b,exclude=()):
    """Prefer a consistent start-anchored bend while the user draws a wire.

    Previously the preview switched between the two equally short direct
    doglegs when one candidate began sharing a grid cell with another wire.
    That made a bend jump from the start to the end as the pointer moved. A
    legal start-anchored dogleg is now always preferred; shared stretches are
    still merged after the route is committed. Only fall back to the full
    router when that stable shape is blocked or overlaps a wire illegally.
    """
    preferred=diagonal_route(a,b)
    if route_allowed(sheet,preferred) and overlap_allowed(sheet,preferred,exclude):
        return preferred
    return safe_route(sheet,a,b,exclude)

def preview_route(sheet,a,b):
    """Constant-time rubber-band preview; obstacle routing happens on commit."""
    return diagonal_route(a,b)
