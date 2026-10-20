"""Movable sandbox multimeter and non-mutating terminal/wire probes."""
from math import sin,cos,pi
from PySide6.QtCore import QRectF,QPointF,Qt
from PySide6.QtGui import QColor,QPainterPath,QPen,QFont,QPolygonF
from PySide6.QtWidgets import QGraphicsObject,QGraphicsItem

class Probe(QGraphicsObject):
    def __init__(self,panel,index):
        super().__init__(); self.panel=panel; self.index=index; self.node=None; self.label=""
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(12); self.setToolTip(panel.window.t("Drag probe to a pin or wire","Przeciągnij sondę na pin lub przewód"))
    def boundingRect(self): return QRectF(-9,-49,18,51)
    def paint(self,p,o,w=None):
        p.setPen(QPen(QColor("#c7d9e7"),2)); p.drawLine(QPointF(0,0),QPointF(0,-15))
        p.setBrush(QColor("#f24e58" if self.index==0 else "#343c46")); p.setPen(QPen(QColor("#d0d5dc"),1))
        p.drawRoundedRect(QRectF(-6,-47,12,34),3,3)
        p.setBrush(QColor("#56eb92" if self.node is not None else "#89929e")); p.drawEllipse(QPointF(0,0),3,3)
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and hasattr(self.panel,"instrument"):
            self.panel.probe_moved(self); self.panel.draw_cords()
        return super().itemChange(change,value)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event); self.panel.probe_moved(self,snap=True)

class Multimeter(QGraphicsObject):
    def __init__(self,panel):
        super().__init__(); self.panel=panel
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(11)
    def boundingRect(self): return QRectF(0,0,150,210)
    def positions(self): return [QPointF(75+42*cos(-pi+i*pi/4),130+42*sin(-pi+i*pi/4)) for i in range(5)]
    def paint(self,p,o,w=None):
        p.setPen(QPen(QColor("#ce9e36"),3)); p.setBrush(QColor("#dba72c")); p.drawRoundedRect(self.boundingRect(),12,12)
        p.setPen(QColor("#102028")); f=QFont("Arial"); f.setPixelSize(11); p.setFont(f); p.drawText(QRectF(8,9,134,20),Qt.AlignmentFlag.AlignCenter,"ElektroSchem")
        p.setBrush(QColor("#b6d2b3")); p.drawRoundedRect(QRectF(10,35,130,43),3,3)
        f.setPixelSize(12); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(14,38,122,37),Qt.AlignmentFlag.AlignCenter,self.panel.reading.text()[:25])
        f.setPixelSize(13); p.setFont(f)
        for label,point in zip(("V","A","Ω","•","~"),self.positions()):
            p.drawText(QRectF(point.x()-11,point.y()-10,22,20),Qt.AlignmentFlag.AlignCenter,label)
        p.setBrush(QColor("#263440")); p.drawEllipse(QPointF(75,130),25,25)
        target=self.positions()[max(0,self.panel.mode.currentIndex())]; direction=(target-QPointF(75,130))*.5
        p.setPen(QPen(QColor("#f0f3f5"),3)); p.drawLine(QPointF(75,130),QPointF(75,130)+direction)
        p.setPen(QColor("#18202b")); p.drawText(QRectF(15,172,120,18),Qt.AlignmentFlag.AlignCenter,self.panel.window.t("Drag probes","Przesuń sondy"))
        for x,color in ((48,"#f24e58"),(102,"#232b35")):
            p.setBrush(QColor(color)); p.drawEllipse(QPointF(x,199),5,5)
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and hasattr(self.panel,"probes"): self.panel.draw_cords()
        return super().itemChange(change,value)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and QRectF(22,83,106,82).contains(event.pos()):
            i=min(range(5),key=lambda i:(event.pos()-self.positions()[i]).manhattanLength())
            self.panel.mode.setCurrentIndex(i); event.accept(); return
        super().mousePressEvent(event)

def draw_cord(item,a,b,color):
    path=QPainterPath(a); path.cubicTo(a+QPointF(0,60),b+QPointF(0,-80),b)
    item.setPath(path); item.setPen(QPen(QColor(color),2)); item.setZValue(10)

