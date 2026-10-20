"""Paint tools layered on the existing asset preview; no source circuit edits."""
from copy import deepcopy
from uuid import uuid4
from pathlib import Path
from PySide6.QtCore import Qt,QEvent,QPointF,QRectF,QSize
from PySide6.QtGui import QPainterPathStroker,QColor,QIcon,QPen,QTransform
from PySide6.QtWidgets import QApplication,QHBoxLayout,QVBoxLayout,QGridLayout,QToolButton,QPushButton,QLineEdit,QLabel,QMessageBox,QComboBox,QListWidget,QListWidgetItem,QCheckBox,QWidget
from app.ui.asset_case_editor import AssetCaseEditor,CaseView
from app.canvas.case_shapes import path
from app.libraries.built_in import get_instance_definition


class PaintView(CaseView):
    def __init__(self,editor):
        super().__init__(editor); self.points=[]; self.edit=None; self.stroke_tool=None
        self.setMouseTracking(True); self.viewport().setMouseTracking(True)
    def cancel_stroke(self):
        if self.draft is not None:
            try:
                if self.draft.scene(): self.scene().removeItem(self.draft)
            except RuntimeError: pass
        self.origin=None; self.draft=None; self.points=[]; self.edit=None; self.stroke_tool=None
    def location(self,event):
        p=self.mapToScene(event.position().toPoint()); b=self.editor.bounds()
        return QPointF(max(b.left(),min(b.right(),p.x())),max(b.top(),min(b.bottom(),p.y())))
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton: return super().mousePressEvent(event)
        self.cancel_stroke()
        p=self.location(event); tool=self.editor.tool.currentData()
        if tool in ('pencil','pin','rect','circle','light','interaction','selection'):
            self.stroke_tool=tool
        if tool=='pencil': self.origin=p; self.points=[p]
        elif tool=='terminal': self.editor.add_pin(p,'PIN')
        elif tool=='connect': self.editor.connect_at(p)
        elif tool=='erase': self.editor.erase(p)
        elif tool=='pin':
            self.edit=self.editor.begin_edit(p)
            self.origin=p if self.edit else None
        else: return super().mousePressEvent(event)
        event.accept()
    def mouseMoveEvent(self,event):
        tool=self.stroke_tool or self.editor.tool.currentData()
        if tool=='connect' and isinstance(self.editor.pending,dict) and 'region' in self.editor.pending:
            self.editor.update_connect_preview(self.location(event)); event.accept(); return
        if tool=='pin' and self.origin is not None:
            p=self.location(event); shape=self.editor.preview_edit(self.edit,self.origin,p)
            if self.draft: self.scene().removeItem(self.draft); self.draft=None
            if shape:
                if shape.get('kind')=='pin':
                    point=QPointF(*shape['point']); self.draft=self.scene().addEllipse(point.x()-5,point.y()-5,10,10,QPen(QColor('#21854f'),2))
                else:
                    self.draft=self.scene().addPath(path(shape),QPen(QColor('#3888ad'),2,Qt.PenStyle.DashLine))
            event.accept(); return
        if tool!='pencil' or self.origin is None: return super().mouseMoveEvent(event)
        p=self.location(event)
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier: self.points=[self.origin,p]
        elif (p-self.points[-1]).manhattanLength()>2 and len(self.points)<2000: self.points.append(p)
        if self.draft: self.scene().removeItem(self.draft); self.draft=None
        if len(self.points)>1: self.draft=self.scene().addPath(path(dict(kind='path',points=[[p.x(),p.y()] for p in self.points])),QPen(QColor('#3888ad'),2))
        event.accept()
    def mouseReleaseEvent(self,event):
        if self.origin is None: return super().mouseReleaseEvent(event)
        tool=self.stroke_tool or self.editor.tool.currentData()
        if tool=='pin':
            p=self.location(event); result=self.editor.preview_edit(self.edit,self.origin,p)
            if result: self.editor.commit_edit(self.edit,result)
            self.cancel_stroke(); self.editor.render(); event.accept(); return
        if tool in ('light','interaction','selection'):
            super().mouseMoveEvent(event)
            if self.draft and self.draft.rect().width()>4 and self.draft.rect().height()>4:
                r=self.draft.rect(); self.editor.checkpoint()
                if tool=='selection': self.editor.selection=[r.x(),r.y(),r.width(),r.height()]
                else:
                    kind=tool
                    component=None if kind=='light' else self.editor.region_target.currentData()
                    self.editor.regions.append(dict(kind=kind,component=component,rect=[r.x(),r.y(),r.width(),r.height()]))
            self.cancel_stroke(); self.editor.render(); event.accept(); return
        if tool=='pencil':
            self.mouseMoveEvent(event)
            if len(self.points)>1:
                self.editor.checkpoint(); self.editor.shapes.append(dict(kind='path',points=[[p.x(),p.y()] for p in self.points],closed=len(self.points)>3 and (self.points[-1]-self.points[0]).manhattanLength()<15))
            self.cancel_stroke(); self.editor.render(); event.accept()
        else:
            if self.draft: self.editor.checkpoint()
            super().mouseReleaseEvent(event)
            self.points=[]; self.edit=None; self.stroke_tool=None


