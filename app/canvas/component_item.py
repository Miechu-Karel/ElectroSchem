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
CABLE_NAMES={'Kabel USB','Kabel Męsko-Żeński','Kabel Żeńsko-Żeński','Kabel Męsko-Męski'}


def bottom_sockets(definition):
    return "Arduino" in definition.name or "Raspberry Pi" in definition.name or definition.name.startswith("Port USB") or definition.name=="Port Lightning"

def socket_strip(definition,rect):
    top=definition.name.startswith(("Port USB","Port Lightning")) and definition.pins and all(pin.y==definition.height/2 for pin in definition.pins)
    return rect.adjusted(0,-40,0,0) if top else rect.adjusted(0,0,0,40)


class ComponentItem(QGraphicsObject):
    """Klikalny, obracany symbol z rzeczywistą listą elektrycznych pinów."""

    def __init__(self, component, on_position_changed=None, language="en", standard="EN", custom_components=None):
        super().__init__()
        self.component = component
        self.on_position_changed = None
        self.language, self.standard = language, standard
        self.asset_case=next((raw.get('asset',{}).get('case') for raw in (custom_components or []) if raw.get('id')==component.library_id),None)
        self.asset_payload=next((raw.get('asset') for raw in (custom_components or []) if raw.get('id')==component.library_id),None)
        from app.libraries.built_in import get_instance_definition
        try: self.definition = get_instance_definition(component, custom_components)
        except ValueError: self.definition=get_definition(component.library_id,custom_components)
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
        rect=self._hit_rect.adjusted(-10, -10, 10, 10)
        if self.asset_case:
            from app.canvas.case_shapes import outline
            body,strokes=outline(self.asset_case['shapes'])
            rect=rect.united(body.boundingRect().adjusted(-10,-10,10,10)).united(strokes.boundingRect())
            for pin in self.definition.pins: rect=rect.united(QRectF(pin.x-10,pin.y-15,90,30))
        if self.definition.name in CABLE_NAMES:
            a,b=self.cable_points()
            rect=rect.united(QRectF(a,b).normalized().adjusted(-30,-30,30,110))
        return rect

    def cable_points(self):
        prefix='usb_' if self.definition.name=='Kabel USB' else 'jumper_'
        def coordinate(key,default):
            try:
                number=float(self.component.properties.get(key,default))
                return number if math.isfinite(number) and abs(number)<1e6 else default
            except (ValueError,TypeError): return default
        return tuple(QPointF(coordinate(prefix+side+'_x',x),coordinate(prefix+side+'_y',0)) for side,x in (('a',-75),('b',75)))

    @staticmethod
    def symbol_rect(definition):
        """Obwiednia symbolu na siatce, niezależna od długości jego nazwy.

        Niesymetryczny symbol nie potrzebuje lustrzanego pustego zapasu.
        Końcówki pinów pozostają objęte polem; kreski mogą wystawać o kilka
        jednostek, co uwzględnia osobno boundingRect (obszar odmalowania).
        """
        rectangles = {
            **{key: (-40, -20, 80, 40) for key in (
                "resistor", "variable_resistor", "capacitor", "polar_capacitor", "inductor",
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
            "logic_input": (-20, -20, 60, 40),
            "logic_output": (-40, -20, 60, 40),
            "meter": (-40, -20, 80, 40),
            "match": (-60, -40, 120, 80),
            "ultrasonic_target": (-60, -40, 120, 80),
            "motion_target": (-40, -60, 80, 120),
            "ir_remote": (-40, -80, 80, 160),
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
        if bottom_sockets(definition):
            return socket_strip(definition,rect)
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
        if self.definition.name in {"Kabel USB","Kostka zasilająca USB","Klawiatura USB"}: return []
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
        if self.asset_case and self.asset_case.get('selection_rect'): new_rect=QRectF(*self.asset_case['selection_rect'])
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
        if self.show_value and self.component.properties.get('sim_voltage_mode') == 'limits':
            p = self.component.properties
            values = [f"{p.get('sim_voltage_min', '-5 V')} … {p.get('sim_voltage_max', '5 V')}"]
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
            if bottom_sockets(self.definition): core=socket_strip(self.definition,core)
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
        if bottom_sockets(d): r=self._symbol_rect
        top_pins = any(abs(pin.y-r.top()) < .1 for pin in d.pins)
        body = r.adjusted(20, 20 if top_pins or len(d.pins)>8 else 0, -20, -20)
        p.setBrush(QColor(getattr(self, "paper_color", "#ffffff")))
        p.drawRect(body)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if d.name == "Czujnik Płomienia":
            p.save()
            p.setPen(QPen(QColor("#123a28"),1.5)); p.setBrush(QColor("#267247"))
            p.drawRoundedRect(body,5,5)
            p.setBrush(QColor("#111820")); p.setPen(QPen(QColor("#71808a"),1.5))
            lens=QRectF(body.left()+10,body.center().y()-20,40,40); p.drawEllipse(lens)
            p.setBrush(QColor("#392944")); p.setPen(QPen(QColor("#b878d1"),1))
            p.drawEllipse(lens.adjusted(8,8,-8,-8))
            p.setBrush(QColor("#17232c")); p.setPen(QPen(QColor("#0d1720"),1))
            chip=QRectF(body.left()+62,body.top()+14,34,29); p.drawRoundedRect(chip,2,2)
            for offset in (6,13,20,27):
                p.drawLine(QPointF(chip.left()-4,chip.top()+offset),QPointF(chip.left(),chip.top()+offset))
                p.drawLine(QPointF(chip.right(),chip.top()+offset),QPointF(chip.right()+4,chip.top()+offset))
            p.setBrush(QColor("#d3b554")); p.setPen(QPen(QColor("#795e25"),1))
            p.drawEllipse(QPointF(body.right()-23,body.center().y()),10,10)
            p.drawLine(QPointF(body.right()-29,body.center().y()),QPointF(body.right()-17,body.center().y()))
            lit=self.component.properties.get("sim_flame_detected")=="true"
            p.setPen(QPen(QColor("#ff503c" if lit else "#82463f"),1)); p.setBrush(QColor("#ff503c" if lit else "#552d2b"))
            p.drawEllipse(QPointF(body.right()-48,body.top()+15),4,4)
            p.restore()
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
        if d.name.startswith("Port USB") and len(d.pins)<=8:
            text_rect=QRectF(body.left()+5,body.top()+55,body.width()-10,32)
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

        from app.canvas.connector_art import paint_connectors
        paint_connectors(self,p,body)

    def connector_body(self):
        if self.definition.name=="Kostka zasilająca USB": return QRectF(-30,-32,60,64)
        d,r=self.definition,self._hit_rect
        if bottom_sockets(d): r=self._symbol_rect
        top=any(abs(pin.y-r.top())<.1 for pin in d.pins)
        return r.adjusted(20,20 if top or len(d.pins)>8 else 0,-20,-20)

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
            common_anode=any(pin.name=="A" for pin in self.definition.pins)
            for y in (-40,0,40):
                line(-80,y,-20,y)
                base,tip=(-4,-20) if common_anode else (-20,-4)
                p.drawPolygon(QPolygonF([QPointF(base,y-8),QPointF(base,y+8),QPointF(tip,y)]))
                line(tip,y-9,tip,y+9); line(-4,y,40,y)
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
        two_terminal=s in {"resistor","variable_resistor","capacitor","polar_capacitor","inductor","crystal","ldr","thermistor","diode","zener","schottky","led","battery","buzzer","thyristor","triac"}
        if two_terminal:
            line(-40,0,-20,0);line(20,0,40,0)
        if s in {"resistor","variable_resistor","ldr","thermistor","potentiometer"}:
            if s=="potentiometer":line(-40,0,-20,0);line(20,0,40,0)
            # Prostokąt jest wariantem europejskim; PN wdrażająca EN używa
            # tego samego rysunku, nie amerykańskiego zygzaka.
            if self.standard == "IEEE/ANSI":
                path=QPainterPath(QPointF(-20,0))
                for x,y in ((-16,-7),(-8,7),(0,-7),(8,7),(16,-7),(20,0)):
                    path.lineTo(x,y)
                p.drawPath(path)
            else:
                p.drawRect(QRectF(-20,-7,40,14))
            if s=="potentiometer":self._arrow(p,QPointF(0,-40),QPointF(0,-8))
            if s=="variable_resistor":self._arrow(p,QPointF(13,20),QPointF(-13,-20))
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
        elif s in {"lamp", "ac_source"}:
            line(-40,0,-16,0);line(16,0,40,0)
            p.drawEllipse(QRectF(-16,-16,32,32))
            if s == "lamp":
                line(-11,-11,11,11);line(-11,11,11,-11)
            else:
                path=QPainterPath(QPointF(-11,0))
                path.cubicTo(-7,-16,-4,-16,0,0)
                path.cubicTo(4,16,7,16,11,0)
                p.drawPath(path)
        elif s=="spst":
            line(-40,0,-20,0);line(20,0,40,0)
            closed = self.component.properties.get("sim_closed", "false") == "true"
            line(-20,0,20,0 if closed else -15)
            p.drawEllipse(QPointF(-20,0),2,2);p.drawEllipse(QPointF(20,0),2,2)
        elif s=="ground":
            line(0,-20,0,0);line(-13,0,13,0);line(-8,5,8,5);line(-3,10,3,10)
        elif s=="power":
            line(0,20,0,-7);line(-10,-7,10,-7)
        elif s=="switch":
            line(-40,0,-20,0);line(20,0,40,0)
            line(-40,20,-30,20);line(-30,20,-30,0)
            line(40,20,30,20);line(30,20,30,0)
            pressed=self.component.properties.get("sim_closed","false")=="true"
            level=0 if pressed else -10
            line(-20,level,20,level);line(0,level,0,level-10)
            p.drawEllipse(QPointF(-20,0),2,2);p.drawEllipse(QPointF(20,0),2,2)
        elif s=="spdt":
            selected=self.component.properties.get("sim_closed","false")=="true"
            line(-40,0,-20,0);line(-20,0,15,16 if selected else -16)
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
        if self.standard != "IEEE/ANSI":
            p.drawRect(QRectF(-28,-25,50,50))
            symbol="&" if kind in {"and","nand"} else ">=1" if kind in {"or","nor"} else "=1" if kind in {"xor","xnor"} else "1"
            font=QFont("Arial"); font.setPixelSize(18); p.setFont(font)
            p.drawText(QRectF(-27,-24,48,48),Qt.AlignmentFlag.AlignCenter,symbol)
            for y in ((0,) if kind=="not" else (-20,20)):
                line(-40,y,-28,y)
            if kind in {"not","nand","nor","xnor"}:
                p.drawEllipse(QPointF(27,0),5,5); line(32,0,40,0)
            else:
                line(22,0,40,0)
            p.restore()
            if kind != "not":
                self._line(p,-20,-20,-20,-10); self._line(p,-20,20,-20,10)
            self._bottom_labels(p)
            return
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
        ink = painter.pen().color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
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
        color=QColor(getattr(self, "ink_color", "#163247"))
        painter.setPen(QPen(color,1.35,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.asset_case:
            painter.setBrush(QColor(getattr(self,'paper_color','white')))
            from app.canvas.case_shapes import outline
            body,strokes=outline(self.asset_case['shapes']); painter.drawPath(body)
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawPath(strokes)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(self._symbol_rect.adjusted(8,8,-8,-8),Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter,self.display_name)
            font=painter.font(); font.setPixelSize(10); painter.setFont(font)
            for pin in self.definition.pins:
                point=QPointF(pin.x,pin.y)
                from app.canvas.case_shapes import pin_root
                inside=pin_root(self.asset_case['shapes'],point)
                painter.drawLine(inside,point)
                label=pin.number+(' '+pin.name if self.asset_case.get('show_pin_names',False) else '')
                self._pin_label(painter,QPointF(pin.x+4,pin.y-4),label)
            for region in self.asset_case.get('regions',[]):
                painter.drawEllipse(QRectF(*region['rect'])) if region['kind']=='light' else painter.drawRect(QRectF(*region['rect']))
        elif self.definition.symbol in {"logic_input", "logic_output"}:
            live_logic = hasattr(self, "logic_label")
            painter.drawRect(QRectF(-20,-20,40,40))
            if self.definition.symbol == "logic_input":
                painter.drawLine(QPointF(20,0),QPointF(40,0))
            else:
                painter.drawLine(QPointF(-40,0),QPointF(-20,0))
            painter.save()
            if live_logic:
                font = painter.font(); font.setPixelSize(28); font.setBold(True)
                painter.setFont(font)
                if self.logic_label == "1": painter.setPen(QColor("#ffffff"))
            if int(round(self.rotation())) % 360 in (90,180): painter.rotate(180)
            painter.drawText(QRectF(-20,-20,40,40), Qt.AlignmentFlag.AlignCenter,
                             getattr(self, "logic_label", "IN" if self.definition.symbol == "logic_input" else "OUT"))
            painter.restore()
            self._bottom_labels(painter)
        elif self.definition.name == 'Karta RFID':
            body=self.symbol_rect(self.definition).adjusted(3,3,-3,-3)
            painter.setPen(QPen(QColor('#c6cbd0'),2)); painter.setBrush(QColor('#e5e8e8'))
            painter.drawRoundedRect(body,9,9)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor('#263d50'))
            painter.drawRoundedRect(QRectF(body.left()+2,body.top()+3,body.width()-4,18),6,6)
            chip=QRectF(body.left()+13,body.bottom()-34,34,24)
            painter.setPen(QPen(QColor('#83692d'),1)); painter.setBrush(QColor('#dfc36f'))
            painter.drawRoundedRect(chip,4,4)
            painter.drawLine(QPointF(chip.center().x(),chip.top()),QPointF(chip.center().x(),chip.bottom()))
            painter.drawLine(QPointF(chip.left(),chip.center().y()),QPointF(chip.right(),chip.center().y()))
            painter.setPen(QPen(QColor('#aab8c4'),1)); painter.setBrush(Qt.BrushStyle.NoBrush)
            for inset in (7,11,15):
                painter.drawRoundedRect(body.adjusted(inset,inset,-inset,-inset),7,7)
            label_x=chip.right()+7
            label_width=max(0.0,body.right()-label_x-5)
            # The card ID goes above the RFID marking in the upper area to the
            # chip's right, as indicated on the card-layout sketch.
            painter.setPen(QColor('#243747'))
            font=painter.font(); font.setPixelSize(9); font.setBold(False); painter.setFont(font)
            id_rect=QRectF(label_x,body.top()+24,label_width,16)
            painter.drawText(id_rect,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
                str(self.component.properties.get('rfid_id','A1B2C3D4')))
            font.setPixelSize(11); font.setBold(True); painter.setFont(font)
            painter.drawText(QRectF(label_x,id_rect.bottom(),label_width,18),
                Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,'RFID')
            painter.setPen(QPen(QColor('#254151'),2)); painter.setBrush(Qt.BrushStyle.NoBrush)
            for radius in (5,9,13):
                painter.drawArc(QRectF(body.right()-30-radius,body.center().y()-radius,2*radius,2*radius),-55*16,110*16)
        elif self.definition.name == 'Zapałka':
            lit=self.component.properties.get('sim_lit')=='true'
            shaft_start=QPointF(-43,14); shaft_end=QPointF(37,-12)
            painter.setPen(QPen(QColor('#684426'),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            painter.drawLine(shaft_start,shaft_end)
            painter.setPen(QPen(QColor('#c28a4c'),5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            painter.drawLine(shaft_start,shaft_end)
            painter.setPen(QPen(QColor('#56332c'),1)); painter.setBrush(QColor('#ba3e32'))
            painter.drawEllipse(QPointF(42,-14),8,6)
            if lit:
                painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(255,115,35,80))
                painter.drawEllipse(QPointF(48,-18),19,17)
                painter.setBrush(QColor('#ff8a27'))
                painter.drawPolygon(QPolygonF([QPointF(39,-17),QPointF(43,-32),QPointF(49,-25),QPointF(54,-37),QPointF(57,-20),QPointF(51,-10),QPointF(43,-11)]))
                painter.setBrush(QColor('#ffe28a'))
                painter.drawPolygon(QPolygonF([QPointF(46,-17),QPointF(49,-27),QPointF(53,-18),QPointF(50,-13)]))
        elif self.definition.symbol == 'ultrasonic_target':
            body=QRectF(-52,-30,104,60)
            painter.setPen(QPen(QColor('#4f5962'),2)); painter.setBrush(QColor('#b5bdc3'))
            painter.drawRoundedRect(body,4,4)
            painter.setPen(QPen(QColor('#77838b'),1)); painter.setBrush(QColor('#dbe0e3'))
            painter.drawRoundedRect(body.adjusted(7,7,-7,-7),2,2)
            for x in range(-32,33,16): painter.drawLine(QPointF(x,-20),QPointF(x,20))
            painter.setPen(QColor('#36424a')); font=painter.font(); font.setPixelSize(9); painter.setFont(font)
            painter.drawText(QRectF(-48,31,96,14),Qt.AlignmentFlag.AlignCenter,'HC-SR04 target')
            self._bottom_labels(painter)
        elif self.definition.symbol == 'motion_target':
            # Neutral, instantly recognizable person silhouette used as a
            # movable heat/motion source in the simulation sandbox.
            painter.setPen(QPen(QColor('#263b4b'),2)); painter.setBrush(QColor('#dfb783'))
            painter.drawEllipse(QPointF(0,-39),13,13)
            painter.setPen(QPen(QColor('#233e52'),2)); painter.setBrush(QColor('#397aa2'))
            painter.drawRoundedRect(QRectF(-17,-24,34,43),8,8)
            painter.setPen(QPen(QColor('#263b4b'),7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(-9,17),QPointF(-13,48)); painter.drawLine(QPointF(9,17),QPointF(13,48))
            painter.setPen(QPen(QColor('#dfb783'),6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(-15,-15),QPointF(-29,7)); painter.drawLine(QPointF(15,-15),QPointF(29,7))
            self._bottom_labels(painter)
        elif self.definition.symbol == 'ir_remote':
            body=QRectF(-29,-69,58,138)
            painter.setPen(QPen(QColor('#080d12'),2)); painter.setBrush(QColor('#252b31'))
            painter.drawRoundedRect(body,15,15)
            painter.setPen(QPen(QColor('#424b54'),1)); painter.setBrush(QColor('#0d1217'))
            painter.drawRoundedRect(QRectF(-21,-61,42,20),7,7)
            painter.setBrush(QColor('#c34a45')); painter.drawEllipse(QPointF(0,-51),5,5)
            painter.setBrush(QColor('#56636e'))
            for row in range(4):
                for col in range(3): painter.drawRoundedRect(QRectF(-18+col*13,-32+row*20,10,12),4,4)
            painter.setPen(QColor('#c6d5df')); font=painter.font(); font.setPixelSize(8); painter.setFont(font)
            painter.drawText(QRectF(-25,52,50,12),Qt.AlignmentFlag.AlignCenter,'IR')
            self._bottom_labels(painter)
        elif self.definition.name in CABLE_NAMES:
            props=self.component.properties; prefix='usb_' if self.definition.name=='Kabel USB' else 'jumper_'
            a,b=self.cable_points()
            path=QPainterPath(a); path.cubicTo(a+QPointF(0,80),b+QPointF(0,80),b)
            painter.save(); painter.setPen(QPen(color,5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); painter.drawPath(path); painter.restore()
            from app.canvas.connector_art import socket
            for point,side,default in ((a,'a','A'),(b,'b','C')):
                painter.save(); painter.translate(point); x=0
                painter.drawRoundedRect(QRectF(x-15,-15,30,30),4,4)
                if prefix=='usb_': socket(painter,QRectF(x-23,-25,46,28),self.component.properties.get("sim_usb_"+side+"_type",default))
                else:
                    from app.simulation.jumper import GENDERS
                    gender=GENDERS[self.component.library_id][0 if side=='a' else 1]
                    from app.canvas.connector_art import jumper_contact
                    jumper_contact(painter,QPointF(0,-28),gender)
                painter.restore()
            self._bottom_labels(painter)
        elif self.definition.name=="Klawiatura USB":
            body=self.connector_body(); painter.setBrush(QColor(getattr(self,"paper_color","#ffffff")))
            painter.drawRoundedRect(body,6,6)
            for row in range(4):
                for col in range(10 if row<3 else 5):
                    painter.drawRoundedRect(QRectF(body.left()+7+col*(body.width()-14)/10,body.top()+6+row*13,(body.width()-18)/10,10),1,1)
            painter.drawText(body.adjusted(5,60,-5,-3),Qt.AlignmentFlag.AlignCenter,self.display_name)
            from app.canvas.connector_art import paint_connectors
            paint_connectors(self,painter,body)
        elif self.definition.symbol == "multi_switch":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            self._line(painter,-60,0,-25,0)
            selected=int(self.component.properties.get("sim_position","1"))
            if selected==0 and self.component.properties.get('sim_allow_off','true')=='false': selected=1
            for pin in self.definition.pins[1:]:
                self._line(painter,25,pin.y,60,pin.y)
                painter.drawEllipse(QPointF(25,pin.y),3,3)
                self._pin_label(painter,QRectF(36,pin.y-16,20,14),pin.name)
            destination=next((p for p in self.definition.pins if p.name==str(selected)),None)
            self._line(painter,-25,0,20 if destination else 0,destination.y if destination else -25)
            self._bottom_labels(painter)
        elif self.definition.name == "Kostka zasilająca USB":
            painter.setBrush(QColor(getattr(self,"paper_color","#ffffff")))
            painter.drawRoundedRect(QRectF(-30,-32,60,64),8,8)
            self._line(painter,-18,-32,-18,-49); self._line(painter,18,-32,18,-49)
            from app.canvas.connector_art import socket
            from app.canvas.connector_art import socket_regions
            for kind,rect in socket_regions(self,self.connector_body()): socket(painter,rect,kind)
            self._bottom_labels(painter)
        elif self.definition.symbol == "breadboard":
            painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRoundedRect(QRectF(-220,-140,440,280),8,8)
            painter.drawLine(QPointF(0,-125),QPointF(0,105))
            for pin in self.definition.pins: painter.drawRect(QRectF(pin.x-4,pin.y-4,8,8))
            font=QFont(painter.font()); font.setPixelSize(9); painter.save(); painter.setFont(font)
            for column,x in zip('ABCDEFGHIJ',[-140,-120,-100,-80,-60,60,80,100,120,140]): painter.drawText(QRectF(x-7,-122,14,12),Qt.AlignmentFlag.AlignCenter,column)
            for row in range(10): painter.drawText(QRectF(-16,-107+row*20,32,14),Qt.AlignmentFlag.AlignCenter,str(row+1))
            painter.restore()
            self._bottom_labels(painter)
        elif self.definition.symbol == "goldpin":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(-5,-15,30,30))
            # RC1: thick monochrome male pin or hollow female socket, attached
            # to the offset square. Cable housings are painted separately.
            if self.definition.name=='Goldpin żeński':
                painter.drawRect(QRectF(-40,-5,35,10))
            else:
                painter.save(); painter.setPen(QPen(color,8,Qt.PenStyle.SolidLine,Qt.PenCapStyle.FlatCap))
                painter.drawLine(QPointF(-40,0),QPointF(-5,0)); painter.restore()
            self._line(painter,25,0,40,0)
            self._bottom_labels(painter)
        elif self.definition.symbol == "meter":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0,0),20,20)
            self._line(painter,-40,0,-20,0); self._line(painter,20,0,40,0)
            letter={"Woltomierz":"V","Amperomierz":"A","Omomierz":"Ω","Tester ciągłości":"•","Oscyloskop":"~"}.get(self.definition.name,"?")
            painter.drawText(QRectF(-20,-20,40,40),Qt.AlignmentFlag.AlignCenter,letter)
            self._bottom_labels(painter)
        elif self.definition.symbol.startswith("gate_"):
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
        painter.setBrush(QColor(getattr(self, "paper_color", "white")))
        for pin in (() if self.definition.name in CABLE_NAMES or self.definition.name in {"Kostka zasilająca USB","Klawiatura USB"} else self.definition.pins[1:] if self.definition.symbol=='goldpin' else self.definition.pins):
            painter.drawEllipse(QPointF(pin.x,pin.y),1.6,1.6)
        if self.isSelected():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#168bd2"),1,Qt.PenStyle.DashLine))
            painter.drawRect(self._hit_rect)
        painter.restore()
