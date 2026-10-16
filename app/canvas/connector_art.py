"""Code-native connector silhouettes; decorations never create hidden pins."""
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QColor, QPen, QPolygonF, QFont

def socket(p, rect, kind):
    p.save(); ink=p.pen().color(); p.setPen(QPen(ink,1.4)); p.setBrush(Qt.BrushStyle.NoBrush)
    x,y,w,h=rect.x(),rect.y(),rect.width(),rect.height()
    kind=kind.replace("USB ","")
    # Top-down metal housing, with the connector mouth at its outer edge.
    p.drawRoundedRect(rect,2,2)
    rect=rect.adjusted(4,4,-4,-4); x,y,w,h=rect.x(),rect.y(),rect.width(),rect.height()
    if kind in {"C","Lightning"}:
        p.drawRoundedRect(rect,h/2,h/2)
    elif kind in {"Mini-B","Micro-B","HDMI"}:
        inset=.18 if kind=="Mini-B" else .12
        p.drawPolygon(QPolygonF([QPointF(x+w*a,y+h*b) for a,b in [(inset,0),(1-inset,0),(1,.6),(1-inset,1),(inset,1),(0,.6)]]))
    elif kind=="POWER": p.drawEllipse(rect)
    elif kind=="Ethernet":
        p.drawPolygon(QPolygonF([QPointF(x+w*a,y+h*b) for a,b in [(0,0),(1,0),(1,.7),(.65,.7),(.65,1),(.35,1),(.35,.7),(0,.7)]]))
    elif kind == "B":
        p.drawPolygon(QPolygonF([QPointF(x+w*.2,y),QPointF(x+w*.8,y),QPointF(x+w,y+h*.3),QPointF(x+w,y+h),QPointF(x,y+h),QPointF(x,y+h*.3)]))
    else: p.drawRect(rect)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(rect.adjusted(w*.12,h*.38,-w*.12,-h*.3),1,1)
    p.setPen(QPen(ink,1.1))
    count={"C":12,"Lightning":8,"HDMI":19,"Mini-B":5,"Micro-B":5,"Ethernet":8}.get(kind,4)
    for i in range(count):
        px=x+w*(.18+.64*i/max(1,count-1)); p.drawLine(QPointF(px,y+h*.52),QPointF(px,y+h*.76))
    # Code-native USB schematic mark, not a raster asset or copied library file.
    if kind in {'A','B','C','Mini-B','Micro-B'}:
        cx,cy=x+w*.5,y+h*.24
        p.drawLine(QPointF(cx-9,cy),QPointF(cx+8,cy))
        p.drawEllipse(QPointF(cx-9,cy),1.5,1.5)
        p.drawLine(QPointF(cx-3,cy),QPointF(cx,cy-3)); p.drawLine(QPointF(cx,cy-3),QPointF(cx+3,cy-3))
        p.drawRect(QRectF(cx+3,cy-4,2,2))
        p.drawPolygon(QPolygonF([QPointF(cx+8,cy-2),QPointF(cx+11,cy),QPointF(cx+8,cy+2)]))
    p.restore()

SOCKET_WIDTH,SOCKET_HEIGHT=46,28

def jumper_contact(p,point,gender,angle=0):
    """Identical monochrome contact geometry for plugs and goldpins."""
    p.save(); p.translate(point); p.rotate(angle); p.setBrush(Qt.BrushStyle.NoBrush)
    pen=QPen(p.pen()); pen.setWidthF(4); p.setPen(pen)
    if gender=='male':
        p.setPen(QPen(QColor('#969696'),5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(0,0),QPointF(0,35))
        p.setPen(QPen(QColor('#a6a6a6'),1)); p.setBrush(QColor('#252525'))
        p.drawRoundedRect(QRectF(-5,23,10,24),2,2)
    else:
        pen.setWidthF(2); p.setPen(pen); p.drawRect(QRectF(-5,0,10,35))
    p.restore()

def socket_regions(item,body):
    name=item.definition.name
    if name.startswith("Port USB") or name == "Port Lightning":
        kind=name.split()[-1]; width=SOCKET_WIDTH
        if item.definition.pins and all(pin.y==item.definition.height/2 for pin in item.definition.pins):
            return [(kind,QRectF(body.center().x()-width/2,body.top()-38,width,28))]
        return [(kind,QRectF(body.center().x()-width/2,body.bottom()+10,width,28))]
    elif name in {"Kostka zasilająca USB","Klawiatura USB"}:
        width=SOCKET_WIDTH
        return [("A" if name.startswith("Kostka") else "C",QRectF(body.right()-width,body.center().y()-14,width,SOCKET_HEIGHT))]
    elif "Arduino" in name or "Raspberry Pi" in name:
        kinds=("C","HDMI","A","Ethernet") if "Raspberry Pi" in name and "Pico" not in name else ("B" if "Uno" in name or "Mega" in name else "Micro-B","POWER")
        width=SOCKET_WIDTH
        total=len(kinds)*(width+6)-6
        return [(kind,QRectF(body.center().x()-total/2+index*(width+6),body.bottom()+10,width,28)) for index,kind in enumerate(kinds)]
    return []

def paint_connectors(item,p,body):
    from app.canvas.component_item import bottom_sockets
    if bottom_sockets(item.definition):
        p.save(); p.setBrush(QColor(getattr(item,"paper_color","#ffffff")))
        top=item.definition.name.startswith(("Port USB","Port Lightning")) and item.definition.pins and all(pin.y==item.definition.height/2 for pin in item.definition.pins)
        p.drawRect(QRectF(body.left(),body.top()-40 if top else body.bottom(),body.width(),40)); p.restore()
    for kind,rect in socket_regions(item,body): socket(p,rect,kind)
