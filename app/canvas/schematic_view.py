"""Płótno edytora: interakcje są oddzielone od symboli i danych dokumentu.

Silne referencje trzymamy dla wszystkich obiektów Qt. Przewody wiążemy z
konkretnym pinem i węzłem, nie z nazwą ani boundingRect komponentu.
"""
from __future__ import annotations
from copy import deepcopy
from math import ceil, floor
from PySide6.QtCore import QByteArray, QMimeData, QLineF, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QCursor, QFont
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView, QGraphicsRectItem
from app.core.models import Annotation, ComponentInstance, Project, Sheet, Wire, new_id
from app.canvas.component_item import ComponentItem
from app.canvas.annotations import AnnotationItem, InlineAnnotationEditor, edit_annotation
from app.canvas.page import (GRID_STEP, draw_page, page_rect, drawing_rect, title_block_rect,
                             title_field_layout, drawing_contains, fit_component_position, route_allowed)
from app.libraries.built_in import get_definition
from app.services.clipboard import MIME_TYPE, encode_selection, decode_selection, prepare_paste

PAGE_RECT = QRectF(0, 0, 1188, 840)  # zgodność z dawnymi integracjami; widok używa paper_rect()
ITEM_DATA_KIND, ITEM_DATA_ID = 0, 1

class PaperScene(QGraphicsScene):
    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#e5ebf0"))
        draw_page(painter, self.view._sheet, self.view.project, self.view.settings,
                  editing_field=self.view._title_field)

class WireItem(QGraphicsPathItem):
    """boundingRect obejmuje kropki i pióro, aby nie zostawiać artefaktów."""
    def __init__(self, points):
        super().__init__()
        self.setPen(QPen(QColor("#167d3d"), 2.0))
        self.set_points(points)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-1)

    def set_points(self, points):
        self.prepareGeometryChange()
        self.points = points
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        self.setPath(path)
        self.update()

    def boundingRect(self):
        return super().boundingRect().adjusted(-5, -5, 5, 5)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(8)
        return stroker.createStroke(self.path())

    def paint(self, painter, option, widget=None):
        painter.save()
        painter.setPen(QPen(QColor("#df6b45" if self.isSelected() else "#167d3d"), 2))
        painter.drawPath(self.path())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#167d3d"))
        for point in (self.points[0], self.points[-1]):
            painter.drawEllipse(point, 3, 3)
        painter.restore()

