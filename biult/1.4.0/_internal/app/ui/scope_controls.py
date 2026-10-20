"""Oscilloscope controls embedded in the simulator, not another window."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QComboBox,QDoubleSpinBox,QCheckBox

class ScopeControls(QWidget):
    def __init__(self,window,cid=None):
        super().__init__(); self.window=window; self.cid=cid; layout=QVBoxLayout(self)
        layout.setContentsMargins(4,4,4,4)
        self.target=QComboBox(); layout.addWidget(QLabel(window.t('Scope','Oscyloskop'))); layout.addWidget(self.target)
        def number(en,pl,minimum,maximum,decimals):
            field=QDoubleSpinBox(); field.setRange(minimum,maximum); field.setDecimals(decimals)
            layout.addWidget(QLabel(window.t(en,pl))); layout.addWidget(field); field.valueChanged.connect(self.changed); return field
        self.volts_div=number('V/div','V/dz.',.001,1e6,3)
        self.offset=number('Centre [V]','Środek [V]',-1e6,1e6,3)
        self.time_div=number('s/div','s/dz.',.000001,100,6)
        self.time_div.setSingleStep(.01)
        self.auto_scale=QCheckBox(window.t('Auto axes','Auto osi')); layout.addWidget(self.auto_scale)
        self.target.setMaximumWidth(180)
        for field in (self.volts_div,self.offset,self.time_div): field.setFixedWidth(124)
        for i in range(layout.count()):
            widget=layout.itemAt(i).widget()
            if isinstance(widget,QLabel): widget.setFixedWidth(widget.sizeHint().width())
        self.setFixedWidth(180)
        self.auto_scale.toggled.connect(self.changed); self.target.currentIndexChanged.connect(self.load)
        self.hide()
    def refresh(self):
        self.target.blockSignals(True); self.target.clear()
        for cid,item in self.window.scopes.items():
            if self.cid is None or self.cid==cid: self.target.addItem(item.component.reference,cid)
        self.target.blockSignals(False); self.setVisible(bool(self.window.scopes)); self.load()
    def load(self,*_):
        item=self.window.scopes.get(self.target.currentData())
        if item is None: return
        a,b=item.scope_bounds
        for field,value in ((self.volts_div,(b-a)/4),(self.offset,(a+b)/2),(self.time_div,item.scope_duration/8),(self.auto_scale,item.scope_autoscale)):
            field.blockSignals(True)
            if field is self.auto_scale: field.setChecked(value)
            else: field.setValue(value)
            field.blockSignals(False)
        self.changed()
    def changed(self,*_):
        item=self.window.scopes.get(self.target.currentData())
        if item is None: return
        centre=self.offset.value(); span=2*self.volts_div.value()
        item.scope_bounds=(centre-span,centre+span); item.scope_duration=8*self.time_div.value(); item.scope_autoscale=self.auto_scale.isChecked()
        for field in (self.volts_div,self.offset,self.time_div): field.setEnabled(not item.scope_autoscale)
        item.update()
