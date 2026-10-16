"""On-screen keyboard and host-key feedback for simulated Python stdin only."""
from PySide6.QtCore import QEvent,Qt,QPointF
from PySide6.QtGui import QIcon,QPixmap,QPainter,QColor,QPen,QPolygonF
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,QPushButton

ROWS=(('Esc',)+tuple(f'F{i}' for i in range(1,13)), tuple('`1234567890-=')+('Backspace',), ('Tab',)+tuple('qwertyuiop[]\\'), ('Caps',)+tuple("asdfghjkl;'")+('Enter',), ('Shift',)+tuple('zxcvbnm')+(',', '.', '/','RShift'), ('Ctrl','Win','Alt','Space','AltGr','RWin','Menu','RCtrl'))
NAV=(('Print','Scroll','Pause'),('Insert','Home','PgUp'),('Delete','End','PgDn'),('','Up',''),('Left','Down','Right'))
NUM=(('Num','Num/','Num*','Num-'),('Num7','Num8','Num9','Num+'),('Num4','Num5','Num6',''),('Num1','Num2','Num3','NumEnter'),('Num0','','Num.',''))
SHIFT=dict(zip("1234567890-=,./[]\\;'","!@#$%^&*()_+<>?{}|:\""))
POLISH=dict(zip('acelnosxz','ąćęłńóśźż'))

def special_icon(key):
    """Draw symbols natively, including on hosts without Unicode glyph fonts."""
    key={'RWin':'Win','RShift':'Shift','NumEnter':'Enter'}.get(key,key)
    if key not in {'Win','Shift','Caps','Enter','Backspace','Tab','Menu','Left','Right','Up','Down'}: return None
    image=QPixmap(24,24); image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#7c91a8'),1.8)); p.setBrush(Qt.BrushStyle.NoBrush)
    def line(x,y,xx,yy): p.drawLine(QPointF(x,y),QPointF(xx,yy))
    if key=='Win':
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#8096ae'))
        for x in (2,13):
            for y in (2,13): p.drawRect(x,y,8,8)
    elif key in {'Shift','Caps'}:
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in ((12,3),(21,12),(16,12),(16,19),(8,19),(8,12),(3,12))]))
        if key=='Caps': line(8,22,16,22)
    elif key=='Backspace':
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in ((3,12),(9,5),(22,5),(22,19),(9,19))]))
        line(12,9,18,15); line(18,9,12,15)
    elif key=='Enter':
        line(20,4,20,14); line(20,14,4,14); line(4,14,10,8); line(4,14,10,20)
    elif key=='Menu':
        for y in (6,12,18): line(4,y,20,y)
    elif key=='Tab':
        line(3,12,20,12); line(20,12,14,6); line(20,12,14,18); line(22,4,22,20)
    else:
        angle={'Right':0,'Down':90,'Left':180,'Up':270}[key]
        p.translate(12,12); p.rotate(angle); p.translate(-12,-12)
        line(4,12,20,12); line(20,12,14,6); line(20,12,14,18)
    p.end(); return QIcon(image)

