"""Rysowanie pojedynczego symbolu bez logiki narzędzi i zapisu projektu.

Współrzędne symbolu są współrzędnymi sceny: 20 jednostek = jedna kratka 5 mm.
Znikanie i smugi najłatwiej wywołać malowaniem poza boundingRect; dlatego
osobno przechowujemy dokładne pole wyboru i obrys z marginesem pióra.
"""
from __future__ import annotations

import math
from html import escape
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject
from app.libraries.built_in import get_definition, item_name, LibraryItem, PinSpec
from app.core.led_colors import color_label

GRID_STEP = 20


class ComponentItem(QGraphicsObject):
    """Klikalny, obracany symbol z rzeczywistą listą elektrycznych pinów."""

    def __init__(self, component, on_position_changed=None, language="en", standard="EN", custom_components=None):
        super().__init__()
        self.component = component
        self.on_position_changed = None
        self.language, self.standard = language, standard
        self.definition = get_definition(component.library_id, custom_components)
        if self.definition is None:
            # Brak definicji nie kasuje elementu starego projektu. Pozostaje
            # czytelny blok oznaczony ?, zamiast niewidocznej instancji.
            self.definition = LibraryItem(component.library_id, "Nieznany element", "", "Unknown element", "Cmp", "module", (), 120, 80)
        self.name = item_name(self.definition, language)
        self.category = self.definition.category
        # Dla prostych symboli pole wyboru opisuje sam symbol, a nie długi
        # tekst wariantu katalogowego. Wszystkie wymiary są wielokrotnością
        # kratki 20 jednostek (z zapasem jednej kratki dla wyprowadzeń).
        self._symbol_rect = self.symbol_rect(self.definition)
        self._hit_rect = self.selection_rect(self.definition, show_name=component.show_name)
        self.setData(0, "component")
        self.setData(1, component.id)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        # Inicjalizacja nie zgłasza zmiany modelu zanim widok zdąży wpisać
        # obiekt do swojego słownika silnych referencji.
        self.setPos(component.x, component.y)
        self.setRotation(component.rotation)
        # Mikrokontrolery wracają do pełnego rozmiaru katalogowego. Ich piny
        # pozostają na rzeczywistych krawędziach dużego symbolu.
        self.on_position_changed = on_position_changed
        self.update_labels()

    def boundingRect(self):
        # Okrąg pinu ma promień 1.6, połowa pióra kolejne 0.675.
        # Zapas obejmuje również podpis obrócony wokół narożnika. Nie wpływa
        # to na pole zaznaczenia (shape() używa dokładnego _hit_rect), ale
        # chroni QGraphicsView przed obcięciem/artefaktami po odświeżeniu.
        return self._hit_rect.adjusted(-10, -10, 10, 10)

    @staticmethod
    def symbol_rect(definition):
        """Obwiednia symbolu na siatce, niezależna od długości jego nazwy.

        Niesymetryczny symbol nie potrzebuje lustrzanego pustego zapasu.
        Końcówki pinów pozostają objęte polem; kreski mogą wystawać o kilka
        jednostek, co uwzględnia osobno boundingRect (obszar odmalowania).
        """
        rectangles = {
            **{key: (-40, -20, 80, 40) for key in (
                "resistor", "capacitor", "polar_capacitor", "inductor",
                "crystal", "diode", "zener", "schottky", "led", "thermistor",
                "buzzer", "npn", "pnp", "nmos", "pmos", "switch", "spdt")},
            "potentiometer": (-40, -40, 80, 60),
            "ldr": (-40, -40, 80, 60),
            "battery": (-40, -20, 80, 40),
            "thyristor": (-40, -20, 80, 60),
            "triac": (-40, -20, 80, 60),
            "ground": (-20, -20, 40, 40), "power": (-20, -20, 40, 40),
            "relay": (-100, -40, 200, 80), "opto": (-80, -40, 160, 80),
            "rgb": (-80, -60, 160, 120), "motor": (-80, -40, 160, 80),
        }
        if definition.symbol.startswith("gate_"):
            return QRectF(-20, -20, 40, 40)
        if definition.symbol in {"led", "battery"}:
            return QRectF(-40, -40, 80, 60)
        if definition.symbol in rectangles:
            return QRectF(*rectangles[definition.symbol])
        return QRectF(-definition.width/2, -definition.height/2,
                      definition.width, definition.height)

    @classmethod
    def selection_rect(cls, definition, show_name=True, show_values=True):
        rect = cls.symbol_rect(definition)
        if definition.symbol in {"module", "ic", "connector"}:
            return rect
        # Oddzielne rzędy siatki na tekst, poza przewodami i obrysem symbolu.
        # Bramka ma symbol 2×2 i tylko dolny rząd nazwy (razem 2×3).
        return rect.adjusted(0, -GRID_STEP if show_values and not definition.symbol.startswith("gate_") else 0,
                             0, GRID_STEP if show_name else 0)

    def shape(self):
        path = QPainterPath()
        path.addRect(self._hit_rect)
        return path

    def pin_positions(self):
        # Rotacja rodzica jest uwzględniona także dla końców przewodów.
        return [self.mapToScene(QPointF(pin.x, pin.y)) for pin in self.definition.pins]

    def update_labels(self):
        self.name = item_name(self.definition, self.language)
        self.display_name = getattr(self.component, "display_name", "") or self.name
        self.show_name = getattr(self.component, "show_name", True)
        self.show_value = getattr(self.component, "show_value", True)
        self.value_text = " ".join(str(s) for s in (getattr(self.component, "value", ""), getattr(self.component, "unit", "")) if s)
        # Dodatkowe pola nie są uniwersalną wartością każdego elementu.
        # Katalog/properties_dialog pokazują je tylko dla typów, które mają
        # drugi znormalizowany parametr (np. napięcie kondensatora lub kolor LED).
        props = getattr(self.component, "properties", {}) or {}
        self.extra_text = ""
        if props.get("show_voltage") and str(props.get("voltage", "")).strip():
            self.extra_text = str(props["voltage"]).strip()
        elif self.definition.symbol == "led" and props.get("show_color") and str(props.get("color", "")).strip():
            self.extra_text = color_label(props["color"], self.language)
        # Pas jest wspólny dla wartości głównej z jednostką i dodatkowego
        # parametru (np. napięcia). Usuwamy go dopiero, gdy żaden z tych
        # napisów nie jest widoczny, również gdy jego treść jest pusta.
        new_rect, self._name_rect, self._value_rect = self._layout_labels()
        if new_rect != self._hit_rect:
            # Qt musi poznać zmianę obwiedni PRZED przypisaniem nowej wartości.
            # Stary pas zostaje odmalowany i znika z hit-testów; symbol,
            # pozycje pinów i podpięte przewody nie są skalowane/przesuwane.
            self.prepareGeometryChange()
            self._hit_rect = new_rect
        reference = getattr(self.component, "reference", "")
        d = self.definition
        warning = "" if d.verified else ("Wariant ogólny / sprawdź dokumentację swojego elementu." if self.language == "pl" else "Check the pinout of your exact device or board revision.")
        self.setToolTip("<b>" + escape(self.display_name) + "</b><br>" + escape(reference) + "<br>" +
                        escape(d.variant) + "<br>" + escape(d.pin_scope) + "<br>" + escape(warning) +
                        "<br>" + " · ".join(escape(f"{pin.number}: {pin.name}") for pin in d.pins))
        self.update()

    def _visible_values(self):
        values = [self.value_text.strip()] if self.show_value and self.value_text.strip() else []
        if self.extra_text.strip():
            values.append(self.extra_text.strip())
        return " / ".join(values)

    def _layout_labels(self):
        """Najpierw sprawdzamy realnie wolne pasy, dopiero potem dodajemy kratkę.

        Pasy odnoszą się do geometrii konkretnego symbolu, a nie prostokąta
        wszystkich pinów. Nie wciskamy podpisu między kreski mikroskopijnym
        fontem: wewnętrzny pas musi zmieścić cały tekst przy co najmniej 8 px.
        """
        core = QRectF(self._symbol_rect)
        symbol = self.definition.symbol
        if symbol in {"module", "ic", "connector"}:
            return core, QRectF(), QRectF()  # Tytuł jest częścią korpusu modułu.
        # Bezpieczne zakresy Y po uwzględnieniu grubości pióra symbolu.
        free = {
            "resistor": ((-20, -9), (9, 20)),
            "inductor": ((-20, -11), (3, 20)),
            "capacitor": ((-20, -13), (13, 20)),
            "polar_capacitor": ((-20, -15), (13, 20)),
            "crystal": ((-20, -14), (14, 20)),
            "diode": ((-20, -13), (13, 20)),
            "zener": ((-20, -17), (17, 20)),
            "schottky": ((-20, -13), (13, 20)),
            "led": ((-40, -29), (13, 20)),
            "potentiometer": (None, (9, 20)),
            "ldr": ((-40, -32), (9, 20)),
            "buzzer": ((-20, -14), (14, 20)),
            "thermistor": ((-20, -14), (14, 20)),
            "ground": (None, (12, 20)),
            "battery": ((-40, -28), None),
            "rgb": (None, (43, 60)),
        }.get(symbol, (None, None))
        result = QRectF(core)
        rects = []
        texts = (self.display_name if self.show_name else "", self._visible_values())
        for index, text in enumerate(texts):
            if not text or (index == 1 and symbol.startswith("gate_")):
                rects.append(QRectF())
                continue
            span = free[1 if index == 0 else 0]
            candidate = QRectF(core.left(), span[0], core.width(), span[1]-span[0]) if span else QRectF()
            if not candidate.isEmpty():
                font, lines = self._fit_wrapped_text(text, candidate.width(), candidate.height(), max_lines=3)
                if font.pixelSize() >= 8 and lines:
                    rects.append(candidate)
                    continue
            if index == 0:
                result.setBottom(core.bottom()+GRID_STEP)
                rects.append(QRectF(core.left(), core.bottom()+2, core.width(), GRID_STEP-2))
            else:
                result.setTop(core.top()-GRID_STEP)
                rects.append(QRectF(core.left(), core.top()-GRID_STEP, core.width(), GRID_STEP-2))
        return result, rects[0], rects[1]

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(value, QPointF):
            return QPointF(round(value.x()/GRID_STEP)*GRID_STEP, round(value.y()/GRID_STEP)*GRID_STEP)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Model synchronizuje widok dopiero przy puszczeniu myszy. Gdyby
            # aktualizować go tutaj, mouseRelease nie wykryłby przesunięcia:
            # zabrakłoby wpisu undo i podpięcia wcześniej położonego kabla.
            if self.on_position_changed:
                self.on_position_changed()
        return super().itemChange(change, value)

    @staticmethod
    def _line(p, x1, y1, x2, y2):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    @staticmethod
    def _arrow(p, start, end, size=5):
        p.drawLine(start, end)
        angle = math.atan2(end.y()-start.y(), end.x()-start.x())
        points = [end, end-QPointF(size*math.cos(angle-.45),size*math.sin(angle-.45)),
                  end-QPointF(size*math.cos(angle+.45),size*math.sin(angle+.45))]
        p.save()
        p.setBrush(p.pen().color())
        p.drawPolygon(QPolygonF(points))
        p.restore()

    def _module(self, p):
        d, r = self.definition, self._hit_rect
        top_pins = any(abs(pin.y-r.top()) < .1 for pin in d.pins)
        body = r.adjusted(20, 20 if top_pins or len(d.pins)>8 else 0, -20, -20)
        p.setBrush(QColor("#ffffff"))
        p.drawRect(body)
        p.setBrush(Qt.BrushStyle.NoBrush)
        font = QFont("Arial")
        font.setPixelSize(10)
        p.setFont(font)
        metrics = QFontMetricsF(font)
        # Dla zdefiniowanych przez użytkownika symboli strona wynika z punktu
        # końca pinu. Nie zakładamy zawsze dwóch albo tylko dolnych pinów.
        for pin in d.pins:
            x,y = pin.x,pin.y
            if abs(x-r.left()) < .1:
                self._line(p,x,y,body.left(),y)
                text = metrics.elidedText(pin.name,Qt.TextElideMode.ElideRight,body.width()/2-12)
                self._pin_label(p, QPointF(body.left()+4,y+3), text)
            elif abs(x-r.right()) < .1:
                self._line(p,body.right(),y,x,y)
                text = metrics.elidedText(pin.name,Qt.TextElideMode.ElideRight,body.width()/2-12)
                self._pin_label(p, QPointF(body.right()-4-metrics.horizontalAdvance(text),y+3), text)
            elif y <= r.top()+.1:
                self._line(p,x,y,x,body.top())
                if len(d.pins)>64:
                    p.save()
                    p.translate(x+3,body.top()+5)
                    p.rotate(90)
                    self._pin_label(p, QPointF(0,0), metrics.elidedText(pin.name,Qt.TextElideMode.ElideRight,body.height()/2-38), base_angle=90)
                    p.restore()
                else:
                    self._pin_label(p, QRectF(x-19,body.top()+3,38,13), metrics.elidedText(pin.name,Qt.TextElideMode.ElideRight,38))
            else:
                self._line(p,x,body.bottom(),x,y)
                if len(d.pins)>64:
                    p.save()
                    p.translate(x-3,body.bottom()-5)
                    p.rotate(-90)
                    self._pin_label(p, QPointF(0,0), metrics.elidedText(pin.name,Qt.TextElideMode.ElideRight,body.height()/2-38), base_angle=-90)
                    p.restore()
                else:
                    text = metrics.elidedText(pin.name,Qt.TextElideMode.ElideRight,38)
                    self._pin_label(p, QRectF(x-19,body.bottom()-16,38,13), text)
            # Numer pinu jest przy kresce, nazwa sygnału wewnątrz korpusu.
            # ST1167 nie ma numeracji fizycznej w definicji: identyfikatory
            # CH1.RXO itp. wiążą przewody, ale na symbolu wystarcza RXO1.
            # Powtarzanie obu opisów zasłaniałoby nazwę sygnału.
            if not d.show_pin_numbers:
                continue
            p.save()
            font.setPixelSize(7)
            p.setFont(font)
            if abs(x-r.left())<.1:
                self._pin_label(p, QPointF(x+2,y-3), pin.number)
            elif abs(x-r.right())<.1:
                fm=QFontMetricsF(font)
                self._pin_label(p, QPointF(x-2-fm.horizontalAdvance(pin.number),y-3), pin.number)
            else:
                self._pin_label(p, QPointF(x+3,y-4), pin.number)
            p.restore()
            font.setPixelSize(10)
        # Tytuł nie ściera pinów: w dużym module ma osobny górny pas.
        title = self.display_name if self.show_name else ""
        if self.show_value and self.value_text:
            title += ("\n" if title else "") + self.value_text
        if self.extra_text:
            title += ("\n" if title else "") + self.extra_text
        p.save()
        title_font=QFont("Arial")
        title_font.setPixelSize(11)
        p.setFont(title_font)
        if top_pins:
            # Czterostronne złącza dużych płytek pozostawiają wolny środek.
            # Górny tytuł nachodziłby tu na opisy górnego rzędu pinów.
            text_rect=QRectF(body.left()+20,body.center().y()-22,body.width()-40,44)
        elif len(d.pins)<=8:
            text_rect=QRectF(body.left()+5,body.top()+4,body.width()-10,max(15,body.height()-23))
        else:
            text_rect=QRectF(body.left()+5,body.top()+1,body.width()-10,30 if "\n" in title else 18)
        # Nazwa nie może zniknąć po cichym elipsowaniu. Dobieramy mniejszą
        # czcionkę i ręcznie zawijamy tekst w obrębie korpusu modułu.
        # Tytuły modułów zachowują czytelność przy tych samych zasadach co
        # podpisy prostych symboli: 180° nie odwraca liter, a bokiem czytamy
        # od dołu do góry. Rysujemy wokół środka, więc napis nie wypływa z
        # korpusu przy zmianie orientacji.
        rotation = int(round(self.rotation())) % 360
        local_angle = 180 if rotation in (90, 180) else 0
        p.save()
        p.translate(text_rect.center())
        p.rotate(local_angle)
        self._draw_fitted_label(p, title, QRectF(-text_rect.width()/2, -text_rect.height()/2,
                                               text_rect.width(), text_rect.height()), centered=True)
        p.restore()
        p.restore()

    def _device_symbol(self, p):
        """Symbole urządzeń z wewnętrznym połączeniem, nie puste pudełka.

        Geometria katalogu daje numery fizycznych pinów; tutaj rysujemy
        obwód wewnętrzny. Nie oznacza to modelu wykonywanej symulacji.
        """
        s = self.definition.symbol
        line = lambda a,b,c,d: self._line(p,a,b,c,d)
        if s == "opto":
            # PC817: LED oraz fototranzystor NPN; brak połączenia galwanicznego.
            p.drawRect(QRectF(-65,-42,130,84))
            line(-80,-20,-35,-20); line(-35,-20,-35,-10)
            line(-80,20,-35,20); line(-35,20,-35,10)
            p.drawPolygon(QPolygonF([QPointF(-44,-10),QPointF(-26,-10),QPointF(-35,9)]))
            line(-45,10,-25,10)
            line(23,-13,23,13)
            line(23,-7,42,-20); line(42,-20,80,-20)
            line(23,7,42,20); line(42,20,80,20)
            self._arrow(p,QPointF(29,11),QPointF(40,19),4)
            self._arrow(p,QPointF(-16,-10),QPointF(10,-3),4)
            self._arrow(p,QPointF(-16,1),QPointF(10,8),4)
        elif s == "relay":
            # Cewka prostokątna i styk przełączny w stanie spoczynku.
            line(-100,-20,-50,-20); line(-50,-20,-50,-10)
            line(-100,20,-50,20); line(-50,20,-50,10)
            p.drawRect(QRectF(-70,-10,40,20))
            line(100,40,30,40); line(30,40,30,20)
            line(100,-40,60,-40); line(100,0,70,0)
            line(30,20,60,-40)
            for x,y in ((30,20),(60,-40),(70,0)):
                p.drawEllipse(QPointF(x,y),2,2)
            p.save()
            pen=QPen(p.pen()); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
            line(-30,0,38,0)
            p.restore()
        elif s == "rgb":
            # Trzy diody we wspólnej obudowie, wspólna katoda zgodnie z wariantem.
            for y in (-40,0,40):
                line(-80,y,-20,y)
                p.drawPolygon(QPolygonF([QPointF(-20,y-8),QPointF(-20,y+8),QPointF(-4,y)]))
                line(-4,y-9,-4,y+9); line(-4,y,40,y)
                self._arrow(p,QPointF(-8,y-11),QPointF(3,y-22),3.5)
                self._arrow(p,QPointF(0,y-8),QPointF(11,y-19),3.5)
            line(40,-40,40,40); line(40,0,80,0)
        elif s == "motor":
            p.drawEllipse(QRectF(-24,-24,48,48))
            font=QFont("Arial"); font.setPixelSize(20); p.setFont(font)
            p.drawText(QRectF(-20,-19,40,38),Qt.AlignmentFlag.AlignCenter,"M")
            if len(self.definition.pins)==4:
                # Uzwojenia bipolarnego silnika krokowego są odseparowane.
                for sign in (-1,1):
                    x=sign*45
                    line(sign*80,-20,x,-20); line(sign*80,20,x,20)
                    path=QPainterPath(QPointF(x,-20))
                    for y in (-20,-10,0,10):
                        path.cubicTo(x+sign*12,y,x+sign*12,y+10,x,y+10)
                    p.drawPath(path)
            else:
                # Serwo zawiera elektronikę sterującą, ma zasilanie i PWM,
                # nie należy rysować zwarcia między trzema wyprowadzeniami.
                p.drawRect(QRectF(-65,-32,30,64))
                for y in (-20,0,20):line(-80,y,-65,y)
                line(-35,0,-24,0)
                font.setPixelSize(8); p.setFont(font)
                p.drawText(QRectF(-63,-8,26,16),Qt.AlignmentFlag.AlignCenter,"CTRL")
        # Numery i nazwy przy wyprowadzeniach są krótkie; pełna lista znajduje
        # się też w podpowiedzi, niezależnie od widoczności nazwy elementu.
        font=QFont("Arial"); font.setPixelSize(8); p.setFont(font)
        fm=QFontMetricsF(font)
        for pin in self.definition.pins:
            text=f"{pin.number} {pin.name}"
            left=pin.x+3 if pin.x<0 else pin.x-3-fm.horizontalAdvance(text)
            self._pin_label(p, QPointF(left,pin.y-4), text)
        self._bottom_labels(p)

    def _pin_label(self, painter, position, text, base_angle=0):
        """Obrót napisu wokół jego środka, bez przesunięcia przypisanego pinu.

        base_angle uwzględnia pionowe podpisy górnych/dolnych rzędów dużych
        płytek. Wypadkowy tekst ma zawsze 0° albo 270° (od dołu do góry).
        """
        rect = position if isinstance(position, QRectF) else QFontMetricsF(painter.font()).boundingRect(text).translated(position)
        painter.save()
        if (int(round(self.rotation())) + base_angle) % 360 in (90, 180):
            painter.translate(rect.center())
            painter.rotate(180)
            painter.translate(-rect.center())
        if isinstance(position, QRectF):
            painter.drawText(position, Qt.AlignmentFlag.AlignCenter, text)
        else:
            painter.drawText(position, text)
        painter.restore()

    def _simple_symbol(self,p):
        s=self.definition.symbol
        line=lambda a,b,c,d:self._line(p,a,b,c,d)
        two_terminal=s in {"resistor","capacitor","polar_capacitor","inductor","crystal","ldr","thermistor","diode","zener","schottky","led","battery","buzzer","thyristor","triac"}
        if two_terminal:
            line(-40,0,-20,0);line(20,0,40,0)
        if s in {"resistor","ldr","thermistor","potentiometer"}:
            if s=="potentiometer":line(-40,0,-20,0);line(20,0,40,0)
            # Prostokąt jest wariantem europejskim; PN wdrażająca EN używa
            # tego samego rysunku, nie amerykańskiego zygzaka.
            p.drawRect(QRectF(-20,-7,40,14))
            if s=="potentiometer":self._arrow(p,QPointF(0,-40),QPointF(0,-8))
            if s=="thermistor":line(-15,12,15,-12);line(-15,12,-21,12)
            if s=="ldr":
                self._arrow(p,QPointF(-20,-27),QPointF(-9,-13))
                self._arrow(p,QPointF(-6,-30),QPointF(5,-16))
        elif s in {"capacitor","polar_capacitor"}:
            line(-20,0,-5,0);line(5,0,20,0)
            line(-5,-11,-5,11);line(5,-11,5,11)
            if s=="polar_capacitor":line(-16,-10,-10,-10);line(-13,-13,-13,-7)
        elif s=="inductor":
            path=QPainterPath(QPointF(-20,0))
            for i in range(4):
                x=-20+i*10
                path.cubicTo(x,-12,x+10,-12,x+10,0)
            p.drawPath(path)
        elif s=="crystal":
            line(-20,0,-12,0);line(12,0,20,0)
            line(-12,-12,-12,12);line(12,-12,12,12)
            p.drawRect(QRectF(-7,-11,14,22))
        elif s in {"diode","zener","schottky","led","thyristor"}:
            line(-20,0,-10,0);line(10,0,20,0)
            p.drawPolygon(QPolygonF([QPointF(-10,-10),QPointF(-10,10),QPointF(10,0)]))
            line(10,-11,10,11)
            if s=="zener":line(10,-11,15,-15);line(10,11,5,15)
            if s=="schottky":line(10,-11,15,-11);line(15,-11,15,-6);line(10,11,5,11);line(5,11,5,6)
            if s=="led":
                self._arrow(p,QPointF(0,-13),QPointF(12,-27))
                self._arrow(p,QPointF(10,-8),QPointF(23,-23))
            if s=="thyristor":line(10,7,0,20);line(0,20,0,40)
        elif s=="triac":
            p.drawPolygon(QPolygonF([QPointF(-13,-13),QPointF(-13,0),QPointF(11,-7)]))
            p.drawPolygon(QPolygonF([QPointF(13,0),QPointF(13,13),QPointF(-11,7)]))
            line(-13,-13,-13,13);line(13,-13,13,13)
            line(-20,0,-13,0);line(13,0,20,0);line(0,40,0,20);line(0,20,-13,10)
        elif s in {"npn","pnp"}:
            line(-40,0,-10,0);line(-10,-13,-10,13)
            line(-10,-7,15,-20);line(15,-20,40,-20)
            line(-10,7,15,20);line(15,20,40,20)
            a,b=QPointF(0,12),QPointF(14,19)
            self._arrow(p,a,b) if s=="npn" else self._arrow(p,b,a)
        elif s in {"nmos","pmos"}:
            line(-40,0,-14,0);line(-14,-14,-14,14)
            for y in (-12,-2,8):line(-8,y,-8,y+5)
            line(-8,-10,12,-10);line(12,-10,12,-20);line(12,-20,40,-20)
            line(-8,10,12,10);line(12,10,12,20);line(12,20,40,20)
            line(-8,0,12,0);line(12,0,12,20)
            a,b=QPointF(4,0),QPointF(-7,0)
            self._arrow(p,a,b) if s=="nmos" else self._arrow(p,b,a)
        elif s=="battery":
            line(-20,0,-7,0);line(7,0,20,0)
            line(-7,-16,-7,16);line(7,-8,7,8)
            line(-18,-22,-10,-22);line(-14,-26,-14,-18)
        elif s=="ground":
            line(0,-20,0,0);line(-13,0,13,0);line(-8,5,8,5);line(-3,10,3,10)
        elif s=="power":
            line(0,20,0,-7);line(-10,-7,10,-7)
        elif s=="switch":
            line(-40,0,-20,0);line(20,0,40,0)
            line(-40,20,-30,20);line(-30,20,-30,0)
            line(40,20,30,20);line(30,20,30,0)
            line(-20,-10,20,-10);line(0,-10,0,-20)
            p.drawEllipse(QPointF(-20,0),2,2);p.drawEllipse(QPointF(20,0),2,2)
        elif s=="spdt":
            line(-40,0,-20,0);line(-20,0,15,-16)
            line(20,-20,40,-20);line(20,20,40,20)
            p.drawEllipse(QPointF(20,-20),2,2);p.drawEllipse(QPointF(20,20),2,2)
        elif s=="buzzer":
            line(-20,0,-12,0);line(12,0,20,0)
            p.drawEllipse(QRectF(-12,-12,24,24));line(-5,-6,-5,6);line(-5,-6,5,-10);line(-5,6,5,10);line(5,-10,5,10)
        else:
            self._module(p)

    def _logic_gate(self, p):
        """Normowany symbol pojedynczej bramki (ANSI/IEC uproszczony).

        Bramka jest elementem schematowym, a nie prostokątnym modułem.
        Katalog podaje rzeczywiste punkty A/B/Y, a poniższy obrys opisuje
        funkcję logiczną bez wykonywania jakiejkolwiek symulacji.
        """
        kind = self.definition.symbol.removeprefix("gate_")
        p.save()
        p.scale(.5, .5)
        pen = QPen(p.pen())
        pen.setWidthF(2.7)
        p.setPen(pen)
        line = lambda a,b,c,d: self._line(p,a,b,c,d)
        if kind == "not":
            p.drawPolygon(QPolygonF([QPointF(-24,-24), QPointF(-24,24), QPointF(24,0)]))
            p.drawEllipse(QPointF(29,0), 5, 5)
            line(-40,0,-24,0); line(34,0,40,0)
        elif kind in {"and", "nand"}:
            path = QPainterPath(QPointF(-28,-25))
            path.lineTo(0,-25)
            path.cubicTo(34,-25,34,25,0,25)
            path.lineTo(-28,25); path.closeSubpath(); p.drawPath(path)
            line(-40,-20,-28,-20); line(-40,20,-28,20)
            if kind == "nand":
                p.drawEllipse(QPointF(30.5,0),5,5)
                line(35.5,0,40,0)
            else:
                line(25.5,0,40,0)
        elif kind in {"or", "nor", "xor", "xnor"}:
            if kind in {"xor", "xnor"}:
                extra = QPainterPath(QPointF(-34,-25))
                extra.cubicTo(-18,-7,-18,7,-34,25)
                p.drawPath(extra)
            path = QPainterPath(QPointF(-28,-25))
            path.cubicTo(-8,-20,4,-15,30,0)
            path.cubicTo(4,15,-8,20,-28,25)
            path.cubicTo(-12,7,-12,-7,-28,-25)
            p.drawPath(path)
            line(-40,-20,-25,-20); line(-40,20,-25,20)
            if kind in {"nor", "xnor"}:
                p.drawEllipse(QPointF(35,0),5,5)
            else:
                line(30,0,40,0)
        else:
            self._module(p)
        p.restore()
        if kind != "not":
            # Końce wejść zostają na pełnej kratce, nie na półkratkach
            # powstałych przy skalowaniu samego rysunku bramki.
            self._line(p, -20, -20, -20, -10)
            self._line(p, -20, 20, -20, 10)
        self._bottom_labels(p)

    @staticmethod
    def _wrap_line(text, metrics, max_width):
        """Zawija także pojedyncze, długie słowa bez obcinania tekstu."""
        text = str(text)
        if not text:
            return [""]
        words = text.split()
        if not words:
            return [""]
        lines, current = [], ""
        for word in words:
            candidate = word if not current else current + " " + word
            if current and metrics.horizontalAdvance(candidate) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            # Nazwy katalogowe typu ``SeeedStudio...`` nie mają spacji.
            # Dzielimy je znak po znaku, aż każda część zmieści się w polu.
            part = ""
            for char in word:
                if part and metrics.horizontalAdvance(part + char) > max_width:
                    lines.append(part)
                    part = char
                else:
                    part += char
            current = part
        if current:
            lines.append(current)
        return lines or [""]

    @classmethod
    def _fit_wrapped_text(cls, text, max_width, max_height, max_lines=4, start_size=11):
        """Zwraca czcionkę i pełne linie, nigdy nie używa ``...``."""
        text = str(text or "").strip()
        if not text:
            return QFont("Arial"), []
        # Jeżeli nazwa nie mieści się przy normalnym rozmiarze, od razu
        # planujemy 2–3 linie. Samo zmniejszanie fontu mogłoby ponownie
        # zmieścić ją w jednej, bardzo drobnej linii (wbrew ustawieniu).
        initial_font = QFont("Arial")
        initial_font.setPixelSize(start_size)
        initial_width = QFontMetricsF(initial_font).horizontalAdvance(text)
        if "\n" not in text and initial_width > max_width:
            count = min(max_lines, 2 if initial_width <= max_width*2 else 3)
            words = text.split()
            if len(words) >= count:
                sections = []
                for remaining in range(count, 1, -1):
                    target = len(" ".join(words)) / remaining
                    split = min(range(1, len(words)-remaining+2),
                                key=lambda index: abs(len(" ".join(words[:index]))-target))
                    sections.append(" ".join(words[:split]))
                    words = words[split:]
                text = "\n".join(sections + [" ".join(words)])
        for size in range(start_size, 3, -1):
            font = QFont("Arial")
            font.setPixelSize(size)
            metrics = QFontMetricsF(font)
            lines = []
            for raw in text.splitlines() or [""]:
                lines.extend(cls._wrap_line(raw, metrics, max(8, max_width)))
            line_height = max(1.0, metrics.height())
            if len(lines) <= max_lines and len(lines) * line_height <= max_height + 1:
                return font, lines
        # Bardzo długi wpis też zachowujemy w całości w maksymalnie trzech
        # liniach. Poszerzamy wirtualny wiersz, po czym renderer skaluje
        # komplet glifów do docelowego pola. Nigdy nie malujemy poza obrysem.
        font = QFont("Arial")
        font.setPixelSize(3)
        metrics = QFontMetricsF(font)
        width = max(8, max_width)
        flat = " ".join(text.split())
        lines = cls._wrap_line(flat, metrics, width)
        while len(lines) > max_lines:
            width *= 1.25
            lines = cls._wrap_line(flat, metrics, width)
        return font, lines

    @classmethod
    def _label_path(cls, text, rect, centered=False):
        """Zamknięty w polu tekst wektorowy, identyczny dla ekranu i PDF."""
        font, lines = cls._fit_wrapped_text(text, rect.width(), rect.height(), max_lines=3)
        metrics = QFontMetricsF(font)
        path = QPainterPath()
        for index, line in enumerate(lines):
            glyphs = QPainterPath()
            glyphs.addText(0, 0, font, line)
            glyphs.translate(-glyphs.boundingRect().left(), index * metrics.height())
            path.addPath(glyphs)
        bounds = path.boundingRect()
        if bounds.isEmpty():
            return path
        from PySide6.QtGui import QTransform
        scale = min(1.0, rect.width()/bounds.width(), rect.height()/bounds.height())
        path = QTransform.fromScale(scale, scale).map(path)
        bounds = path.boundingRect()
        if centered:
            path.translate(rect.center() - bounds.center())
        else:
            path.translate(rect.left()-bounds.left(), rect.bottom()-bounds.bottom())
        return path

    @classmethod
    def _draw_fitted_label(cls, painter, text, rect, centered=False):
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#163247"))
        painter.drawPath(cls._label_path(text, rect, centered))
        painter.restore()

    def label_rects(self):
        """Pasy tekstu nie przecinają symbolu, także po jego obrocie."""
        return self._name_rect, self._value_rect

    def _bottom_labels(self, p):
        name_rect, value_rect = self.label_rects()
        for text, rect in ((self.display_name if self.show_name else "", name_rect),
                           (self._visible_values(), value_rect)):
            if not text or rect.isEmpty():
                continue
            p.save()
            # Obracamy w obrębie własnego pasa, nigdy przez środek symbolu.
            # Zapobiega to kolizjom tekstu z niesymetrycznym np. przyciskiem.
            p.translate(rect.center())
            if int(round(self.rotation())) % 360 in (90, 180):
                p.rotate(180)
            local = QRectF(-rect.width()/2, -rect.height()/2, rect.width(), rect.height())
            self._draw_fitted_label(p, text, local)
            p.restore()

    def paint(self,painter,option,widget=None):
        painter.save()
        color=QColor("#163247")
        painter.setPen(QPen(color,1.35,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.definition.symbol.startswith("gate_"):
            self._logic_gate(painter)
        elif self.definition.symbol in {"relay","rgb","motor","opto"}:
            self._device_symbol(painter)
        elif self.definition.symbol in {"module","ic","connector"}:
            self._module(painter)
        else:
            self._simple_symbol(painter)
            self._bottom_labels(painter)
        # Niezajęty pin to drobny pusty okrąg. Duże zielone węzły należą do
        # przewodów i nie mogą mylić się z samym elektrycznym wyprowadzeniem.
        painter.setBrush(QColor("white"))
        for pin in self.definition.pins:
            painter.drawEllipse(QPointF(pin.x,pin.y),1.6,1.6)
        if self.isSelected():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#168bd2"),1,Qt.PenStyle.DashLine))
            painter.drawRect(self._hit_rect)
        painter.restore()
