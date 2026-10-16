"""Faint, clipped visual overlay only; never changes wires or electrical nets."""
from PySide6.QtCore import QRectF,QPointF
from PySide6.QtGui import QPainterPath,QPen,QColor

def draw(painter,symbols,wires,color):
    clip=QPainterPath()
    for item in symbols:
        if item.definition.symbol not in ('module','ic','connector'): continue
        path=QPainterPath()
        if item.asset_case:
            for shape in item.asset_case['shapes']:
                from app.canvas.case_shapes import path as shape_path
                path=path.united(shape_path(shape))
        else: path.addRect(item.connector_body())
        clip=clip.united(item.sceneTransform().map(path))
    painter.save(); painter.setClipPath(clip); painter.setOpacity(.32); painter.setPen(QPen(QColor(color),2))
    for item in wires: painter.drawPath(item.path())
    for item in symbols:
        if not item.asset_payload: continue
        scale=1.0
        for wire in item.asset_payload['sheet'].get('wires',[]):
            points=wire.get('points') or [[wire['start_x'],wire['start_y']],[wire['end_x'],wire['end_y']]]
            path=QPainterPath(item.mapToScene(QPointF(points[0][0]*scale,points[0][1]*scale)))
            for x,y in points[1:]: path.lineTo(item.mapToScene(QPointF(x*scale,y*scale)))
            painter.drawPath(path)
    painter.restore()