class SchematicView(QGraphicsView):
    def __init__(self, parent=None, project=None, settings=None, sheet=None):
        super().__init__(parent)
        self.project = project
        self.settings = settings
        self._sheet = None
        self.scene = PaperScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._component_items, self._wire_items, self._comment_items = {}, {}, {}
        self.tool = "select"
        self._wire_start = self._wire_preview = self._dragged_wire_end = None
        self._annotation_editor = None
        self._title_editor = None
        self._title_field = None
        self._pan_active = False
        self._pan_last = None
        self._rubber_start = None
        self._rubber_item = None
        self._group_drag = None
        self._paste_serial = 0
        self._last_paste = None
        self.on_change = self.on_selection = self.on_edit_properties = None
        self._page_fitted = False
        self._fitting = False
        self._auto_fit = True
        self._refreshing = False
        self._loading = False
        self.scene.selectionChanged.connect(self._selection_changed)
        self.set_tool("select")
        if sheet:
            self.load_sheet(sheet)

    def paper_rect(self):
        return page_rect(self._sheet)

    def apply_settings(self, settings):
        self.settings = settings
        if self._sheet:
            selected = {i.data(1) for i in self.scene.selectedItems()}
            self.load_sheet(self._sheet)
            for key in selected:
                if key in self._component_items:
                    self._component_items[key].setSelected(True)
        self.viewport().update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._page_fitted:
            self._page_fitted = True
            QTimer.singleShot(0, self.fit_page)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._auto_fit and not self._fitting:
            QTimer.singleShot(0, self.fit_page)

    def fit_page(self):
        if self._fitting:
            return
        self._fitting = True
        self.resetTransform()
        self.fitInView(self.paper_rect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._auto_fit = True
        self._fitting = False

    def render_page(self, painter, target_rect=None):
        """Ten sam renderer w PNG/SVG/PDF; bez zaznaczeń i podglądu kabla."""
        selected = list(self.scene.selectedItems())
        self.scene.blockSignals(True)
        for item in selected:
            item.setSelected(False)
        if self._wire_preview:
            self._wire_preview.hide()
        try:
            target = target_rect if target_rect is not None else QRectF(painter.viewport())
            self.scene.render(painter, target, self.paper_rect(), Qt.AspectRatioMode.KeepAspectRatio)
        finally:
            for item in selected:
                item.setSelected(True)
            if self._wire_preview:
                self._wire_preview.show()
            self.scene.blockSignals(False)

    def set_tool(self, tool):
        if self._group_drag:
            self._move_selection_group(QPointF())
            self._group_drag = None
        self.tool = tool
        self._clear_wire_preview()
        # Zaznaczanie prostokątem jest przypisane do PPM, więc Qt nie może
        # przechwytywać LPM własnym RubberBandDrag.
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor if tool == "select" else Qt.CursorShape.CrossCursor)

    def load_sheet(self, sheet):
        self._loading = True
        self._clear_wire_preview()
        if self._rubber_item is not None:
            self.scene.removeItem(self._rubber_item)
            self._rubber_item = None
        self._rubber_start = None
        self._title_editor = self._title_field = None
        self._annotation_editor = None
        self._dragged_wire_end = None
        self._group_drag = None
        self.scene.blockSignals(True)
        self.scene.clear()
        self._component_items.clear()
        self._wire_items.clear()
        self._comment_items.clear()
        self._sheet = sheet
        self.scene.setSceneRect(self.paper_rect())
        if self.project:
            self.project.ensure_references()
        for component in sheet.components:
            self._add_component_item(component)
        for wire in sheet.wires:
            self._add_wire_item(wire)
        for comment in sheet.comments:
            self._add_comment_item(comment)
        self._join_coincident_ends()
        self._refresh_attached_wires()
        self.scene.blockSignals(False)
        self._loading = False
        self.viewport().update()

    def _add_component_item(self, component):
        item = ComponentItem(component, language=getattr(self.settings, "language", "en"),
                             standard=getattr(self._sheet, "standard", getattr(self.settings, "standard", "EN")),
                             custom_components=self.project.custom_components if self.project else None)
        item.on_position_changed = self._refresh_attached_wires
        self._component_items[component.id] = item
        self.scene.addItem(item)

    def refresh_component(self, component_id):
        item = self._component_items.get(component_id)
        if item:
            item.update_labels()
            item.update()
        self.viewport().update()

    def add_component(self, library_id, global_pos=None):
        if not self._sheet:
            return
        if global_pos is None:
            global_pos = QCursor.pos()
        local = self.mapFromGlobal(global_pos)
        point = self._snap(self.mapToScene(local))
        definition = get_definition(library_id, self.project.custom_components if self.project else None)
        if definition is None:
            raise ValueError("Unknown component / Nieznany element")
        # Rozmiar modułu, nie stałe 80 jednostek, wyznacza wolny obszar. Dzięki
        # temu nawet Mega z pełnymi złączami nie pojawi się poza kartką.
        preview = ComponentItem(ComponentInstance(library_id, 0, 0, unit=definition.default_unit),
                                language=getattr(self.settings, "language", "en"),
                                custom_components=self.project.custom_components if self.project else None)
        point = fit_component_position(self._sheet, preview._hit_rect, point)
        if point is None:
            raise ValueError("Component does not fit this sheet; choose a larger paper size. / Element nie mieści się na arkuszu; wybierz większy format.")
        project = self.project or Project(sheets=[self._sheet])
        component = project.new_component(library_id, point.x(), point.y())
        self._sheet.components.append(component)
        self._add_component_item(component)
        self._attach_free_wire_ends_to_component_pins()
        self.scene.clearSelection()
        self._component_items[component.id].setSelected(True)
        self._changed()
        return component

    def _add_wire_item(self, wire):
        points = [QPointF(*p) for p in wire.points] if wire.points else self._route_45_degrees(QPointF(wire.start_x, wire.start_y), QPointF(wire.end_x, wire.end_y))
        item = WireItem(points)
        item.setData(0, "wire")
        item.setData(1, wire.id)
        self._wire_items[wire.id] = item
        self.scene.addItem(item)

    def _add_comment_item(self, comment):
        item = AnnotationItem(comment)
        self._comment_items[comment.id] = item
        self.scene.addItem(item)

    def _wire_path(self, points):
        path = QPainterPath(points[0])
        for p in points[1:]:
            path.lineTo(p)
        return path

    @staticmethod
    def _route_45_degrees(start, end):
        dx, dy = end.x()-start.x(), end.y()-start.y()
        if abs(dx) < .001 or abs(dy) < .001 or abs(abs(dx)-abs(dy)) < .001:
            return [start, end]
        middle = QPointF(start.x()+(abs(dy) if dx > 0 else -abs(dy)), end.y()) if abs(dx) > abs(dy) else QPointF(end.x(), start.y()+(abs(dx) if dy > 0 else -abs(dx)))
        return [start, middle, end]

    def _route_in_drawing_area(self, start, end):
        """W obszarze L wybieramy legalną trasę, nadal wyłącznie co 45°."""
        candidates = [self._route_45_degrees(start, end),
                      list(reversed(self._route_45_degrees(end, start)))]
        block = title_block_rect(self._sheet)
        corner = QPointF(block.left()-GRID_STEP, block.top()-GRID_STEP)
        candidates.append(self._route_45_degrees(start, corner)[:-1]+self._route_45_degrees(corner, end))
        return next((route for route in candidates if route_allowed(self._sheet, route)), None)

    @staticmethod
    def _snap(point):
        return QPointF(round(point.x()/GRID_STEP)*GRID_STEP, round(point.y()/GRID_STEP)*GRID_STEP)

    def _ends(self):
        for wire in self._sheet.wires if self._sheet else []:
            for side in ("start", "end"):
                yield wire, side

    @staticmethod
    def _end_point(wire, side):
        return QPointF(getattr(wire, side+"_x"), getattr(wire, side+"_y"))

    def _snap_to_pin(self, point, exclude_wire=None):
        # Promień mniejszy od połowy odstępu pinów: sąsiedni pin nie zostanie
        # przypadkowo przejęty. Nie przyciągamy końca do jego poprzedniej pozycji.
        targets = [(pin, item.component.id, index) for item in self._component_items.values()
                   for index, pin in enumerate(item.pin_positions())]
        excluded_junction = None
        if exclude_wire and self._dragged_wire_end:
            wire = next((w for w in self._sheet.wires if w.id == exclude_wire), None)
            if wire:
                excluded_junction = getattr(wire, ("start" if self._dragged_wire_end[1] else "end")+"_junction_id")
        targets += [(self._end_point(w, s), getattr(w, s+"_component_id"), getattr(w, s+"_pin_index"))
                    for w, s in self._ends() if w.id != exclude_wire and
                    (not excluded_junction or getattr(w, s+"_junction_id") != excluded_junction)]
        # Odgałęzienie może zaczynać się też w środku istniejącego odcinka.
        # Krzyżowanie dwóch przewodów samo w sobie nie tworzy połączenia:
        # rozcięcie powstaje dopiero po świadomym zakończeniu kabla w tym punkcie.
        grid_point = self._snap(point)
        for wire in self._sheet.wires if self._sheet else []:
            if wire.id == exclude_wire:
                continue
            vertices = [QPointF(*p) for p in wire.points] if wire.points else [self._end_point(wire, "start"), self._end_point(wire, "end")]
            if any(self._point_on_segment(grid_point, a, b) for a, b in zip(vertices, vertices[1:])):
                targets.append((grid_point, None, None))
        if targets:
            nearest = min(targets, key=lambda t: QLineF(point, t[0]).length())
            if QLineF(point, nearest[0]).length() <= 9:
                return nearest
        return self._snap(point), None, None

    @staticmethod
    def _point_on_segment(point, a, b):
        distance = QLineF(a, b).length()
        return distance > .001 and abs(QLineF(a, point).length()+QLineF(point, b).length()-distance) < .001

    def _split_wires_at_point(self, point, exclude_wire=None):
        """Rozcina odcinek w węźle bez utraty przypięcia dalszego końca.

        Nowy odcinek dostaje UUID, a oryginalny zachowuje swój. Dwa końce w
        tym samym punkcie scalają się następnie w _join_coincident_ends.
        """
        for wire in list(self._sheet.wires):
            if wire.id == exclude_wire or point in (self._end_point(wire, "start"), self._end_point(wire, "end")):
                continue
            vertices = [QPointF(*p) for p in wire.points] if wire.points else self._route_45_degrees(self._end_point(wire, "start"), self._end_point(wire, "end"))
            segment = next((i for i in range(len(vertices)-1) if self._point_on_segment(point, vertices[i], vertices[i+1])), None)
            if segment is None:
                continue
            tail = Wire(point.x(), point.y(), wire.end_x, wire.end_y,
                        end_component_id=wire.end_component_id, end_pin_index=wire.end_pin_index,
                        end_pin_number=wire.end_pin_number, end_junction_id=wire.end_junction_id)
            before, after = vertices[:segment+1]+[point], [point]+vertices[segment+1:]
            # Jeżeli węzeł trafił dokładnie w zakręt, usuń jego powtórzenie.
            before = [p for i,p in enumerate(before) if i == 0 or p != before[i-1]]
            after = [p for i,p in enumerate(after) if i == 0 or p != after[i-1]]
            wire.end_x, wire.end_y = point.x(), point.y()
            wire.end_component_id = wire.end_pin_index = wire.end_pin_number = wire.end_junction_id = None
            wire.points = [[p.x(),p.y()] for p in before]
            tail.points = [[p.x(),p.y()] for p in after]
            self._sheet.wires.append(tail)
            self._add_wire_item(tail)

    def _join_coincident_ends(self):
        groups = {}
        for wire, side in self._ends():
            point = self._end_point(wire, side)
            groups.setdefault((round(point.x(), 4), round(point.y(), 4)), []).append((wire, side))
        for ends in groups.values():
            if len(ends) < 2:
                continue
            old = {getattr(w, s+"_junction_id") for w, s in ends} - {None}
            junction = sorted(old)[0] if old else new_id()
            # Scala ID także gdy oba węzły były już większymi grupami.
            for w, s in self._ends():
                if getattr(w, s+"_junction_id") in old:
                    setattr(w, s+"_junction_id", junction)
            for w, s in ends:
                setattr(w, s+"_junction_id", junction)

    def _refresh_attached_wires(self):
        if not self._sheet or self._refreshing:
            return
        self._refreshing = True
        try:
            anchors = {}
            for wire, side in self._ends():
                comp_id, pin = getattr(wire, side+"_component_id"), getattr(wire, side+"_pin_index")
                item = self._component_items.get(comp_id)
                if item and pin is not None:
                    pins = item.pin_positions()
                    if pin < len(pins):
                        point = pins[pin]
                        setattr(wire, side+"_pin_number", item.definition.pins[pin].number)
                        setattr(wire, side+"_x", point.x())
                        setattr(wire, side+"_y", point.y())
                        junction = getattr(wire, side+"_junction_id")
                        if junction:
                            anchors[junction] = point
            for wire, side in self._ends():
                junction = getattr(wire, side+"_junction_id")
                if junction in anchors:
                    p = anchors[junction]
                    setattr(wire, side+"_x", p.x())
                    setattr(wire, side+"_y", p.y())
            for wire in self._sheet.wires:
                start, end = self._end_point(wire, "start"), self._end_point(wire, "end")
                unchanged = (len(wire.points) >= 2 and QPointF(*wire.points[0]) == start and QPointF(*wire.points[-1]) == end)
                route = ([QPointF(*p) for p in wire.points] if unchanged else
                         self._route_in_drawing_area(start, end) or self._route_45_degrees(start, end))
                wire.points = [[p.x(), p.y()] for p in route]
                if wire.id in self._wire_items:
                    self._wire_items[wire.id].set_points(route)
        finally:
            self._refreshing = False

    def _attach_end_if_near_pin(self, wire, is_start):
        side = "start" if is_start else "end"
        point = self._end_point(wire, side)
        candidates = [(pin, item.component.id, index) for item in self._component_items.values() for index, pin in enumerate(item.pin_positions())]
        if candidates:
            pin, comp, index = min(candidates, key=lambda t: QLineF(point, t[0]).length())
            if QLineF(point, pin).length() <= 6:
                setattr(wire, side+"_component_id", comp)
                setattr(wire, side+"_pin_index", index)
                setattr(wire, side+"_x", pin.x())
                setattr(wire, side+"_y", pin.y())

    def _attach_free_wire_ends_to_component_pins(self):
        for wire, side in self._ends():
            if getattr(wire, side+"_component_id") is None:
                self._attach_end_if_near_pin(wire, side == "start")
        self._join_coincident_ends()
        self._refresh_attached_wires()

    def _nearest_wire_endpoint(self, point):
        candidates = [(self._end_point(w, s), w.id, s == "start") for w, s in self._ends()]
        if not candidates:
            return None
        nearest = min(candidates, key=lambda t: QLineF(point, t[0]).length())
        return (nearest[1], nearest[2]) if QLineF(point, nearest[0]).length() <= 6 else None

    def _move_wire_endpoint(self, wire_id, is_start, point, component_id, pin_index):
        wire = next((w for w in self._sheet.wires if w.id == wire_id), None)
        if wire is None:
            return
        side = "start" if is_start else "end"
        junction = getattr(wire, side+"_junction_id")
        # Wspólny węzeł może mieć kilka przewodów. Żaden z nich nie może po
        # przesunięciu wchodzić do tabliczki ani na margines.
        for w, s in self._ends():
            if (w is wire and s == side) or (junction and getattr(w, s+"_junction_id") == junction):
                opposite = self._end_point(w, "end" if s == "start" else "start")
                if self._route_in_drawing_area(point, opposite) is None:
                    return
        for w, s in self._ends():
            if (w is wire and s == side) or (junction and getattr(w, s+"_junction_id") == junction):
                setattr(w, s+"_x", point.x())
                setattr(w, s+"_y", point.y())
                setattr(w, s+"_component_id", component_id)
                setattr(w, s+"_pin_index", pin_index)
                setattr(w, s+"_pin_number", None)
        self._refresh_attached_wires()

    def mousePressEvent(self, event):
        point = self.mapToScene(event.position().toPoint())
        item = self.scene.itemAt(point, self.transform())
        while item and item.parentItem():
            item = item.parentItem()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = True
            self._pan_last = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self._wire_start:
            self._clear_wire_preview()
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self.tool == "select":
            self._rubber_start = point
            self._rubber_item = QGraphicsRectItem(QRectF(point, point))
            self._rubber_item.setPen(QPen(QColor("#168bd2"), 1, Qt.PenStyle.DashLine))
            self._rubber_item.setBrush(Qt.BrushStyle.NoBrush)
            self._rubber_item.setZValue(1000)
            self.scene.addItem(self._rubber_item)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tool == "select":
                # Grupę przesuwamy jednym wektorem, zanim Qt rozpocznie
                # przeciąganie pojedynczego symbolu albo końcówki kabla.
                if item and item.isSelected() and len(self.scene.selectedItems()) > 1:
                    self._begin_selection_group(point)
                    event.accept()
                    return
                endpoint = self._nearest_wire_endpoint(point)
                if endpoint:
                    self._dragged_wire_end = endpoint
                    event.accept()
                    return
            if self.tool == "wire" and drawing_contains(self._sheet, point):
                snapped = self._snap_to_pin(point)
                if not drawing_contains(self._sheet, snapped[0]):
                    event.accept()
                    return
                if self._wire_start is None:
                    self._wire_start = snapped
                    self._wire_preview = QGraphicsPathItem(self._wire_path([snapped[0], snapped[0]]))
                    self._wire_preview.setPen(QPen(QColor("#e76f51"), 2, Qt.PenStyle.DashLine))
                    self.scene.addItem(self._wire_preview)
                else:
                    start, comp, pin = self._wire_start
                    end, end_comp, end_pin = snapped
                    if start != end:
                        route = self._route_in_drawing_area(start, end)
                        if route is None:
                            event.accept()
                            return
                        wire = Wire(start.x(), start.y(), end.x(), end.y(), start_component_id=comp,
                                    start_pin_index=pin, end_component_id=end_comp, end_pin_index=end_pin)
                        wire.points = [[p.x(), p.y()] for p in route]
                        self._sheet.wires.append(wire)
                        self._add_wire_item(wire)
                        self._split_wires_at_point(start, wire.id)
                        self._split_wires_at_point(end, wire.id)
                        self._join_coincident_ends()
                        self._refresh_attached_wires()
                        self._changed()
                    self._clear_wire_preview()
                event.accept()
                return
            if self.tool == "delete":
                if item:
                    self._delete_item(item)
                    self._changed()
                event.accept()
                return
            if self.tool == "comment" and self.paper_rect().contains(point):
                self._begin_inline_comment(self._snap(point))
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept()
            return
        point = self.mapToScene(event.position().toPoint())
        field = self._title_field_at(point)
        if field is not None:
            self._begin_title_edit(field)
            event.accept()
            return
        item = self.itemAt(event.position().toPoint())
        while item and item.parentItem():
            item = item.parentItem()
        if item and self.tool == "select":
            if item.data(0) == "component" and self.on_edit_properties:
                self._dragged_wire_end = None
                self._group_drag = None
                item.setSelected(True)
                self.on_edit_properties(item.component)
                event.accept()
                return
            if item.data(0) == "comment":
                self._comment_items.pop(item.annotation.id, None)
                self.scene.removeItem(item)
                self._begin_inline_comment(QPointF(item.x(), item.y()), item.annotation)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_active and self._pan_last is not None:
            current = event.position().toPoint()
            delta = current - self._pan_last
            self._pan_last = current
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._rubber_item is not None and self._rubber_start is not None:
            point = self.mapToScene(event.position().toPoint())
            self._rubber_item.setRect(QRectF(self._rubber_start, point).normalized())
            event.accept()
            return
        if self._group_drag is not None:
            point = self.mapToScene(event.position().toPoint())
            self._move_selection_group(self._snap(point - self._group_drag["origin"]))
            event.accept()
            return
        if self._dragged_wire_end:
            candidate = self.mapToScene(event.position().toPoint())
            if drawing_contains(self._sheet, candidate):
                snapped = self._snap_to_pin(candidate, self._dragged_wire_end[0])
                self._move_wire_endpoint(*self._dragged_wire_end, *snapped)
            event.accept()
            return
        if self._wire_preview:
            end, _, _ = self._snap_to_pin(self.mapToScene(event.position().toPoint()))
            route = self._route_in_drawing_area(self._wire_start[0], end)
            self._wire_preview.setPath(self._wire_path(route) if route else QPainterPath())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._group_drag is not None:
            moved = self._group_drag["delta"] != QPointF()
            origin = self._group_drag["origin"]
            self._group_drag = None
            if moved:
                self._attach_free_wire_ends_to_component_pins()
                self._changed()
            elif not event.modifiers():
                # Sam klik nadal wybiera jeden obiekt, dopiero ruch myszy
                # uruchamia przesunięcie całego wcześniejszego zaznaczenia.
                item = self.scene.itemAt(origin, self.transform())
                while item and item.parentItem():
                    item = item.parentItem()
                self.scene.clearSelection()
                if item:
                    item.setSelected(True)
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_active:
            self._pan_active = False
            self._pan_last = None
            self.setCursor(Qt.CursorShape.ArrowCursor if self.tool == "select" else Qt.CursorShape.CrossCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self._rubber_item is not None:
            rect = self._rubber_item.rect().normalized()
            self.scene.removeItem(self._rubber_item)
            self._rubber_item = self._rubber_start = None
            self.scene.clearSelection()
            for candidate in self.scene.items(rect, Qt.ItemSelectionMode.IntersectsItemShape):
                if candidate.data(0) in {"component", "wire", "comment"}:
                    candidate.setSelected(True)
            event.accept()
            return
        if self._dragged_wire_end:
            wire_id, start = self._dragged_wire_end
            wire = next((w for w in self._sheet.wires if w.id == wire_id), None)
            if wire:
                self._split_wires_at_point(self._end_point(wire, "start" if start else "end"), wire.id)
            self._dragged_wire_end = None
            self._join_coincident_ends()
            self._refresh_attached_wires()
            self._changed()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self._sync_component_positions():
            self._attach_free_wire_ends_to_component_pins()
            self._changed()

    def keyPressEvent(self, event):
        # QGraphicsTextItem nie jest QWidget: litery R/S/D i Delete muszą
        # trafić do jego kursora tekstowego, nie do narzędzi schematu.
        if self.is_editing_text():
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            return
        if event.key() == Qt.Key.Key_R and not event.modifiers():
            self.rotate_selected_components()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self._group_drag is not None:
                self._move_selection_group(QPointF())
                self._group_drag = None
            self._clear_wire_preview()
            return
        super().keyPressEvent(event)

    def is_editing_text(self):
        return self._title_editor is not None or self._annotation_editor is not None

    def finish_text_editing(self):
        """Zapis/eksport uwzględnia też tekst aktualnie wpisywany na arkuszu."""
        if self._title_editor is not None:
            self._finish_title_edit(self._title_editor.toPlainText())
        if self._annotation_editor is not None:
            self._finish_inline_comment(self._annotation_editor.toPlainText())

    def delete_selected(self):
        items = list(self.scene.selectedItems())
        for item in items:
            self._delete_item(item)
        if items:
            self._changed()

    def copy_selected(self):
        """Schowek zawiera JSON z własnym MIME, nigdy pickle ani kod."""
        data = encode_selection(self.project, self._sheet, {i.data(1) for i in self.scene.selectedItems()})
        if data is None:
            return False
        mime = QMimeData()
        mime.setData(MIME_TYPE, QByteArray(data))
        QApplication.clipboard().setMimeData(mime)
        return True

    def cut_selected(self):
        # Najpierw udany zapis do schowka; dopiero potem usuwanie.
        if self.copy_selected():
            self.delete_selected()

    def paste_selection(self, *, duplicate=False, target=None):
        if duplicate:
            data = encode_selection(self.project, self._sheet, {i.data(1) for i in self.scene.selectedItems()})
            if data is None:
                return False
        else:
            mime = QApplication.clipboard().mimeData()
            if mime is None or not mime.hasFormat(MIME_TYPE):
                return False  # zwykły tekst nadal wklejamy w edytorach tekstu
            data = bytes(mime.data(MIME_TYPE))
        fragment = decode_selection(data)
        source = fragment.sheets[0]
        positions = [QPointF(c.x, c.y) for c in source.components + source.comments]
        positions += [QPointF(w.start_x, w.start_y) for w in source.wires]
        positions += [QPointF(w.end_x, w.end_y) for w in source.wires]
        if not positions:
            return False
        origin = self._snap(QPointF(min(p.x() for p in positions), min(p.y() for p in positions)))
        serial = 0
        if duplicate:
            deltas = [QPointF(x, y) for x, y in ((20, 20), (-20, -20), (20, -20), (-20, 20))]
        else:
            if target is None:
                local = self.viewport().mapFromGlobal(QCursor.pos())
                if not self.viewport().rect().contains(local):
                    local = self.viewport().rect().center()
                target = self.mapToScene(local)
            target = self._snap(target)
            marker = (data, target.x(), target.y())
            serial = self._paste_serial + 1 if self._last_paste == marker else 0
            deltas = [target - origin + QPointF(20 * serial, 20 * serial)]
        for delta in deltas:
            staged, additions = prepare_paste(self.project, fragment, delta.x(), delta.y())
            if self._fragment_fits(additions, staged):
                break
        else:
            raise ValueError("The selection does not fit here. Move the cursor into the drawing area. / Zaznaczenie nie mieści się tutaj. Przenieś kursor w obszar rysunku.")
        # Cała geometria została sprawdzona przed mutacją projektu/liczników.
        self.project.custom_components = staged.custom_components
        self.project.reference_counters = staged.reference_counters
        for field in ("components", "wires", "comments"):
            getattr(self._sheet, field).extend(getattr(additions, field))
        added_ids = {obj.id for field in ("components", "wires", "comments") for obj in getattr(additions, field)}
        self.load_sheet(self._sheet)
        for item in self.scene.items():
            if item.data(1) in added_ids:
                item.setSelected(True)
        if not duplicate:
            self._last_paste, self._paste_serial = marker, serial
        self._changed()
        return True

    def _fragment_fits(self, fragment, project):
        for component in fragment.components:
            if get_definition(component.library_id, project.custom_components) is None:
                raise ValueError("Unknown component in clipboard / Nieznany element w schowku")
            item = ComponentItem(component, language=getattr(self.settings, "language", "en"),
                                 custom_components=project.custom_components)
            bounds = item.mapRectToParent(item._hit_rect).translated(-item.pos())
            if fit_component_position(self._sheet, bounds, item.pos()) != item.pos():
                return False
        for wire in fragment.wires:
            points = [QPointF(*p) for p in wire.points] if wire.points else self._route_45_degrees(
                QPointF(wire.start_x, wire.start_y), QPointF(wire.end_x, wire.end_y))
            if not route_allowed(self._sheet, points):
                return False
        return all(self.paper_rect().contains(QPointF(c.x, c.y)) for c in fragment.comments)

    def _begin_selection_group(self, origin):
        selected = self.scene.selectedItems()
        self._group_drag = {
            "origin": origin, "delta": QPointF(),
            "ids": {i.data(1) for i in selected},
            "items": [(i, QPointF(i.pos())) for i in selected if i.data(0) in {"component", "comment"}],
            "wires": deepcopy(self._sheet.wires),
        }

    def _move_selection_group(self, delta):
        """Wspólny snap i transakcyjne przesuwanie, także wolnych węzłów.

        Kotwica na niezaznaczonym komponencie zostaje na miejscu. Pozostałe
        końce zaznaczonych kabli oraz wszystkie odnogi ich węzłów podążają
        za grupą. Geometria pochodzi zawsze ze stanu początkowego gestu.
        """
        group = self._group_drag
        if group is None:
            return False
        delta = self._snap(delta)
        ids = group["ids"]
        for item, original in group["items"]:
            destination = original + delta
            if item.data(0) == "component":
                bounds = item.mapRectToParent(item._hit_rect).translated(-item.pos())
                if fit_component_position(self._sheet, bounds, destination) != destination:
                    return False
            elif not self.paper_rect().contains(destination):
                return False
        wires = deepcopy(group["wires"])
        moving_junctions, fixed_junctions = set(), set()
        for wire in wires:
            for side in ("start", "end"):
                comp = getattr(wire, side + "_component_id")
                junction = getattr(wire, side + "_junction_id")
                if junction:
                    if comp and comp not in ids:
                        fixed_junctions.add(junction)
                    elif comp in ids or wire.id in ids:
                        moving_junctions.add(junction)
        moving_junctions -= fixed_junctions
        for wire in wires:
            moved = []
            for side in ("start", "end"):
                comp = getattr(wire, side + "_component_id")
                junction = getattr(wire, side + "_junction_id")
                should_move = (comp in ids or (not comp and (wire.id in ids or junction in moving_junctions)))
                should_move = should_move and junction not in fixed_junctions
                moved.append(bool(should_move))
                if should_move:
                    setattr(wire, side + "_x", getattr(wire, side + "_x") + delta.x())
                    setattr(wire, side + "_y", getattr(wire, side + "_y") + delta.y())
            if all(moved) and wire.points:
                route = [QPointF(x, y) + delta for x, y in wire.points]
            elif any(moved):
                route = self._route_in_drawing_area(self._end_point(wire, "start"), self._end_point(wire, "end"))
            else:
                continue
            if not route or not route_allowed(self._sheet, route):
                return False
            wire.points = [[p.x(), p.y()] for p in route]
        self._refreshing = True
        try:
            for item, original in group["items"]:
                item.setPos(original + delta)
                model = item.component if item.data(0) == "component" else item.annotation
                model.x, model.y = item.x(), item.y()
            live = {w.id: w for w in self._sheet.wires}
            for wire in wires:
                live[wire.id].__dict__.update(wire.__dict__)
        finally:
            self._refreshing = False
        group["delta"] = delta
        self._refresh_attached_wires()
        return True

    def _delete_item(self, item):
        if not self._sheet:
            return
        kind, key = item.data(0), item.data(1)
        if kind == "component":
            for wire, side in self._ends():
                if getattr(wire, side+"_component_id") == key:
                    setattr(wire, side+"_component_id", None)
                    setattr(wire, side+"_pin_index", None)
                    setattr(wire, side+"_pin_number", None)
            self._sheet.components = [c for c in self._sheet.components if c.id != key]
            self._component_items.pop(key, None)
        elif kind == "wire":
            self._sheet.wires = [w for w in self._sheet.wires if w.id != key]
            self._wire_items.pop(key, None)
        elif kind == "comment":
            self._sheet.comments = [c for c in self._sheet.comments if c.id != key]
            self._comment_items.pop(key, None)
        else:
            return
        self.scene.removeItem(item)
        self._selection_changed()

    def _selection_changed(self):
        if self.on_selection and not self._loading:
            item = next((i for i in self.scene.selectedItems() if i.data(0) == "component"), None)
            self.on_selection(item.component if item else None)

    def rotate_selected_components(self):
        changed = False
        for item in self.scene.selectedItems():
            if item.data(0) == "component":
                item.component.rotation = (item.component.rotation + 90) % 360
                item.setRotation(item.component.rotation)
                changed = True
        if changed:
            self._sync_component_positions()
            self._refresh_attached_wires()
            self._attach_free_wire_ends_to_component_pins()
            self._changed()

    def _sync_component_positions(self):
        changed = False
        area = self._sheet
        for item in list(self._component_items.values()) + list(self._comment_items.values()):
            model = item.component if item.data(0) == "component" else item.annotation
            if item.data(0) == "component" and area is not None:
                # Po obrocie 90/270 szerokość i wysokość pola wyboru zamieniają
                # się miejscami. Dzięki temu nie da się wypchnąć symbolu w
                # margines ani do tabliczki rysunkowej.
                bounds = item.mapRectToParent(item._hit_rect).translated(-item.pos())
                snapped = fit_component_position(self._sheet, bounds, item.pos())
                if snapped is not None and snapped != item.pos():
                    item.setPos(snapped)
            if (model.x, model.y) != (item.x(), item.y()):
                model.x, model.y = item.x(), item.y()
                changed = True
        return changed

    def _sync_wire_positions(self):
        return False  # kabli nie przenosi się jako całych obiektów

    def _clear_wire_preview(self):
        if self._wire_preview is not None:
            self.scene.removeItem(self._wire_preview)
        self._wire_start = self._wire_preview = None

    def _begin_inline_comment(self, point, existing=None):
        if self._annotation_editor is not None:
            self._finish_inline_comment(self._annotation_editor.toPlainText())
        editor = InlineAnnotationEditor(existing.text if existing else "", existing.font_size if existing else 12)
        editor.setData(0, "annotation-editor")
        editor.setPos(point)
        self.scene.addItem(editor)
        self._annotation_editor = editor
        self._editing_annotation = existing
        editor.editing_finished.connect(self._finish_inline_comment)
        editor.setFocus(Qt.FocusReason.MouseFocusReason)

    def _title_field_at(self, point):
        if not self._sheet or not title_block_rect(self._sheet).contains(point):
            return None
        block = title_block_rect(self._sheet)
        if QRectF(block.left()+4, block.top()+2, block.width()-8, 36).contains(point):
            return "project"
        if QRectF(block.left()+4, block.top()+40, block.width()*0.65-8, 40).contains(point):
            return "sheet"
        if QRectF(block.left()+4, block.top()+80, block.width()*0.65-8, 40).contains(point):
            return "author"
        return None

    def _begin_title_edit(self, field):
        if self._title_editor is not None:
            self._finish_title_edit(self._title_editor.toPlainText())
        _, rect, _, font, value = title_field_layout(self._sheet, self.project, field,
                                                    getattr(self.settings, "language", "en"))
        editor = InlineAnnotationEditor(value)
        editor.setTextWidth(rect.width())
        editor.setFont(font)
        editor.setDefaultTextColor(QColor("#233a4e"))
        def align_editor():
            editor.setPos(rect.left(), rect.top()+max(0, (rect.height()-editor.document().size().height())/2))
        editor.document().documentLayout().documentSizeChanged.connect(align_editor)
        align_editor()
        editor.title_cell = rect
        editor.setData(0, "title-editor")
        editor.setZValue(100)
        self.scene.addItem(editor)
        self._title_editor, self._title_field = editor, field
        self.viewport().update()
        editor.editing_finished.connect(self._finish_title_edit)
        editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        editor.setTextCursor(cursor)

    def _finish_title_edit(self, text):
        editor, field = self._title_editor, self._title_field
        if editor is None or field is None:
            return
        self._title_editor = self._title_field = None
        value = str(text).strip()[:250]
        self.scene.removeItem(editor)
        if field == "project" and value:
            self.project.name = value
        elif field == "sheet" and value:
            self._sheet.name = value
            index = self.project.sheets.index(self._sheet)
            window = self.window()
            if window is not None and hasattr(window, "tabs"):
                window.tabs.setTabText(index, value)
        elif field == "author":
            self.project.metadata["author"] = value
        else:
            return
        self.viewport().update()
        window = self.window()
        if hasattr(window, "tabs"):
            for index in range(window.tabs.count()):
                window.tabs.widget(index).viewport().update()
        self._changed()

    def _finish_inline_comment(self, text):
        editor = self._annotation_editor
        if editor is None:
            return
        self._annotation_editor = None
        text = str(text).strip()[:20000]
        point = QPointF(editor.x(), editor.y())
        existing = getattr(self, "_editing_annotation", None)
        self.scene.removeItem(editor)
        self._editing_annotation = None
        if existing is not None:
            if text:
                existing.text = text
            else:
                self._sheet.comments = [c for c in self._sheet.comments if c.id != existing.id]
            self._add_comment_item(existing) if text else None
            self._changed()
        elif text:
            comment = Annotation(text, self._snap(point).x(), self._snap(point).y(), font_size=12)
            self._sheet.comments.append(comment)
            self._add_comment_item(comment)
            self._changed()

    def _changed(self):
        self._sync_component_positions()
        if self.on_change and not self._loading:
            self.on_change()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        if 0.08 <= self.transform().m11()*factor <= 8:
            self._auto_fit = False
            self.scale(factor, factor)
        event.accept()
