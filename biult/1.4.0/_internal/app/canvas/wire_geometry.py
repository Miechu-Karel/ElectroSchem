"""Stretch terminal segments without throwing away the user's wire layout."""
from PySide6.QtCore import QPointF,QLineF


def compact_route(points):
    """Remove redundant bends and closed detours within one unbranched wire."""
    result=[]
    for point in points:
        p=QPointF(point)
        if result and result[-1]==p: continue
        if len(result)>2:
            incoming=QLineF(result[-1],p)
            for i in range(len(result)-2):
                kind,cross=QLineF(result[i],result[i+1]).intersects(incoming)
                if kind==QLineF.IntersectionType.BoundedIntersection:
                    result=result[:i+1]+[cross]; break
        result.append(p)
        while len(result)>=3:
            a,b,c=result[-3:]; ab=b-a; bc=c-b
            if abs(ab.x()*bc.y()-ab.y()*bc.x())>1e-6: break
            result.pop(-2)
    return result


def stretch(points,start,end):
    old=[QPointF(*p) for p in points]
    if len(old)<2:
        from app.canvas.routing import diagonal_route
        return diagonal_route(start,end)
    da,db=start-old[0],end-old[-1]
    if da==db: return compact_route([p+da for p in old])
    orthogonal=all(a.x()==b.x() or a.y()==b.y() for a,b in zip(old,old[1:]))
    if orthogonal:
        if len(old)==2:
            from app.canvas.routing import diagonal_route
            result=diagonal_route(start,end)
        else:
            result=[QPointF(p) for p in old]; result[0],result[-1]=start,end
            if old[0].x()==old[1].x(): result[1].setX(start.x())
            else: result[1].setY(start.y())
            if old[-1].x()==old[-2].x(): result[-2].setX(end.x())
            else: result[-2].setY(end.y())
    else:
        # Preserve 45-degree bends too. Replacing only endpoints turns the
        # old diagonals into arbitrary slopes after even a one-cell move.
        from app.canvas.routing import diagonal_route
        if len(old)==2: result=diagonal_route(start,end)
        else:
            result=diagonal_route(start,old[1])[:-1]+old[1:-1]+diagonal_route(old[-2],end)[1:]
    compact=compact_route(result)
    from app.canvas.routing import diagonal_route
    if any(abs(a.x()-b.x())>1e-6 and abs(a.y()-b.y())>1e-6 and abs(abs(a.x()-b.x())-abs(a.y()-b.y()))>1e-6 for a,b in zip(compact,compact[1:])):
        compact=compact_route([p for a,b in zip(compact,compact[1:]) for p in diagonal_route(a,b)])
    return compact if len(compact)>1 else [start,end]
