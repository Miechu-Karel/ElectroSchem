"""Data-only case drawing around a read-only preview of the original circuit."""
from copy import deepcopy
from math import ceil
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPen,QColor,QPainter
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QSpinBox,
    QGraphicsView,QGraphicsScene,QDialogButtonBox,QMessageBox,QLineEdit)
from app.core.models import Project
from app.canvas.component_item import ComponentItem


class CaseView(QGraphicsView):
    def __init__(self,editor):
        super().__init__(editor); self.editor=editor; self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing); self.origin=None; self.draft=None
    def wheelEvent(self,event): self.scale(1.2 if event.angleDelta().y()>0 else 1/1.2,1.2 if event.angleDelta().y()>0 else 1/1.2)
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton: return super().mousePressEvent(event)
        point=self.mapToScene(event.position().toPoint()); tool=self.editor.tool.currentData()
        if tool=='selection': point=QPointF(round(point.x()/20)*20,round(point.y()/20)*20)
        if tool=='erase':
            for index in range(len(self.editor.shapes)-1,-1,-1):
                shape=self.editor.shapes[index]
                if QRectF(*shape['rect']).contains(point): self.editor.shapes.pop(index); self.editor.render(); break
        elif tool=='pin': self.editor.move_pin(point)
        else: self.origin=point
        event.accept()
    def mouseMoveEvent(self,event):
        if self.origin is not None:
            point=self.mapToScene(event.position().toPoint())
            if self.editor.tool.currentData()=='selection': point=QPointF(round(point.x()/20)*20,round(point.y()/20)*20)
            rect=QRectF(self.origin,point).normalized()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                side=min(rect.width(),rect.height()); rect.setWidth(side); rect.setHeight(side)
            rect=rect.intersected(self.editor.bounds())
            if self.draft: self.scene().removeItem(self.draft)
            self.draft=self.scene().addEllipse(rect,QPen(QColor('#3888ad'),2)) if self.editor.tool.currentData()=='circle' else self.scene().addRect(rect,QPen(QColor('#3888ad'),2))
            event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.origin is not None:
            # Recompute on release as modifiers may change after the last move.
            self.mouseMoveEvent(event)
            if self.draft:
                rect=self.draft.rect()
                if rect.width()>4 and rect.height()>4:
                    self.editor.shapes.append(dict(kind=self.editor.tool.currentData(),rect=[rect.x(),rect.y(),rect.width(),rect.height()]))
            self.origin=self.draft=None; self.editor.render(); event.accept(); return
        super().mouseReleaseEvent(event)


