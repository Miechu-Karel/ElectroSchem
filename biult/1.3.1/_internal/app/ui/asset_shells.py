"""Preserve saved asset shells in the sandbox while solving expanded contents."""
from copy import deepcopy
from uuid import uuid5,NAMESPACE_URL
from PySide6.QtCore import QPointF,QRectF,Qt,QEvent
from PySide6.QtGui import QPainterPath,QKeyEvent,QColor,QPen,QBrush,QRadialGradient
from app.canvas.component_item import ComponentItem
from app.core.assets import instantiate

class CaseShell(ComponentItem):
    def __init__(self,window,instance,contents,definition):
        super().__init__(deepcopy(instance),language='pl' if window.pl else 'en',custom_components=window.custom)
        # Match the deterministic IDs used by instantiate()/expand_assets()
        # explicitly; relying on two component lists staying in identical
        # order can bind a case window to a sibling LED in another module.
        self.window=window; self.targets={raw['id']:str(uuid5(NAMESPACE_URL,instance.id+":"+raw['id'])) for raw in definition['asset']['sheet']['components']}; self.pressed=None; self.result=None; self.interaction_controls=[]
        self.setFlag(self.GraphicsItemFlag.ItemIsFocusable,True)
    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        for region in (self.asset_case or {}).get('regions',[]):
            rect=QRectF(*region['rect']); cid=self.targets.get(region['component']); result=self.result
            # Match standalone LED visibility: the engine may report tiny
            # positive leakage current for an electrically-off LED. Treating
            # every value > 0 as lit made the case window glow at full strength.
            value=max(0.,min(1.,float(result.brightness.get(cid,0) if result else 0)))
            lit=value>.001
            color=QColor('#34424d')
            if region['kind']=='light' and lit:
                from app.core.led_colors import color_key
                item=self.window.symbols.get(cid); key=color_key(item.component.properties.get('color','')) if item else ''
                colors={'red':'#ff4433','green':'#48ff55','blue':'#4488ff','yellow':'#ffee44','white':'#ffffff','orange':'#ff9922','ir':'#9f63cb'}
                color=QColor(colors.get(key,'#ffd166'))
                color.setAlphaF(min(1.,.65+value*.35))
            if region['kind']=='light' and lit and result and cid in getattr(result,'rgb',{}):
                rgb=result.rgb[cid]; peak=max(rgb) or 1.; color=QColor.fromRgbF(*(max(0.,min(1.,float(v)/peak)) for v in rgb[:3]))
            # The regular component halo applies this same brightness alpha
            # after its optional RGB colour override. fromRgbF defaults to
            # opaque, so doing this afterward is essential for RGB windows.
            if region['kind']=='light' and lit:
                color.setAlphaF(min(1.,.65+value*.35))
            painter.setPen(QPen(QColor('#bdcbd4'),1.5)); painter.setBrush(color)
            if region['kind']=='light':
                painter.drawEllipse(rect)
                if lit:
                    intensity=value
                    glow_color=QColor(color); glow_color.setAlphaF(min(1.,.65+intensity*.35))
                    center=QPointF(rect.center()); gradient=QRadialGradient(center,max(1.,max(rect.width(),rect.height())*.55))
                    gradient.setColorAt(0,QColor('#ffffff')); gradient.setColorAt(.18,glow_color)
                    gradient.setColorAt(.55,glow_color); gradient.setColorAt(1,QColor(0,0,0,0))
                    painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(gradient)); painter.drawEllipse(rect)
            else:
                item=self.window.symbols.get(cid)
                device=next((d for d in getattr(getattr(self.window,'circuit',None),'devices',()) if d.component.id==cid),None)
                active=False
                if device:
                    if device.kind in {'tactile','joystick','switch','spdt','encoder','ir_receiver'}: active=bool(device.closed)
                    elif device.kind=='multi_switch': active=int(device.parameters.get('sim_position','0'))>0
                    elif device.kind=='digital_sensor': active=device.parameters.get('sim_active')=='true'
                    elif device.kind=='keypad': active=device.parameters.get('sim_key','none')!='none'
                    elif device.parameters.get('logic_input'): active=float(device.parameters.get('value',0))>2.5
                if active: painter.setBrush(QColor('#8d5bc4'))
                painter.drawRect(rect)
    def shape(self):
        drawing=super().shape()
        for region in (self.asset_case or {}).get('regions',[]):
            area=QPainterPath(); area.addRect(QRectF(*region['rect'])); drawing=drawing.united(area)
        return drawing
    def activate_at(self,point):
        for region in (self.asset_case or {}).get('regions',[]):
            if region['kind']=='interaction' and QRectF(*region['rect']).contains(point):
                self.release_input(); self.setFocus(); cid=self.targets.get(region['component'])
                if cid in self.window.symbols:
                    # Use the same simulation input dispatcher as clicking the
                    # real, expanded component, not a synthetic keyboard E.
                    item=self.window.symbols.get(cid)
                    devices=getattr(getattr(self.window,'circuit',None),'devices',())
                    device=next((d for d in devices if d.component.id==cid),None)
                    if device and device.kind in {'tactile','joystick'}:
                        self.pressed=cid
                        self.window.set_simulation_input(cid,'sim_closed',True)
                    elif device is None and getattr(item,'held',None):
                        from app.libraries.simulation_catalog import behavior_for
                        model=behavior_for(item.definition)
                        if model and model.kind in {'tactile','joystick'}:
                            self.pressed=cid
                            item.held(cid,'sim_closed',True)
                        else:
                            toggle=getattr(self.window,'toggle',None)
                            if toggle: toggle(cid)
                    else:
                        toggle=getattr(self.window,'toggle',None)
                        if toggle: toggle(cid)
                    self.update(); return True
        return False
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            if self.activate_at(event.pos()): event.accept(); return
        super().mousePressEvent(event)
    def release_input(self):
        if self.pressed:
            setter=getattr(self.window,'set_simulation_input',None)
            if setter: setter(self.pressed,'sim_closed',False)
            else:
                item=self.window.symbols.get(self.pressed)
                held=getattr(item,'held',None) if item else None
                if held: held(self.pressed,'sim_closed',False)
            self.pressed=None; self.update()
    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_E: self.release_input(); event.accept(); return
        super().keyReleaseEvent(event)
    def mouseReleaseEvent(self,event): self.release_input(); super().mouseReleaseEvent(event)
    def focusOutEvent(self,event): self.release_input(); super().focusOutEvent(event)

