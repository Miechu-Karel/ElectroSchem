"""Movable USB/jumper plugs: persistent editor links or sandbox-only links."""
from copy import deepcopy
from math import cos,sin,radians,isfinite
from PySide6.QtCore import QRectF,QPointF,Qt,QTimer
from PySide6.QtGui import QColor,QPen,QPainterPath
from PySide6.QtWidgets import QGraphicsObject,QGraphicsItem
from app.canvas.connector_art import socket,socket_regions
from app.simulation.jumper import GENDERS,JUMPER_IDS,CABLE_IDS

class Plug(QGraphicsObject):
    def __init__(self,cable,side):
        super().__init__(); self.cable=cable; self.side=side
        self.kind=cable.component.properties.get("sim_usb_"+side.lower()+"_type","A" if side=="A" else "C")
        self.jumper=cable.component.library_id in JUMPER_IDS
        if self.jumper: self.kind=GENDERS[cable.component.library_id][0 if side=='A' else 1]
        from app.simulation.usb import TYPES
        if not self.jumper and self.kind not in TYPES: self.kind="A" if side=="A" else "C"
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(15); self.setToolTip(side+": "+self.kind)
        self.component=cable.component; self.setData(0,'component'); self.setData(1,self.component.id); self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True)
    def boundingRect(self): return QRectF(-10,-19,20,61) if self.jumper else QRectF(-25,-15,50,58)
    def paint(self,p,o,w=None):
        if self.jumper:
            p.setPen(QPen(QColor('#aeb7c0'),8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.FlatCap))
            if self.kind=='male': p.drawLine(QPointF(0,-16),QPointF(0,10))
            p.setPen(QPen(QColor('#aeb7c0'),1)); p.setBrush(QColor('#252525')); p.drawRoundedRect(QRectF(-7,8,14,30),2,2)
            if self.kind=='female':
                p.setPen(QPen(QColor('#aeb7c0'),1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(-5,-16,10,26))
        else:
            p.setPen(QPen(QColor("#aeb7c0"),2)); p.setBrush(QColor("#252525")); p.drawRect(QRectF(-24,-14,48,54))
            socket(p,QRectF(-23,-13,46,28),self.kind)
        label=self.cable.window.t('M','M') if self.kind=='male' else self.cable.window.t('F','Ż') if self.kind=='female' else self.kind
        p.setPen(QColor("#ffffff")); font=p.font(); font.setPixelSize(11); p.setFont(font)
        p.drawText(QRectF(-7,19,14,16) if self.jumper else QRectF(-24,10,48,18),Qt.AlignmentFlag.AlignCenter,label)
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionChange and hasattr(self.cable.window,'view') and hasattr(self.cable.window.view,'_sheet'):
            from app.canvas.page import fit_component_position,drawing_contains
            from PySide6.QtGui import QTransform
            bounds=QTransform().rotate(self.rotation()).mapRect(self.boundingRect())
            if drawing_contains(self.cable.window.view._sheet,bounds.translated(value)): return value
            point=fit_component_position(self.cable.window.view._sheet,bounds,value)
            if point is not None: return point
            return self.pos()
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged: self.cable.redraw()
        return super().itemChange(change,value)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event); self.cable.attach(self)