class AssetCaseEditor(QDialog):
    def __init__(self,definition,settings,parent=None):
        super().__init__(parent); self.definition=deepcopy(definition); self.settings=settings
        self.t=lambda en,pl:pl if settings.language=='pl' else en
        self.setWindowTitle(self.t('Asset case editor','Edytor obudowy assetu')); self.resize(1150,800)
        self.source=Project.from_dict({'sheets':[definition['asset']['sheet']],'custom_components':definition['asset']['custom']})
        case=definition['asset'].get('case',{})
        self.shapes=deepcopy(case.get('shapes',[])); self.pins=deepcopy(definition['pins'])
        layout=QVBoxLayout(self); self.name=QLineEdit(definition['name']); layout.addWidget(self.name)
        layout.addWidget(QLabel(self.t('Draw a rectangle/circle, erase a shape, or choose a port and click an edge.',
            'Rysuj prostokąt/koło, usuń kształt gumką lub wybierz pin i kliknij miejsce wyprowadzenia.')))
        bar=QHBoxLayout(); layout.addLayout(bar); self.tool=QComboBox()
        for key,en,pl in (('rect','Rectangle','Prostokąt'),('circle','Circle','Koło'),('erase','Eraser','Gumka'),('pin','Expose pin','Wyprowadź PIN')): self.tool.addItem(self.t(en,pl),key)
        bar.addWidget(self.tool); self.port=QComboBox()
        for i,pin in enumerate(self.pins): self.port.addItem(pin['number']+' '+pin['name'],i)
        bar.addWidget(self.port)
        self.width=QSpinBox(); self.height=QSpinBox()
        dimension_help=self.t('Dimension in drawing units; 20 units equal one grid square.','Wymiar w jednostkach rysunku; 20 jednostek to jedna kratka.')
        for field,label,key in ((self.width,self.t('Width','Szerokość'),'width'),(self.height,self.t('Height','Wysokość'),'height')):
            field.setRange(80,2000); field.setSingleStep(40); field.setValue(definition[key]); field.setToolTip(dimension_help)
            caption=QLabel(label); caption.setToolTip(dimension_help); bar.addWidget(caption); bar.addWidget(field)
        self.view=CaseView(self); layout.addWidget(self.view,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        for field in (self.width,self.height): field.valueChanged.connect(self.render)
        self.render()

    def showEvent(self,event):
        super().showEvent(event)
        # Fit only once the layout has given the viewport its real dimensions.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0,self.fit_circuit)

    def fit_circuit(self):
        from shiboken6 import isValid
        if isValid(self.view):
            self.view.fitInView(self.view.scene().itemsBoundingRect().adjusted(-40,-40,40,40),Qt.AspectRatioMode.KeepAspectRatio)

    def bounds(self): return QRectF(-self.width.value()/2,-self.height.value()/2,self.width.value(),self.height.value())
    def move_pin(self,point):
        if not 0<=self.port.currentIndex()<len(self.pins): return
        rect=self.bounds(); x=round(point.x()/20)*20; y=round(point.y()/20)*20
        edge=min(('left','right','top','bottom'),key=lambda e:abs((point.x() if e in ('left','right') else point.y())-getattr(rect,e)()))
        if edge in ('left','right'): x=getattr(rect,edge)(); y=max(rect.top()+20,min(rect.bottom()-20,y))
        else: y=getattr(rect,edge)(); x=max(rect.left()+20,min(rect.right()-20,x))
        pin=self.pins[self.port.currentIndex()]; pin['x'],pin['y']=x,y; self.render()

    def render(self,*_):
        self.view.draft=None; self.view.origin=None
        scene=self.view.scene(); scene.clear(); bounds=self.bounds(); scale=1.0; self.component_bounds=[]
        scene.addRect(bounds,QPen(QColor('#888888'),1,Qt.PenStyle.DashLine))
        for wire in self.source.sheets[0].wires:
            points=wire.points or [[wire.start_x,wire.start_y],[wire.end_x,wire.end_y]]
            for a,b in zip(points,points[1:]): scene.addLine(a[0]*scale,a[1]*scale,b[0]*scale,b[1]*scale,QPen(QColor('#21854f'),1.5))
        for component in self.source.sheets[0].components:
            item=ComponentItem(deepcopy(component),language=self.settings.language,custom_components=self.source.custom_components)
            item.setScale(scale); item.setPos(component.x*scale,component.y*scale); item.setFlags(item.flags() & ~item.GraphicsItemFlag.ItemIsMovable & ~item.GraphicsItemFlag.ItemIsSelectable); scene.addItem(item)
            self.component_bounds.append((component.id,item.mapRectToScene(item._hit_rect)))
        for shape in self.shapes:
            from app.canvas.case_shapes import path
            brush=QColor(70,100,130,40) if shape['kind']!='path' or shape.get('closed') else Qt.BrushStyle.NoBrush
            scene.addPath(path(shape),QPen(QColor('#345d80'),2),brush)
        for i,pin in enumerate(self.pins):
            point=QPointF(pin['x'],pin['y']); scene.addEllipse(point.x()-4,point.y()-4,8,8,QPen(QColor('#b85e20'),2))
            from app.canvas.case_shapes import pin_root
            scene.addLine(point.x(),point.y(),pin_root(self.shapes,point).x(),pin_root(self.shapes,point).y(),QPen(QColor('#b85e20'),2))
            show_names=getattr(self,'show_pin_names',None)
            show_names=show_names.isChecked() if show_names is not None else self.definition.get('asset',{}).get('case',{}).get('show_pin_names',False)
            text=scene.addText(pin['number']+(' '+pin['name'] if show_names else '')); text.setDefaultTextColor(QColor('#af5920')); text.setPos(point)
            port=getattr(self,'exports',self.definition['asset']['exports'])[i]
            component=next((c for c in self.source.sheets[0].components if c.id==port['component']),None)
            if component:
                from app.libraries.built_in import get_instance_definition
                from PySide6.QtGui import QTransform
                spec=get_instance_definition(component,self.source.custom_components).pins[port['pin']]
                p=QTransform().rotate(component.rotation).map(QPointF(spec.x,spec.y))+QPointF(component.x,component.y)
                scene.addLine(p.x()*scale,p.y()*scale,point.x(),point.y(),QPen(QColor('#c68d58'),1,Qt.PenStyle.DashLine))

    def save(self):
        try:
            definition=deepcopy(self.definition); definition['name']=self.name.text().strip(); definition['name_en']=definition['name']
            if self.width.value()%40 or self.height.value()%40: raise ValueError(self.t('Dimensions must be multiples of 40.','Wymiary muszą być wielokrotnością 40.'))
            definition['width']=self.width.value(); definition['height']=self.height.value(); definition['pins']=deepcopy(self.pins)
            definition['asset']['boxed']=True
            shapes=deepcopy(self.shapes) or [dict(kind='rect',rect=[-definition['width']/2,-definition['height']/2,definition['width'],definition['height']])]
            definition['asset']['case']={'shapes':shapes,**({'free_pins':True} if definition['asset'].get('case',{}).get('free_pins') else {})}
            if 'show_pin_names' in self.definition['asset'].get('case',{}):
                definition['asset']['case']['show_pin_names']=self.definition['asset']['case']['show_pin_names']
            if 'regions' in self.definition['asset'].get('case',{}): definition['asset']['case']['regions']=deepcopy(self.definition['asset']['case']['regions'])
            if 'selection_rect' in self.definition['asset'].get('case',{}): definition['asset']['case']['selection_rect']=deepcopy(self.definition['asset']['case']['selection_rect'])
            from app.libraries.built_in import validate_custom_definition
            self.definition=validate_custom_definition(definition); self.accept()
        except (ValueError,TypeError,KeyError) as error: QMessageBox.warning(self,'ElectroSchem',str(error))