def create(window):
    definitions={d['id']:d for d in window.custom if isinstance(d,dict) and d.get('asset',{}).get('boxed')}
    window.asset_cases={}; window.hidden_asset_contents=set()
    for instance in window.initial_sheet.components:
        definition=definitions.get(instance.library_id)
        if not definition: continue
        contents,_=instantiate(definition['asset'],instance)
        window.hidden_asset_contents.update(c.id for c in contents.components)
        shell=CaseShell(window,instance,contents,definition)
        shell.ink_color='#d6e2eb'; shell.paper_color='#0f161e'; shell.setZValue(4)
        shell.setFlag(shell.GraphicsItemFlag.ItemIsMovable,False)
        window.scene.addItem(shell); window.asset_cases[instance.id]=shell
        # Reuse the exact same simulation dial from the expanded component,
        # but mount it in the drawn interaction window instead of above the
        # hidden internal symbol. This keeps one input state and one widget.
        regions={r.get('component'):r for r in definition['asset'].get('case',{}).get('regions',[]) if r.get('kind')=='interaction'}
        from PySide6.QtWidgets import QWidget,QVBoxLayout,QGraphicsProxyWidget
        for raw_id,cid in shell.targets.items():
            region=regions.get(raw_id); panel=window.controls.get(cid)
            if not region or panel is None: continue
            rect=QRectF(*region['rect']); proxy=None; overlay=None
            if hasattr(panel,'dial'):
                dial=panel.dial; label=getattr(panel,'position_label',None)
                for child in (label,dial):
                    if child is not None and panel.layout(): panel.layout().removeWidget(child)
                overlay=QWidget(); layout=QVBoxLayout(overlay); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
                if label is not None: layout.addWidget(label)
                layout.addWidget(dial)
                overlay.adjustSize()
                proxy=QGraphicsProxyWidget(shell); proxy.setWidget(overlay)
            elif hasattr(panel,'joystick'):
                overlay=QWidget(); layout=QVBoxLayout(overlay); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
                for child in (panel.joystick,panel.switch_button,panel.switch_state):
                    panel.layout().removeWidget(child); layout.addWidget(child)
                overlay.adjustSize()
                proxy=QGraphicsProxyWidget(shell); proxy.setWidget(overlay)
            elif hasattr(panel,'keys'):
                proxy=panel.graphics_proxy; proxy.setParentItem(shell); overlay=panel
            if proxy is None: continue
            proxy.setZValue(10)
            widget=proxy.widget(); scale=min(rect.width()/max(1,widget.width()),rect.height()/max(1,widget.height()),1.)
            proxy.setScale(max(.2,scale))
            proxy.setPos(rect.center().x()-widget.width()*proxy.scale()/2,rect.center().y()-widget.height()*proxy.scale()/2)
            shell.interaction_controls.append((cid,proxy,overlay))
    originals={w.id:w for w in window.initial_sheet.wires}
    for wire in window.sheet.wires:
        item=window.wires[wire.id]; raw=originals.get(wire.id)
        if raw and (raw.start_component_id in window.asset_cases or raw.end_component_id in window.asset_cases):
            points=raw.points or [[raw.start_x,raw.start_y],[raw.end_x,raw.end_y]]
            route=QPainterPath(QPointF(*points[0]))
            for p in points[1:]: route.lineTo(QPointF(*p))
            item.setPath(route)
        elif not raw: item.hide()
    hide_contents(window)

def update(window,result):
    for shell in getattr(window,'asset_cases',{}).values(): shell.result=result; shell.update()
    hide_contents(window)

def hide_contents(window):
    for cid in getattr(window,'hidden_asset_contents',()):
        visible_controls={cid for shell in getattr(window,'asset_cases',{}).values() for cid,_,_ in shell.interaction_controls}
        for collection in (window.symbols,window.glows,getattr(window,'fault_marks',{})):
            item=collection.get(cid)
            if item is not None: item.hide()
        if cid not in visible_controls:
            control=window.controls.get(cid)
            if control is not None: control.hide()
    for cable in getattr(window,'usb_cables',()):
        if cable.component.id in getattr(window,'hidden_asset_contents',()):
            for item in (cable.path,*cable.plugs): item.hide()