class UsbCable:
    def __init__(self,window,component):
        self.window=window; self.component=component
        self.prefix='jumper_' if component.library_id in JUMPER_IDS else 'usb_'
        self.path=window.scene.addPath(QPainterPath(),QPen(QColor("#657384"),7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); self.path.setZValue(10)
        self.path.component=component; self.path.setData(0,'component'); self.path.setData(1,component.id); self.path.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True)
        self.plugs=[Plug(self,s) for s in ("A","B")]
        for index,plug in enumerate(self.plugs):
            window.scene.addItem(plug); prefix=self.prefix+plug.side.lower()+"_"
            def coordinate(key,default):
                try:
                    value=float(component.properties.get(key,default))
                    return value if isfinite(value) and abs(value)<1e6 else default
                except (ValueError,TypeError): return default
            dx=coordinate(prefix+"x",-75 if index==0 else 75); dy=coordinate(prefix+"y",0)
            angle=radians(component.rotation)
            plug.setPos(component.x+dx*cos(angle)-dy*sin(angle),component.y+dx*sin(angle)+dy*cos(angle))
            target=component.properties.get(prefix+"target")
            point=self.attached_point(plug,target)
            if point is not None:
                plug.setPos(point)
                if plug.jumper: plug.setRotation(window.symbols[target].rotation()+90)
            plug.parked_pos=plug.pos()
        self.redraw()
    def redraw(self):
        if not hasattr(self,"plugs"): return
        a,b=[p.mapToScene(QPointF(0,35)) for p in self.plugs]; path=QPainterPath(a)
        path.cubicTo(a+QPointF(0,80),b+QPointF(0,80),b); self.path.setPath(path)
    def targets(self,plug):
        for cid,item in self.window.symbols.items():
            if cid==self.component.id: continue
            if plug.jumper:
                if item.definition.symbol=='goldpin':
                    gender='female' if item.definition.name=='Goldpin żeński' else 'male'
                    if gender!=plug.kind: yield cid,item.pin_positions()[0]
                elif item.definition.symbol=='breadboard' and plug.kind=='male':
                    for point in item.pin_positions(): yield cid,point
                continue
            for kind,rect in socket_regions(item,item.connector_body()):
                if kind==plug.kind: yield cid,item.mapToScene(rect.center())
    def attached_point(self,plug,target):
        points=[p for cid,p in self.targets(plug) if cid==target]
        prefix=self.prefix+plug.side.lower()+'_'
        try: index=int(self.component.properties.get(prefix+'pin','0'))
        except (ValueError,TypeError): return None
        return points[index] if 0<=index<len(points) else None
    def attach(self,plug):
        target=min(self.targets(plug),key=lambda x:(x[1]-plug.pos()).manhattanLength(),default=None)
        target=target if target and (target[1]-plug.pos()).manhattanLength()<55 else None
        prefix=self.prefix+plug.side.lower()+"_"; old=(self.component.properties.get(prefix+"target"),self.component.properties.get(prefix+'pin','0'))
        if target:
            points=[p for cid,p in self.targets(plug) if cid==target[0]]
            hole=points.index(target[1])
            for cable in self.window.usb_cables:
                for other in cable.plugs:
                    other_prefix=cable.prefix+other.side.lower()+'_'
                    if other is not plug and other.kind==plug.kind and cable.component.properties.get(other_prefix+'target')==target[0] and cable.component.properties.get(other_prefix+'pin','0')==str(hole):
                        plug.setPos(plug.parked_pos)
                        self.window.log.appendPlainText(self.window.t("Connector is occupied.","Złącze jest zajęte.")); return
            plug.setPos(target[1]); self.component.properties[prefix+"target"]=target[0]
            self.component.properties[prefix+'pin']=str(hole)
            if plug.jumper: plug.setRotation(self.window.symbols[target[0]].rotation()+90)
            self.redraw()
        else:
            self.component.properties.pop(prefix+"target",None); self.component.properties.pop(prefix+'pin',None)
        angle=radians(-self.component.rotation); dx=plug.x()-self.component.x; dy=plug.y()-self.component.y
        self.component.properties[prefix+"x"]=str(dx*cos(angle)-dy*sin(angle)); self.component.properties[prefix+"y"]=str(dx*sin(angle)+dy*cos(angle))
        plug.parked_pos=plug.pos()
        if hasattr(self.window,'cable_changed'):
            self.window.cable_changed(); return
        if old!=(self.component.properties.get(prefix+'target'),self.component.properties.get(prefix+'pin','0')):
            QTimer.singleShot(0,self.window.reconfigure_cables)

class EditorCables:
    """Small adapter; editor attachments are undoable project properties."""
    def __init__(self,view):
        self.view=view; self.scene=view.scene; self.symbols=view._component_items; self.sheet=view._sheet; self.usb_cables=[]; self.log=self
        for c in self.sheet.components:
            if c.library_id in CABLE_IDS:
                self.symbols[c.id].hide(); self.usb_cables.append(UsbCable(self,c))
    def t(self,en,pl): return pl if getattr(self.view.settings,'language','en')=='pl' else en
    def appendPlainText(self,message): self.view.setToolTip(message)
    def cable_changed(self): self.view._changed(); self.view.viewport().update()
    def refresh(self,cid):
        for cable in list(self.usb_cables):
            if cable.component.id==cid:
                for visual in [cable.path,*cable.plugs]: self.scene.removeItem(visual)
                self.usb_cables.remove(cable)
                self.usb_cables.append(UsbCable(self,cable.component))
                self.symbols[cid].hide()
                return
    def follow_targets(self):
        for cable in self.usb_cables:
            for plug in cable.plugs:
                target=cable.component.properties.get(cable.prefix+plug.side.lower()+'_target')
                point=cable.attached_point(plug,target)
                if point is not None:
                    plug.setPos(point)
                    if plug.jumper: plug.setRotation(self.symbols[target].rotation()+90)
                else:
                    angle=radians(cable.component.rotation); prefix=cable.prefix+plug.side.lower()+'_'
                    try:
                        dx=float(cable.component.properties.get(prefix+'x',-75 if plug.side=='A' else 75)); dy=float(cable.component.properties.get(prefix+'y',0))
                        if not isfinite(dx+dy) or max(abs(dx),abs(dy))>=1e6: raise ValueError()
                    except (ValueError,TypeError): dx,dy=(-75 if plug.side=='A' else 75),0
                    plug.setPos(cable.component.x+dx*cos(angle)-dy*sin(angle),cable.component.y+dx*sin(angle)+dy*cos(angle))
                angle=radians(-cable.component.rotation); dx=plug.x()-cable.component.x; dy=plug.y()-cable.component.y
                prefix=cable.prefix+plug.side.lower()+'_'
                cable.component.properties[prefix+'x']=str(dx*cos(angle)-dy*sin(angle)); cable.component.properties[prefix+'y']=str(dx*sin(angle)+dy*cos(angle))
            cable.redraw()