class UsbKeyboard(QWidget):
    def __init__(self,window,device):
        super().__init__(); self.window=window; self.device=device
        self.shift=False; self.caps=False; self.altgr=False; self.alt=False; self.buttons={}
        self.setMinimumWidth(1240); layout=QVBoxLayout(self); layout.setContentsMargins(8,8,8,8)
        self.note=QLabel(window.t("USB keyboard: click keys or type on your keyboard. Enter sends the line to the connected Python program.","Klawiatura USB: klikaj klawisze lub pisz na swojej klawiaturze. Enter wysyła linię do podłączonego programu Python."))
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.entry=QLineEdit(); self.entry.setMaxLength(4096); self.entry.installEventFilter(self); layout.addWidget(self.entry)
        self.status=QLabel(); layout.addWidget(self.status)
        blocks=QHBoxLayout(); layout.addLayout(blocks)
        main=QVBoxLayout(); blocks.addLayout(main,7)
        def make_button(label, square=False):
            symbols={'Left':'←','Right':'→','Up':'↑','Down':'↓','Shift':'⇧','RShift':'⇧','Caps':'⇪','Enter':'↵','NumEnter':'↵','Backspace':'⌫','Tab':'⇥','Menu':'☰','RCtrl':'Ctrl'}
            button=QPushButton(symbols.get(label,label.removeprefix('Num') if label.startswith('Num') and label!='Num' else label))
            button.setToolTip(label)
            icon=special_icon(label)
            if icon: button.setIcon(icon); button.setText('')
            if square:
                button.setFixedSize(56,56)
            else:
                button.setFixedHeight(36); button.setMinimumWidth(34)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            if label in {'Shift','RShift','Caps','Alt','AltGr','Num'}: button.setCheckable(True)
            button.clicked.connect(lambda checked=False,key=label:self.activate(key))
            self.buttons[label]=button
            return button
        for labels in ROWS:
            row=QHBoxLayout(); row.setSpacing(3); main.addLayout(row)
            for label in labels:
                row.addWidget(make_button(label),5 if label=='Space' else 2 if label in {'Backspace','Shift','RShift','Enter'} else 1)
        for rows,stretch in ((NAV,3),(NUM,4)):
            grid=QGridLayout(); grid.setSpacing(3); blocks.addLayout(grid,stretch)
            for r,labels in enumerate(rows):
                for c,label in enumerate(labels):
                    if label: grid.addWidget(make_button(label,square=True),r,c)
        self.buttons['Num'].setChecked(True)
        self.entry.returnPressed.connect(self.send)
        self.status.setText(window.t("Connect a powered USB cable to a Python board.","Podłącz zasilany kabel USB do płytki z programem Python."))
    def refresh_power(self):
        powered=self.device.state.get('powered',False)
        self.status.setText(self.window.t("Powered; input goes only to the simulator.","Zasilana; tekst trafia tylko do symulatora.") if powered else self.window.t("No USB power.","Brak zasilania USB."))
    def activate(self,key):
        if key.startswith('Num') and key not in {'Num','NumEnter'} and not self.buttons['Num'].isChecked():
            key={'Num7':'Home','Num8':'Up','Num9':'PgUp','Num4':'Left','Num5':'Pause','Num6':'Right','Num1':'End','Num2':'Down','Num3':'PgDn','Num0':'Insert','Num.':'Delete'}.get(key,key)
        modifier=key in {'Shift','RShift','Alt','AltGr','Caps','Num','Ctrl','RCtrl','Win','RWin'}
        if key in {'Shift','RShift'}: self.shift=self.buttons[key].isChecked()
        elif key=='Caps': self.caps=self.buttons[key].isChecked()
        elif key=='AltGr': self.altgr=self.buttons[key].isChecked()
        elif key=='Alt': self.alt=self.buttons[key].isChecked()
        elif key in {'Enter','NumEnter'}: self.send()
        elif key=='Backspace': self.entry.backspace()
        elif key=='Delete': self.entry.del_()
        elif key in {'Left','Right'}: self.entry.setCursorPosition(self.entry.cursorPosition()+(-1 if key=='Left' else 1))
        elif key=='Home': self.entry.setCursorPosition(0)
        elif key=='End': self.entry.setCursorPosition(len(self.entry.text()))
        elif key in {'Ctrl','RCtrl','Win','RWin','Num','Menu','Insert','Up','Down','PgUp','PgDn','Esc','Print','Scroll','Pause'} or (key.startswith('F') and key[1:].isdigit()): pass
        else:
            text=' ' if key=='Space' else '\t' if key=='Tab' else key.removeprefix('Num')
            if self.altgr and text in POLISH: text=POLISH[text]
            if text.isalpha() and self.shift!=self.caps: text=text.upper()
            elif self.shift: text=SHIFT.get(text,text)
            self.entry.insert(text)
        if not modifier: self.consume_modifiers()
        self.entry.setFocus()

    def consume_modifiers(self):
        self.shift=self.alt=self.altgr=False
        for key in ('Shift','RShift','Alt','AltGr'): self.buttons[key].setChecked(False)
    def eventFilter(self,obj,event):
        if obj is self.entry and event.type() in {QEvent.Type.KeyPress,QEvent.Type.KeyRelease}:
            key={Qt.Key.Key_Return:'Enter',Qt.Key.Key_Enter:'Enter',Qt.Key.Key_Backspace:'Backspace',Qt.Key.Key_Space:'Space',Qt.Key.Key_Left:'Left',Qt.Key.Key_Right:'Right',Qt.Key.Key_Delete:'Delete',Qt.Key.Key_Shift:'Shift',Qt.Key.Key_AltGr:'AltGr',Qt.Key.Key_CapsLock:'Caps',Qt.Key.Key_Tab:'Tab'}.get(event.key(),event.text().lower())
            button=self.buttons.get(key)
            if button: button.setDown(event.type()==QEvent.Type.KeyPress)
            if event.type()==QEvent.Type.KeyPress:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier and not event.modifiers() & (Qt.KeyboardModifier.AltModifier|Qt.KeyboardModifier.GroupSwitchModifier) and not self.altgr:
                    self.consume_modifiers()
                    return super().eventFilter(obj,event)
                special={Qt.Key.Key_Home:'Home',Qt.Key.Key_End:'End',Qt.Key.Key_Up:'Up',Qt.Key.Key_Down:'Down',Qt.Key.Key_PageUp:'PgUp',Qt.Key.Key_PageDown:'PgDn',Qt.Key.Key_Insert:'Insert',Qt.Key.Key_Escape:'Esc',Qt.Key.Key_Print:'Print',Qt.Key.Key_ScrollLock:'Scroll',Qt.Key.Key_Pause:'Pause'}
                key=special.get(event.key(),key)
                if Qt.Key.Key_F1<=event.key()<=Qt.Key.Key_F12: key=f'F{event.key()-Qt.Key.Key_F1+1}'
                if event.modifiers() & Qt.KeyboardModifier.KeypadModifier:
                    key='NumEnter' if key=='Enter' else 'Num'+key if key in '0123456789/*-+.' and key else key
                if event.key()==Qt.Key.Key_NumLock:
                    if not event.isAutoRepeat(): self.buttons['Num'].toggle()
                    return True
                if event.key()==Qt.Key.Key_CapsLock:
                    if not event.isAutoRepeat():
                        self.buttons['Caps'].toggle(); self.activate('Caps')
                    return True
                modifier={Qt.Key.Key_Shift:'Shift',Qt.Key.Key_Alt:'Alt',Qt.Key.Key_AltGr:'AltGr'}.get(event.key())
                if modifier:
                    if not event.isAutoRepeat():
                        self.buttons[modifier].setChecked(True)
                        setattr(self,{'Shift':'shift','Alt':'alt','AltGr':'altgr'}[modifier],True)
                    return True
                if event.key() not in {Qt.Key.Key_Control,Qt.Key.Key_Meta,Qt.Key.Key_CapsLock}:
                    if key in self.buttons or event.text():
                        self.activate(key); return True
            if event.key()==Qt.Key.Key_Tab and event.type()==QEvent.Type.KeyPress:
                self.entry.insert('\t'); return True
        return super().eventFilter(obj,event)
    def send(self):
        circuit=self.window.circuit
        if circuit is None: return
        if not self.device.state.get('powered'):
            if not self.window.timer.isActive(): self.window.single_step()
            if not self.device.state.get('powered'):
                self.refresh_power(); return
        part=next((p for p in circuit.parts if self.device in p.devices),None)
        if part is None or len(part.scripts)!=1:
            self.status.setText(self.window.t("Connect to exactly one board running Python.","Podłącz do dokładnie jednej płytki uruchamiającej Python.")); return
        script=next(iter(part.scripts.values()))
        try: script.submit_input(self.entry.text())
        except ValueError as error: self.status.setText(str(error)); return
        self.entry.clear()
        if not self.window.timer.isActive(): self.window.single_step()
        self.window.refresh_consoles(); self.refresh_power()
