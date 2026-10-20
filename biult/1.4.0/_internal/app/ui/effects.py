"""Bounded visual effects; overlays never intercept input or enable actions."""
from PySide6.QtCore import Qt,QObject,QEvent,QTimer,QRectF,QPointF
from PySide6.QtGui import QColor,QPainter,QPen,QRadialGradient,QBrush
from PySide6.QtWidgets import QWidget,QApplication,QAbstractButton,QGraphicsItem
from math import sin,cos,pi

FLASH_SECONDS=2.2
RING_TAIL_SECONDS=3.0


def fault_effect(settings):
    chosen=getattr(settings,"fault_effect","legacy")
    return chosen if chosen in {"mini","medium","mega"} else "mega" if getattr(settings,"dramatic_faults",False) else "mini"


def effect_seconds(level):
    return {"mini":.65,"medium":1.,"mega":FLASH_SECONDS}[level]


class ExplosionVisual(QGraphicsItem):
    """A single expanding wave, sparks and smoke, deterministic per fault."""
    def __init__(self,level):
        super().__init__(); self.level=level; self.progress=0.; self.radius=220 if level=="mega" else 110
        self.setZValue(4); self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
    def boundingRect(self):
        r=self.radius+12; return QRectF(-r,-r,2*r,2*r)
    def set_progress(self,value):
        self.progress=float(value); self.setVisible(value<1); self.update()
    def paint(self,painter,option,widget=None):
        u=self.progress; r=self.radius
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Residual smoke drifts upward as the bright core dissipates.
        for i in range(4):
            center=QPointF((i-1.5)*r*.14*u,-r*.32*u)
            gradient=QRadialGradient(center,12+r*.28*u)
            gradient.setColorAt(0,QColor(115,123,132,round(95*sin(pi*u))))
            gradient.setColorAt(1,QColor(85,95,105,0))
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(gradient))
            painter.drawEllipse(center,12+r*.28*u,12+r*.28*u)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255,204,118,round(210*(1-u)**2)),max(1,5*(1-u))))
        wave=10+r*.8*u**.55; painter.drawEllipse(QPointF(),wave,wave)
        for i in range(18 if self.level=="mega" else 10):
            angle=2*pi*i/18+.31*i
            distance=(16+r*(.35+.6*(i%5)/4))*u**.6
            pos=QPointF(cos(angle)*distance,sin(angle)*distance+r*.12*u*u)
            tail=QPointF(cos(angle)*10*(1-u),sin(angle)*10*(1-u))
            painter.setPen(QPen(QColor(255,190+(i%3)*20,80,round(255*(1-u)**1.7)),2))
            painter.drawLine(pos-tail,pos)
        painter.setPen(Qt.PenStyle.NoPen)
        gradient=QRadialGradient(QPointF(),10+r*.22*u)
        gradient.setColorAt(0,QColor(255,249,227,round(255*(1-u)**2)))
        gradient.setColorAt(.4,QColor(255,125,35,round(200*(1-u)**2)))
        gradient.setColorAt(1,QColor(255,90,20,0))
        painter.setBrush(QBrush(gradient)); painter.drawEllipse(QPointF(),10+r*.22*u,10+r*.22*u)

class FlashOverlay(QWidget):
    def __init__(self,parent):
        super().__init__(parent); self.opacity=0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground); self.hide()
    def set_opacity(self,value):
        self.opacity=max(0.,min(1.,value)); self.setGeometry(self.parentWidget().rect())
        self.setVisible(self.opacity>0)
        if self.opacity: self.raise_()
        self.update()
    def paintEvent(self,event):
        painter=QPainter(self); painter.fillRect(self.rect(),QColor(255,255,255,round(255*self.opacity)))

class ClickFeedback(QWidget):
    def __init__(self,button):
        super().__init__(button); self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(button.rect()); self.show(); self.raise_(); QTimer.singleShot(150,self.deleteLater)
    def paintEvent(self,event):
        p=QPainter(self); p.setPen(QPen(QColor("#359ac0"),2)); p.setBrush(QColor(65,170,210,65))
        p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),4,4)

class DisabledClickFilter(QObject):
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:
            button=obj if isinstance(obj,QAbstractButton) else QApplication.widgetAt(event.globalPosition().toPoint())
            if isinstance(button,QAbstractButton) and not button.isEnabled(): ClickFeedback(button)
        return False

def install_click_feedback():
    app=QApplication.instance()
    if not hasattr(app,"_disabled_click_feedback"):
        app._disabled_click_feedback=DisabledClickFilter(app); app.installEventFilter(app._disabled_click_feedback)
