"""Shared native-vector geometry for saved asset cases and their editor."""
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QPainterPath

def path(shape):
    result=QPainterPath()
    if shape['kind']=='path':
        points=shape['points']; result.moveTo(QPointF(*points[0]))
        for point in points[1:]: result.lineTo(QPointF(*point))
        if shape.get('closed'): result.closeSubpath()
    elif shape['kind']=='circle': result.addEllipse(QRectF(*shape['rect']))
    else: result.addRect(QRectF(*shape['rect']))
    return result

def outline(shapes):
    """Boolean union removes edges inside overlapping case primitives."""
    result=QPainterPath(); strokes=QPainterPath()
    for shape in shapes:
        drawing=path(shape)
        if shape['kind']=='path' and len(shape['points'])==2:
            strokes.addPath(drawing); continue
        # A pencil trace defines an envelope, never interior construction lines.
        drawing.closeSubpath(); drawing.setFillRule(Qt.FillRule.WindingFill)
        result=result.united(drawing)
    contours=[]
    for polygon in result.simplified().toSubpathPolygons():
        contour=QPainterPath(); contour.addPolygon(polygon); contour.closeSubpath()
        contours.append(contour)
    outer=QPainterPath()
    for contour in sorted(contours,key=lambda p:p.boundingRect().width()*p.boundingRect().height(),reverse=True):
        if outer.contains(contour): continue
        outer=outer.united(contour)
    return outer,strokes.subtracted(outer)


def pin_root(shapes,point):
    """Closest shell edge on a cardinal ray; terminal location stays electrical."""
    body,_=outline(shapes)
    candidates=[]
    for polygon in body.toSubpathPolygons():
        for a,b in zip(polygon, list(polygon)[1:]):
            if abs(b.y()-a.y())>1e-8:
                t=(point.y()-a.y())/(b.y()-a.y())
                if 0<=t<=1: candidates.append(QPointF(a.x()+t*(b.x()-a.x()),point.y()))
            if abs(b.x()-a.x())>1e-8:
                t=(point.x()-a.x())/(b.x()-a.x())
                if 0<=t<=1: candidates.append(QPointF(point.x(),a.y()+t*(b.y()-a.y())))
    root=min(candidates,key=lambda p:(p-point).manhattanLength(),default=point)
    if (root-point).manhattanLength()<.01:
        for step in (QPointF(20,0),QPointF(-20,0),QPointF(0,20),QPointF(0,-20)):
            if body.contains(point+step): return point+step
    return root