def scope_dimensions(settings):
    return {'normal':(480,260),'large':(640,350),'huge':(800,440)}.get(settings.scope_size,(480,260))

def displayed_waveform(samples,bounds,duration,autoscale):
    if duration is not None:
        from app.ui.scope_trace import acquire,automatic_duration
        if autoscale: duration=automatic_duration(samples,duration)
        samples,bounds=acquire(samples,duration,bounds,autoscale)
    return list(samples),bounds,duration

def _interpolate_values(values,fraction,span):
    if len(values)<2: return None
    span=span or max(1e-9,values[-1][0]-values[0][0])
    target=values[0][0]+max(0.,min(1.,float(fraction)))*span
    if target<values[0][0] or target>values[-1][0]: return None
    for (ta,va),(tb,vb) in zip(values,values[1:]):
        if ta<=target<=tb:
            if tb<=ta: return ta,va
            ratio=(target-ta)/(tb-ta)
            return target,va+(vb-va)*ratio
    return values[-1] if abs(target-values[-1][0])<1e-12 else None

def waveform_value_at(samples,fraction,bounds=(-10.,10.),duration=None,autoscale=False):
    """Interpolate the voltage at a horizontal fraction of the visible trace."""
    values,_,span=displayed_waveform(samples,bounds,duration,autoscale)
    return _interpolate_values(values,fraction,span)

def draw_waveform(p,rect,samples,bounds=(-10.,10.),duration=None,autoscale=False,cursor_fraction=None):
    values,bounds,span=displayed_waveform(samples,bounds,duration,autoscale)
    p.save(); p.fillRect(rect,QColor("#10151c")); f=QFont("Arial"); f.setPixelSize(11); p.setFont(f)
    plot=rect.adjusted(56,22,-12,-24); p.setPen(QPen(QColor("#263747"),1))
    for i in range(9):
        x=plot.left()+plot.width()*i/8; p.drawLine(QPointF(x,plot.top()),QPointF(x,plot.bottom()))
    for i in range(5):
        y=plot.top()+plot.height()*i/4; p.drawLine(QPointF(plot.left(),y),QPointF(plot.right(),y))
    p.setPen(QColor("#d3e1eb"))
    if len(values)<2:
        p.drawText(rect.adjusted(8,0,0,0),Qt.AlignmentFlag.AlignCenter,"V(t)"); p.restore(); return
    lo,hi=bounds
    p.drawText(QPointF(rect.left()+6,plot.top()+6),f"{hi:.3g} V"); p.drawText(QPointF(rect.left()+6,plot.bottom()),f"{lo:.3g} V")
    span=span or max(1e-9,values[-1][0]-values[0][0]); p.setPen(QPen(QColor("#65e9bf"),2))
    p.save(); p.setClipRect(plot)
    p.drawPolyline(QPolygonF([QPointF(plot.left()+(t-values[0][0])/span*plot.width(),plot.top()+(hi-v)/(hi-lo)*plot.height()) for t,v in values])); p.restore()
    if cursor_fraction is not None:
        reading=_interpolate_values(values,cursor_fraction,span)
        if reading is not None:
            time,value=reading
            x=plot.left()+(time-values[0][0])/span*plot.width()
            y=plot.top()+(hi-value)/(hi-lo)*plot.height()
            p.save(); p.setClipRect(plot)
            p.setPen(QPen(QColor("#ffd166"),1,Qt.PenStyle.DashLine)); p.drawLine(QPointF(x,plot.top()),QPointF(x,plot.bottom()))
            p.setBrush(QColor("#ffd166")); p.setPen(QPen(QColor("#10151c"),1)); p.drawEllipse(QPointF(x,y),4,4)
            p.restore(); p.setPen(QColor("#ffd166")); p.drawText(QPointF(plot.left()+5,rect.top()+14),f"{value:.4g} V")
    p.setPen(QColor("#d3e1eb")); p.drawText(QPointF(plot.left(),rect.bottom()-5),f"0 .. {span:.3g} s" if duration else f"{values[0][0]:.3g} .. {values[-1][0]:.3g} s")
    p.restore()