class PaintAssetCaseEditor(AssetCaseEditor):
    def __init__(self,definition,settings,parent=None):
        self.exports=deepcopy(definition['asset']['exports']); self.regions=deepcopy(definition['asset'].get('case',{}).get('regions',[])); self.selection=deepcopy(definition['asset'].get('case',{}).get('selection_rect')); self.history=[]; self.pending=None; self.connect_preview=None; self.ready=False; self.restoring=False
        super().__init__(definition,settings,parent)
        for label in self.findChildren(QLabel):
            if label.text().startswith(('Rysuj prostokąt/koło','Draw a rectangle/circle')): label.hide()
        layout=self.layout(); old=self.view; self.view=PaintView(self); layout.replaceWidget(old,self.view); old.hide(); old.deleteLater()
        # Keep the whole palette visible: a fixed-height grid is more reliable
        # than a non-resizing scroll area's child, whose initial size can be tiny.
        tools_widget=QWidget(); bar=QGridLayout(tools_widget); bar.setContentsMargins(2,2,2,2); bar.setHorizontalSpacing(6); bar.setVerticalSpacing(2)
        bar.setColumnStretch(0,1); bar.setColumnStretch(1,1); bar.setColumnStretch(2,1); bar.setColumnStretch(3,1); bar.setColumnStretch(4,1)
        layout.insertWidget(1,tools_widget); self.buttons=[]
        icon_root=Path(__file__).resolve().parents[2]/'icons'
        for index,(key,en,pl,filename) in enumerate((('pencil','Pencil','Ołówek','pencil.png'),('rect','Rectangle','Prostokąt','rectangle.png'),('circle','Ellipse','Elipsa','ellipse.png'),('erase','Eraser','Gumka','eraser.png'),('terminal','PIN','PIN','PIN.png'),('connect','Connection','Łączenie','Łączenie.png'),('pin','Edit/move shapes and pins','Edytuj/przesuń kształty i piny','move.png'),('selection','Selection area','Pole zaznaczania','select.png'),('light','Light window','Okno świecenia','light.png'),('interaction','Interaction area','Pole interakcji','interaction.png'))):
            if self.tool.findData(key)<0: self.tool.addItem(self.t(en,pl),key)
            icon_path=icon_root/filename
            if not icon_path.is_file() and key=='connect': icon_path=icon_root/'connect_pins.png'
            cell=QWidget(); cell_layout=QVBoxLayout(cell); cell_layout.setContentsMargins(1,1,1,1); cell_layout.setSpacing(0)
            b=QToolButton(); b.setIcon(QIcon(str(icon_path)) if icon_path.is_file() else QIcon()); b.setIconSize(QSize(30,30)); b.setToolTip(self.t(en,pl)); b.setCheckable(True); b.setMinimumHeight(38); b.setMaximumWidth(56); b.setAccessibleName(self.t(en,pl))
            b.clicked.connect(lambda checked=False,k=key:self.tool.setCurrentIndex(self.tool.findData(k)))
            label=QLabel(self.t(en,pl)); label.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop); label.setWordWrap(True); label.setToolTip(self.t(en,pl))
            cell_layout.addWidget(b,0,Qt.AlignmentFlag.AlignHCenter); cell_layout.addWidget(label,1)
            bar.addWidget(cell,index//5,index%5); self.buttons.append((key,b))
        undo=QPushButton(self.t('Undo','Cofnij')); undo.setIcon(QIcon(str(icon_root/'undo.png'))); undo.clicked.connect(self.undo); undo.setMaximumWidth(100); bar.addWidget(undo,2,3)
        fit=QPushButton(self.t('Fit view','Dopasuj widok')); fit.setIcon(QIcon(str(icon_root/'reset_zoom.png'))); fit.clicked.connect(self.fit_circuit); fit.setMaximumWidth(160); bar.addWidget(fit,2,4)
        # Catch Ctrl+Z before Qt resolves QAction/QShortcut ambiguities. The
        # main window has its own document-level undo, which must never run
        # while this editor is active.
        self._app=QApplication.instance()
        if self._app is not None: self._app.installEventFilter(self)
        self.finished.connect(self._restore_main_history_actions)
        self._main_history_actions=[]
        owner=parent
        while owner is not None and not hasattr(owner,'undo_action'):
            owner=owner.parentWidget() if hasattr(owner,'parentWidget') else None
        if owner is not None:
            for name in ('undo_action','redo_action'):
                action=getattr(owner,name,None)
                if action is not None:
                    self._main_history_actions.append((action,action.isEnabled(),action.shortcuts()))
                    action.setEnabled(False)
                    action.setShortcuts([])
        options=QHBoxLayout(); layout.insertLayout(3,options); options.addWidget(QLabel(self.t('Pin name','Nazwa pinu')))
        self.pin_name=QLineEdit(); self.pin_name.setPlaceholderText(self.t('Terminal name','Nazwa pinu')); self.pin_name.setToolTip(self.t('Rename the currently selected package pin.','Zmień nazwę aktualnie wybranego pinu obudowy.')); options.addWidget(self.pin_name)
        self.pin_name.editingFinished.connect(self.rename_pin); self.port.currentIndexChanged.connect(self.show_pin_name)
        clear=QPushButton(self.t('Clear pins','Wyczyść piny')); clear.setToolTip(self.t('Remove all package pins and their internal pin mappings.','Usuń wszystkie piny obudowy i ich przypisania do pinów wewnętrznych.')); clear.clicked.connect(self.clear_pins); options.addWidget(clear)
        self.status=QLabel(); self.status.setToolTip(self.t('Number of package pins that are not connected to internal pins.','Liczba pinów obudowy bez przypisania do pinów wewnętrznych.')); options.addWidget(self.status)
        targets=QHBoxLayout(); layout.insertLayout(4,targets); self.region_target_label=QLabel(self.t('Component for interaction region','Element dla pola interakcji')); targets.addWidget(self.region_target_label)
        self.region_target=QComboBox(); targets.addWidget(self.region_target)
        self.show_pin_names=QCheckBox(self.t('Show internal pin names','Pokazuj nazwy pinów układu wewnątrz'))
        self.show_pin_names.setChecked(bool(definition['asset'].get('case',{}).get('show_pin_names',False)))
        self.show_pin_names.stateChanged.connect(self.render)
        self.show_pin_names.setToolTip(self.t('Show or hide names of the internal components’ pins in the case preview.','Pokaż lub ukryj nazwy pinów elementów wewnątrz obudowy.')); targets.addWidget(self.show_pin_names)
        for c in self.source.sheets[0].components:
            spec=get_instance_definition(c,self.source.custom_components); self.region_target.addItem(c.reference+' — '+spec.name,c.id)
        editable_label=QLabel(self.t('Members whose properties can be edited after placement:','Elementy, których właściwości można edytować po wstawieniu:'))
        editable_label.setToolTip(self.t('Check a component to expose its properties when the asset is placed in a schematic.','Zaznacz element, aby jego właściwości były dostępne po wstawieniu assetu na schemat.')); targets.addWidget(editable_label)
        self.editable_members=QListWidget(); self.editable_members.setToolTip(editable_label.toolTip()); self.editable_members.setMaximumHeight(86); layout.insertWidget(5,self.editable_members)
        enabled=set(definition['asset'].get('editable_properties',[]))
        for c in self.source.sheets[0].components:
            spec=get_instance_definition(c,self.source.custom_components)
            item=QListWidgetItem(c.reference+' — '+spec.name); item.setData(Qt.ItemDataRole.UserRole,c.id)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked if c.id in enabled else Qt.CheckState.Unchecked); self.editable_members.addItem(item)
        hint=QLabel(self.t('Draw a case, add pins, then Connect: click a case terminal and an internal pin. Select a light/interaction target before drawing its window. Shift: straight line, square or circle. Ctrl+Z: undo.',
            'Narysuj obudowę, dodaj PINy, potem Połącz: kliknij pin obudowy i pin układu. Wybierz element dla okna świecenia / interakcji. Shift: prosta linia, kwadrat lub koło. Ctrl+Z: cofnij.'))
        hint.setWordWrap(True); layout.insertWidget(2,hint)
        self.tool.currentIndexChanged.connect(self.select_tool); self.tool.setCurrentIndex(self.tool.findData('pencil')); self.tool.hide()
        # Dimension changes must be undoable and keep pins legal.
        for field in (self.width,self.height): field.valueChanged.disconnect(); field.valueChanged.connect(self.resize_case)
        if 'case' not in definition['asset']:
            self.pins=[]; self.exports=[]
        self.renumber_pins()
        self.port.setMinimumContentsLength(14)
        self.port.setSizeAdjustPolicy(self.port.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.ready=True; self.render()
    def select_tool(self,*_):
        if hasattr(self,'view') and isinstance(self.view,PaintView): self.view.cancel_stroke()
        self.remove_connect_preview()
        self.pending=None
        for key,b in self.buttons: b.setChecked(key==self.tool.currentData())
        self.region_target_label.setVisible(self.tool.currentData()=='interaction')
        self.region_target.setVisible(self.tool.currentData()=='interaction')
        if self.tool.currentData()=='interaction':
            from app.libraries.simulation_catalog import behavior_for
            current=self.region_target.currentData(); choices=[]
            for c in self.source.sheets[0].components:
                spec=get_instance_definition(c,self.source.custom_components); model=behavior_for(spec)
                allowed=model and model.kind in {'tactile','joystick','switch','spdt','multi_switch','encoder','digital_sensor','logic_input','keypad','ir_receiver','potentiometer','variable_resistor'}
                if allowed: choices.append((c.reference+' — '+spec.name,c.id))
            if choices:
                self.region_target.clear()
                for label,cid in choices: self.region_target.addItem(label,cid)
                self.region_target.setCurrentIndex(max(0,self.region_target.findData(current)))
    def begin_edit(self,point):
        for index,pin in enumerate(self.pins):
            if (QPointF(pin['x'],pin['y'])-point).manhattanLength()<14:
                return {'kind':'pin','index':index,'before':(pin['x'],pin['y'])}
        stroker=QPainterPathStroker(); stroker.setWidth(16)
        for index in range(len(self.shapes)-1,-1,-1):
            shape=self.shapes[index]; drawing=path(shape)
            if not drawing.contains(point) and not stroker.createStroke(drawing).contains(point): continue
            mode='move'
            if shape.get('kind') in ('rect','circle'):
                rect=QRectF(*shape['rect']); tolerance=10
                edges=[]
                if rect.top()-tolerance<=point.y()<=rect.bottom()+tolerance: edges.extend(((abs(point.x()-rect.left()),'left'),(abs(point.x()-rect.right()),'right')))
                if rect.left()-tolerance<=point.x()<=rect.right()+tolerance: edges.extend(((abs(point.y()-rect.top()),'top'),(abs(point.y()-rect.bottom()),'bottom')))
                distance,edge=min(edges,default=(tolerance+1,''))
                if distance<=tolerance: mode=edge
            return {'kind':'shape','index':index,'mode':mode,'origin':QPointF(point),'before':deepcopy(shape)}
        return None
    def preview_edit(self,edit,origin,point):
        if not edit: return None
        bounds=self.bounds()
        if edit['kind']=='pin':
            x,y=self.snap_pin(point); index=edit['index']
            if any(i!=index and pin['x']==x and pin['y']==y for i,pin in enumerate(self.pins)): return None
            return {'kind':'pin','point':(x,y)}
        shape=deepcopy(edit['before']); mode=edit['mode']
        if mode=='move':
            dx,dy=point.x()-origin.x(),point.y()-origin.y()
            rect=path(shape).boundingRect()
            dx=max(bounds.left()-rect.left(),min(bounds.right()-rect.right(),dx)); dy=max(bounds.top()-rect.top(),min(bounds.bottom()-rect.bottom(),dy))
            if shape['kind']=='path': shape['points']=[[x+dx,y+dy] for x,y in shape['points']]
            else:
                x,y,w,h=shape['rect']; shape['rect']=[x+dx,y+dy,w,h]
            return shape
        x,y,w,h=shape['rect']; left,right=x,x+w; top,bottom=y,y+h
        px=max(bounds.left(),min(bounds.right(),point.x())); py=max(bounds.top(),min(bounds.bottom(),point.y()))
        if mode=='left': left=min(px,right-8)
        elif mode=='right': right=max(px,left+8)
        elif mode=='top': top=min(py,bottom-8)
        elif mode=='bottom': bottom=max(py,top+8)
        shape['rect']=[left,top,right-left,bottom-top]
        return shape
    def commit_edit(self,edit,result):
        if edit['kind']=='pin':
            index=edit['index']; x,y=result['point']
            if (self.pins[index]['x'],self.pins[index]['y'])==(x,y): return False
            self.checkpoint(); self.pins[index]['x'],self.pins[index]['y']=x,y; return True
        index=edit['index']
        if result==edit['before']: return False
        self.checkpoint(); self.shapes[index]=result; return True
    def snapshot(self): return deepcopy((self.shapes,self.pins,self.exports,self.width.value(),self.height.value(),self.regions,self.selection))
    def checkpoint(self): self.history.append(self.snapshot()); self.history=self.history[-100:]
    def undo(self):
        if not self.history: return
        self.shapes,self.pins,self.exports,w,h,self.regions,self.selection=self.history.pop(); self.restoring=True
        for field,value in ((self.width,w),(self.height,h)): field.setValue(value)
        self.restoring=False; self.pending=None; self.render()
    def eventFilter(self,watched,event):
        modal=self._app.activeModalWidget() if self._app is not None else None
        target_is_editor=(watched is self or
                          isinstance(watched,QWidget) and self.isAncestorOf(watched))
        editor_owns_key=(modal is self or (modal is None and self.isVisible() and target_is_editor))
        if (event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Z and
                event.modifiers() & Qt.KeyboardModifier.ControlModifier and
                not event.modifiers() & Qt.KeyboardModifier.ShiftModifier and
                editor_owns_key):
            focus=self._app.focusWidget()
            # Keep ordinary text undo in the pin-name field when it has edits
            # of its own; otherwise this shortcut belongs to the case canvas.
            if isinstance(focus,QLineEdit) and focus.isUndoAvailable():
                return False
            self.undo(); event.accept(); return True
        return super().eventFilter(watched,event)
    def _restore_main_history_actions(self,*_):
        if self._app is not None:
            self._app.removeEventFilter(self)
            self._app=None
        for action,was_enabled,shortcuts in self._main_history_actions:
            action.setShortcuts(shortcuts)
            action.setEnabled(was_enabled)
        self._main_history_actions=[]
    def resize_case(self,*_):
        if self.restoring: return
        self.history.append(deepcopy(self.last_state)); oldw,oldh=self.last_state[3:5]; b=self.bounds()
        for pin in self.pins:
            pin['x']*=self.width.value()/oldw; pin['y']*=self.height.value()/oldh
            pin['x'],pin['y']=self.snap_pin(QPointF(pin['x'],pin['y']))
        sx,sy=self.width.value()/oldw,self.height.value()/oldh
        for shape in self.shapes:
            if shape['kind']=='path': shape['points']=[[x*sx,y*sy] for x,y in shape['points']]
            else: x,y,w,h=shape['rect']; shape['rect']=[x*sx,y*sy,w*sx,h*sy]
        for region in self.regions:
            x,y,w,h=region['rect']; region['rect']=[x*sx,y*sy,w*sx,h*sy]
        if self.selection:
            x,y,w,h=self.selection; self.selection=[x*sx,y*sy,w*sx,h*sy]
        self.render()
    def show_pin_name(self,*_):
        i=self.port.currentIndex(); self.pin_name.setText(self.pins[i]['name'] if 0<=i<len(self.pins) else '')
    def rename_pin(self):
        i=self.port.currentIndex(); name=self.pin_name.text().strip()
        if 0<=i<len(self.pins) and name and name!=self.pins[i]['name']:
            self.checkpoint(); self.pins[i]['name']=name; self.exports[i]['name']=name; self.render()
    def clear_pins(self): self.checkpoint(); self.pins=[]; self.exports=[]; self.pending=None; self.render()
    def add_pin(self,p,direction):
        if len(self.pins)>=128: return
        x,y=self.snap_pin(p)
        if any(pin['x']==x and pin['y']==y for pin in self.pins): return
        self.checkpoint(); n=str(len(self.pins)+1); name=direction+n
        self.pins.append(dict(number=n,name=name,x=x,y=y,direction=direction,identity=str(uuid4()))); self.exports.append(dict(component=None,pin=None,name=name)); self.renumber_pins(); self.render(); self.port.setCurrentIndex(len(self.pins)-1)
    def renumber_pins(self):
        for index,pin in enumerate(self.pins,1):
            old_number=pin.get('number',''); old_name=pin.get('name','')
            pin.setdefault('identity',f'legacy:{old_number}' if old_number else str(uuid4()))
            new_number=str(index)
            if old_name==f"PIN{old_number}": pin['name']=f'PIN{new_number}'
            pin['number']=new_number
            if index-1<len(self.exports): self.exports[index-1]['name']=pin['name']
    def move_pin(self,p):
        i=self.port.currentIndex()
        if not 0<=i<len(self.pins): return
        x,y=self.snap_pin(p)
        if any(j!=i and pin['x']==x and pin['y']==y for j,pin in enumerate(self.pins)): return
        self.checkpoint(); self.pins[i]['x'],self.pins[i]['y']=x,y; self.render()
    def snap_pin(self,p):
        from math import ceil,floor
        b=self.bounds()
        return (max(ceil(b.left()/20)*20,min(floor(b.right()/20)*20,round(p.x()/20)*20)),max(ceil(b.top()/20)*20,min(floor(b.bottom()/20)*20,round(p.y()/20)*20)))
    def erase(self,p):
        for i in range(len(self.regions)-1,-1,-1):
            if QRectF(*self.regions[i]['rect']).contains(p): self.checkpoint(); self.regions.pop(i); self.render(); return
        for i,pin in enumerate(self.pins):
            if (QPointF(pin['x'],pin['y'])-p).manhattanLength()<12:
                self.checkpoint(); self.pins.pop(i); self.exports.pop(i); self.renumber_pins(); self.render(); return
        stroker=QPainterPathStroker(); stroker.setWidth(12)
        for i in range(len(self.shapes)-1,-1,-1):
            drawing=path(self.shapes[i])
            if drawing.contains(p) or stroker.createStroke(drawing).contains(p): self.checkpoint(); self.shapes.pop(i); self.render(); return
    def connect_at(self,p):
        if isinstance(self.pending,dict) and 'region' in self.pending:
            region_index=self.pending['region']
            from app.libraries.simulation_catalog import behavior_for
            region_kind=self.regions[region_index]['kind']
            light_kinds={'led','lamp','rgb','logic_output','ir_transmitter'}
            interaction_kinds={'tactile','joystick','switch','spdt','multi_switch','encoder','digital_sensor','logic_input','keypad','ir_receiver','potentiometer','variable_resistor'}
            allowed_kinds=light_kinds if region_kind=='light' else interaction_kinds
            emitters={c.id for c in self.source.sheets[0].components
                      if (model:=behavior_for(get_instance_definition(c,self.source.custom_components))) and model.kind in allowed_kinds}
            # The target is the component's actual selection rectangle, so
            # users can finish the wire by clicking its familiar hit area.
            target=next(((cid,rect) for cid,rect in reversed(self.component_bounds)
                         if cid in emitters and rect.contains(p)),None)
            if target:
                component_id=target[0]; anchor=self.pending['anchor']
                self.remove_connect_preview(); self.checkpoint(); self.regions[region_index]['component']=component_id
                self.regions[region_index]['link_line']=[[anchor.x(),anchor.y()],[p.x(),p.y()]]
                self.pending=None; self.render()
                self.status.setText(self.t('Window connected; its guide line is saved.','Pole połączone, linia prowadząca została zapisana.'))
            else: self.status.setText(self.t('Click the selection area of a compatible element.','Kliknij pole zaznaczania zgodnego elementu.'))
            return
        if self.pending is None:
            region_index=next((i for i in range(len(self.regions)-1,-1,-1) if self.regions[i]['kind'] in ('light','interaction') and QRectF(*self.regions[i]['rect']).contains(p)),None)
            if region_index is not None:
                self.pending={'region':region_index,'anchor':QPointF(p)}; self.update_connect_preview(p)
                self.status.setText(self.t('Now click the selection area of the target element.','Teraz kliknij pole zaznaczania elementu docelowego.')); return
            i=min(range(len(self.pins)),key=lambda i:(QPointF(self.pins[i]['x'],self.pins[i]['y'])-p).manhattanLength(),default=None)
            if i is not None and (QPointF(self.pins[i]['x'],self.pins[i]['y'])-p).manhattanLength()<25:
                self.pending=i; self.port.setCurrentIndex(i); self.status.setText(self.t('Click an internal pin.','Kliknij pin układu wewnątrz.'))
            return
        nearest=min(self.internal_pins,key=lambda entry:(entry[0]-p).manhattanLength(),default=None)
        if nearest and (nearest[0]-p).manhattanLength()<25:
            self.checkpoint(); pin=self.pins[self.pending]; self.exports[self.pending]=dict(component=nearest[1],pin=nearest[2],name=pin['name']); self.pending=None; self.render()
    def remove_connect_preview(self):
        if self.connect_preview is not None:
            try:
                if self.connect_preview.scene(): self.connect_preview.scene().removeItem(self.connect_preview)
            except RuntimeError: pass
            self.connect_preview=None
    def update_connect_preview(self,p):
        if not isinstance(self.pending,dict) or 'region' not in self.pending: return
        self.remove_connect_preview()
        anchor=self.pending.get('anchor',p)
        self.connect_preview=self.view.scene().addLine(anchor.x(),anchor.y(),p.x(),p.y(),QPen(QColor('#20d66b'),2,Qt.PenStyle.DashLine))
        self.connect_preview.setZValue(1000)
    def render(self,*_):
        # The parent clears and rebuilds the scene; discard its temporary line
        # reference before Qt deletes the old graphics item.
        if isinstance(self.view,PaintView): self.view.cancel_stroke()
        self.connect_preview=None
        super().render()
        if not self.ready: return
        i=self.port.currentIndex(); self.port.blockSignals(True); self.port.clear()
        for pin in self.pins: self.port.addItem(pin['number']+' '+pin['name'])
        self.port.setCurrentIndex(min(max(i,0),len(self.pins)-1)); self.port.blockSignals(False); self.show_pin_name()
        scale=1.0; self.internal_pins=[]
        for c in self.source.sheets[0].components:
            for i,pin in enumerate(get_instance_definition(c,self.source.custom_components).pins):
                p=(QTransform().rotate(c.rotation).map(QPointF(pin.x,pin.y))+QPointF(c.x,c.y))*scale
                self.internal_pins.append((p,c.id,i)); self.view.scene().addEllipse(p.x()-4,p.y()-4,8,8,QPen(QColor('#21854f'),1.5))
        self.last_state=self.snapshot(); missing=sum(p['component'] is None for p in self.exports)
        b=self.bounds(); pen=QPen(QColor('#b5bec7'),.5)
        for x in range(int(b.left()),int(b.right())+1,20): self.view.scene().addLine(x,b.top(),x,b.bottom(),pen).setZValue(-10)
        for y in range(int(b.top()),int(b.bottom())+1,20): self.view.scene().addLine(b.left(),y,b.right(),y,pen).setZValue(-10)
        if self.selection: self.view.scene().addRect(QRectF(*self.selection),QPen(QColor('#8873ba'),1,Qt.PenStyle.DashLine))
        for region in self.regions:
            self.view.scene().addRect(QRectF(*region['rect']),QPen(QColor('#b88b20' if region['kind']=='light' else '#8d5bc4'),2,Qt.PenStyle.DashLine))
            route=region.get('link_line')
            if isinstance(route,list) and len(route)==2 and all(isinstance(point,list) and len(point)==2 for point in route):
                self.view.scene().addLine(route[0][0],route[0][1],route[1][0],route[1][1],QPen(QColor('#20d66b'),2,Qt.PenStyle.DashLine)).setZValue(5)
        self.status.setText(self.t(f'Unconnected: {missing}',f'Niepodłączone: {missing}'))
    def save(self):
        if not self.shapes or not self.pins or any(p['component'] is None for p in self.exports):
            QMessageBox.warning(self,'ElectroSchem',self.t('Draw the case and connect all pins.','Narysuj obudowę i podłącz wszystkie piny.')); return
        from app.libraries.simulation_catalog import behavior_for
        light_kinds={'led','lamp','rgb','logic_output','ir_transmitter'}
        interaction_kinds={'tactile','joystick','switch','spdt','multi_switch','encoder','digital_sensor','logic_input','keypad','ir_receiver','potentiometer','variable_resistor'}
        required=[]
        for c in self.source.sheets[0].components:
            spec=get_instance_definition(c,self.source.custom_components); model=behavior_for(spec)
            if model and model.kind in light_kinds|interaction_kinds: required.append((c,model.kind in light_kinds))
        missing=[]
        for c,is_light in required:
            kind='light' if is_light else 'interaction'
            if not any(region['component']==c.id and region['kind']==kind for region in self.regions): missing.append(c.reference)
        if required and not self.selection:
            QMessageBox.warning(self,'ElectroSchem',self.t('Draw and snap a selection area before saving.','Narysuj pole zaznaczania przyciągane do siatki przed zapisaniem.')); return
        if missing:
            QMessageBox.warning(self,'ElectroSchem',self.t('Add a light/interaction region for: ','Dodaj pole świecenia/interakcji dla: ')+', '.join(missing)); return
        previous=deepcopy(self.definition); self.definition['asset']['exports']=deepcopy(self.exports)
        self.definition['asset'].setdefault('case',{})['free_pins']=True
        self.definition['asset']['case']['regions']=deepcopy(self.regions)
        self.definition['asset']['case']['show_pin_names']=self.show_pin_names.isChecked()
        self.definition['asset']['editable_properties']=[self.editable_members.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.editable_members.count()) if self.editable_members.item(i).checkState()==Qt.CheckState.Checked]
        if self.selection: self.definition['asset']['case']['selection_rect']=deepcopy(self.selection)
        super().save()
        if self.result()!=self.DialogCode.Accepted: self.definition=previous
