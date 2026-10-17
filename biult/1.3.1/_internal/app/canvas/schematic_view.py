"""Płótno edytora: interakcje są oddzielone od symboli i danych dokumentu.

Silne referencje trzymamy dla wszystkich obiektów Qt. Przewody wiążemy z
konkretnym pinem i węzłem, nie z nazwą ani boundingRect komponentu.
"""
from __future__ import annotations
from copy import copy, deepcopy
from dataclasses import replace
from math import ceil, floor
from queue import Empty, Queue
from threading import Lock
from PySide6.QtCore import QByteArray, QMimeData, QLineF, QPointF, QRectF, Qt, QTimer, QRunnable, QThreadPool
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QCursor, QFont, QTransform
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView, QGraphicsRectItem
from app.core.models import Annotation, ComponentInstance, Project, Sheet, Wire, new_id
from app.canvas.component_item import ComponentItem
from app.canvas.annotations import AnnotationItem, InlineAnnotationEditor, edit_annotation
from app.canvas.page import (GRID_STEP, draw_page, page_rect, drawing_rect, title_block_rect,
                             title_field_layout, drawing_contains, fit_component_position, route_allowed)
from app.libraries.built_in import get_definition
from app.services.clipboard import MIME_TYPE, encode_selection, decode_selection, prepare_paste
from app.ui.theme import canvas_colors

PAGE_RECT = QRectF(0, 0, 1188, 840)  # zgodność z dawnymi integracjami; widok używa paper_rect()
ITEM_DATA_KIND, ITEM_DATA_ID = 0, 1
_ACTIVE_WIRE_ROUTE_TASKS = set()
_ACTIVE_WIRE_ROUTE_TASKS_LOCK = Lock()


def _compute_wire_routes(sheet, wire_ids):
    """Route detached wire data; this function is safe to run off the GUI thread."""
    from app.canvas.routing import safe_route

    routing_by_id = {wire.id: wire for wire in sheet.wires}
    moving_ids = set(wire_ids)
    routes = {}
    for wire_id in sorted(moving_ids):
        wire = routing_by_id.get(wire_id)
        if wire is None:
            continue
        junctions = {getattr(wire, side + "_junction_id") for side in ("start", "end")}
        junctions.discard(None)
        related = {other.id for other in sheet.wires
                   if other.id in moving_ids and other.id != wire.id and
                   junctions.intersection(getattr(other, side + "_junction_id")
                                          for side in ("start", "end"))}
        route = safe_route(sheet, QPointF(wire.start_x, wire.start_y),
                           QPointF(wire.end_x, wire.end_y), exclude=(wire.id, *related))
        if route:
            routes[wire.id] = [[point.x(), point.y()] for point in route]
    return routes


class _WireRouteTask(QRunnable):
    def __init__(self, snapshot, source_sheet, generation, wire_ids, result_queue):
        super().__init__()
        self.snapshot = snapshot
        self.source_sheet = source_sheet
        self.generation = generation
        self.wire_ids = set(wire_ids)
        self.result_queue = result_queue

    def run(self):
        routes, error = {}, None
        try:
            routes = _compute_wire_routes(self.snapshot, self.wire_ids)
        except Exception as exc:  # Keep worker failures away from Qt's event loop.
            error = f"{type(exc).__name__}: {exc}"
        self.result_queue.put((self.generation, self.source_sheet,
                               self.wire_ids, routes, error))
        with _ACTIVE_WIRE_ROUTE_TASKS_LOCK:
            _ACTIVE_WIRE_ROUTE_TASKS.discard(self)

class PaperScene(QGraphicsScene):
    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def drawBackground(self, painter, rect):
        settings=replace(self.view.settings,theme="light") if getattr(self.view,"_exporting",False) else self.view.settings
        painter.fillRect(rect, QColor(canvas_colors(settings)["outside"]))
        draw_page(painter, self.view._sheet, self.view.project, settings,
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
        painter.setPen(QPen(QColor(getattr(self,"selected_color","#df6b45") if self.isSelected() else getattr(self,"ink_color","#167d3d")), 2))
        painter.drawPath(self.path())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(getattr(self,"ink_color","#167d3d")))
        for show,point in zip(getattr(self,"endpoint_dots",(True,True)),(self.points[0], self.points[-1])):
            if show: painter.drawEllipse(point, 3, 3)
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
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._component_items, self._wire_items, self._comment_items = {}, {}, {}
        self.tool = "select"
        self._show_hidden_wires=False
        self._wire_start = self._wire_preview = self._dragged_wire_end = None
        self._wire_press_scene = None
        self._wire_press_from_anchor = False
        self._wire_drag_moved = False
        self._annotation_editor = None
        self._title_editor = None
        self._title_field = None
        self._pan_active = False
        self._pan_last = None
        self._rubber_start = None
        self._rubber_item = None
        self._group_drag = None
        self._route_generation = 0
        self._route_pending_ids = set()
        self._route_task_running = False
        self._route_task = None
        self._last_route_error = None
        self._route_result_queue = Queue()
        self._route_poll_timer = QTimer(self)
        self._route_poll_timer.setInterval(20)
        self._route_poll_timer.timeout.connect(self._poll_wire_route_result)
        self._paste_serial = 0
        self._last_paste = None
        self.on_change = self.on_selection = self.on_edit_properties = None
        self.on_routes_updated = None
        self._page_fitted = False
        self._fitting = False
        self._auto_fit = True
        self._refreshing = False
        self._loading = False
        self._fit_scheduled = False
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(80)
        self._fit_timer.timeout.connect(self._run_scheduled_fit)
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
            self._schedule_fit_page()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._auto_fit and not self._fitting:
            self._schedule_fit_page()

    def _schedule_fit_page(self):
        if self._fit_scheduled:
            self._fit_timer.start()
            return
        self._fit_scheduled = True
        self._fit_timer.start()

    def _run_scheduled_fit(self):
        self._fit_scheduled = False
        self.fit_page()

    def fit_page(self):
        from shiboken6 import isValid
        if not isValid(self): return
        if self._fitting:
            return
        window = self.window()
        if window is not None and window.isMinimized():
            return
        # Minimize/restore can temporarily give a child view an empty viewport.
        # Avoid fitting to a zero-sized target and let the next real resize fit.
        if self.viewport().width() <= 0 or self.viewport().height() <= 0:
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
            self._exporting=True
            self._apply_scene_colors(replace(self.settings,theme="light"))
            target = target_rect if target_rect is not None else QRectF(painter.viewport())
            self.scene.render(painter, target, self.paper_rect(), Qt.AspectRatioMode.KeepAspectRatio)
        finally:
            self._exporting=False
            self._apply_scene_colors(self.settings)
            for item in selected:
                item.setSelected(True)
            if self._wire_preview:
                self._wire_preview.show()
            self.scene.blockSignals(False)

    def _apply_scene_colors(self,settings):
        colours=canvas_colors(settings)
        for item in self._component_items.values():
            item.ink_color=colours["ink"]; item.paper_color=colours["paper"]; item.update()
        for item in self._wire_items.values():
            item.ink_color=colours["wire"]; item.selected_color=colours["selected"]; item.update()
        for item in self._comment_items.values(): item.setDefaultTextColor(QColor(colours["ink"]))

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
        # Worker results belong to the previous canvas state and must never
        # overwrite a newly loaded, undone, or switched-to sheet.
        self._route_generation += 1
        self._route_pending_ids.clear()
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
        self.cable_layer=None
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
        # Older documents and newly drawn branches can have a free endpoint
        # touching the interior of another path. Canonicalize those T/Y joins
        # before history is recorded; otherwise redo would mutate the drawing
        # again every time the canvas is rebuilt.
        self._normalize_wire_junctions()
        for comment in sheet.comments:
            self._add_comment_item(comment)
        self._join_coincident_ends()
        self._refresh_attached_wires()
        self.scene.blockSignals(False)
        self._loading = False
        from app.ui.usb_cable import EditorCables
        self.cable_layer=EditorCables(self)
        self.viewport().update()

    def _add_component_item(self, component):
        item = ComponentItem(component, language=getattr(self.settings, "language", "en"),
                             standard=getattr(self._sheet, "standard", getattr(self.settings, "standard", "EN")),
                             custom_components=self.project.custom_components if self.project else None)
        item.on_position_changed = self._refresh_attached_wires
        colours=canvas_colors(self.settings)
        item.ink_color=colours["ink"]; item.paper_color=colours["paper"]
        self._component_items[component.id] = item
        self.scene.addItem(item)

    def refresh_component(self, component_id):
        item = self._component_items.get(component_id)
        if item:
            from app.libraries.built_in import get_instance_definition
            definition=get_instance_definition(item.component,self.project.custom_components if self.project else None)
            if definition==item.definition:
                # Ordinary value/name edits must retain the original hit area.
                item.update_labels()
            else:
                # Pin count/geometry can depend on properties (multi-position switch).
                selected=item.isSelected(); component=item.component
                numbers={pin.number for pin in definition.pins} if definition else set()
                for wire,side in self._ends():
                    if getattr(wire,side+'_component_id')!=component_id: continue
                    index=getattr(wire,side+'_pin_index')
                    number=getattr(wire,side+'_pin_number')
                    if number is None and index is not None and 0<=index<len(item.definition.pins):
                        number=item.definition.pins[index].number
                    if str(number) not in numbers:
                        # A removed switch throw becomes a free cable end;
                        # keep the cable, never leave an invalid pin anchor.
                        for key in ('component_id','pin_index','pin_number'):
                            setattr(wire,side+'_'+key,None)
                self.scene.removeItem(item)
                self._add_component_item(component)
                self._component_items[component_id].setSelected(selected)
            if getattr(self,'cable_layer',None): self.cable_layer.refresh(component_id)
            self._refresh_attached_wires()
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
        from app.core.component_defaults import apply_defaults, nominal_value
        nominal,unit=nominal_value(definition)
        preview_component=ComponentInstance(library_id,0,0,value=nominal,unit=unit)
        apply_defaults(preview_component,self.settings)
        preview = ComponentItem(preview_component,
                                language=getattr(self.settings, "language", "en"),
                                custom_components=self.project.custom_components if self.project else None)
        point = fit_component_position(self._sheet, preview._hit_rect, point)
        if point is None:
            raise ValueError("Component does not fit this sheet; choose a larger paper size. / Element nie mieści się na arkuszu; wybierz większy format.")
        project = self.project or Project(sheets=[self._sheet])
        from app.core.editor_operations import add_component
        component = add_component(project, self._sheet, library_id, point.x(), point.y(), self.settings)
        self._add_component_item(component)
        from app.ui.usb_cable import CABLE_IDS,UsbCable
        if component.library_id in CABLE_IDS and hasattr(self,'cable_layer'):
            self._component_items[component.id].hide(); self.cable_layer.usb_cables.append(UsbCable(self.cable_layer,component))
        self._attach_free_wire_ends_to_component_pins()
        self.scene.clearSelection()
        if component.library_id in CABLE_IDS and getattr(self,'cable_layer',None):
            next(c for c in self.cable_layer.usb_cables if c.component.id==component.id).path.setSelected(True)
        else: self._component_items[component.id].setSelected(True)
        self._changed()
        return component

    def _add_wire_item(self, wire):
        points = [QPointF(*p) for p in wire.points] if wire.points else self._route_45_degrees(QPointF(wire.start_x, wire.start_y), QPointF(wire.end_x, wire.end_y))
        item = WireItem(points)
        colours=canvas_colors(self.settings)
        item.ink_color=colours["wire"]; item.selected_color=colours["selected"]
        item.setData(0, "wire")
        item.setData(1, wire.id)
        self._wire_items[wire.id] = item
        self.scene.addItem(item)

    def _add_comment_item(self, comment):
        item = AnnotationItem(comment)
        item.setDefaultTextColor(QColor(canvas_colors(self.settings)["ink"]))
        self._comment_items[comment.id] = item
        self.scene.addItem(item)

    def _wire_path(self, points):
        path = QPainterPath(points[0])
        for p in points[1:]:
            path.lineTo(p)
        return path

    @staticmethod
    def _route_45_degrees(start, end):
        from app.canvas.routing import diagonal_route
        return diagonal_route(start,end)

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

    def _wire_pin_candidates(self):
        from app.simulation.jumper import CABLE_IDS
        targets=[]
        for item in self._component_items.values():
            if item.definition.symbol=='breadboard': continue
            if item.component.library_id in CABLE_IDS or item.definition.name in {'Kostka zasilająca USB','Klawiatura USB'}: continue
            for index,pin in enumerate(item.pin_positions()):
                if item.definition.symbol=='goldpin' and index==0: continue
                targets.append((pin,item.component.id,index))
        return targets

    def _snap_to_pin(self, point, exclude_wire=None):
        # Promień mniejszy od połowy odstępu pinów: sąsiedni pin nie zostanie
        # przypadkowo przejęty. Nie przyciągamy końca do jego poprzedniej pozycji.
        targets = self._wire_pin_candidates()
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
                        end_pin_number=wire.end_pin_number, end_junction_id=wire.end_junction_id,group_id=wire.group_id)
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

    def _normalize_wire_junctions(self):
        """Split paths at free endpoints that touch their interiors.

        Work from a snapshot of endpoint coordinates: splitting adds only
        endpoints at the junction already being processed, so a second pass
        is unnecessary. Plain segment crossings remain unconnected.
        """
        ends={(self._end_point(w,side).x(),self._end_point(w,side).y())
              for w in self._sheet.wires for side in ("start","end")
              if not getattr(w,side+"_component_id")}
        for x,y in ends:
            self._split_wires_at_point(QPointF(x,y))

    def _merge_wire_overlaps(self, seeds):
        from app.core.wire_topology import merge_overlaps
        if not merge_overlaps(self._sheet, seeds):
            return False
        for item in self._wire_items.values():
            self.scene.removeItem(item)
        self._wire_items.clear()
        for wire in self._sheet.wires:
            self._add_wire_item(wire)
        self._join_coincident_ends()
        self._refresh_attached_wires()
        return True

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
        for wire in self._sheet.wires:
            item=self._wire_items.get(wire.id)
            if item:
                flags=[]
                for side in ("start","end"):
                    point=self._end_point(wire,side); ends=groups.get((round(point.x(),4),round(point.y(),4)),[])
                    directions=[]
                    for w,s in ends:
                        vertices=w.points or [[w.start_x,w.start_y],[w.end_x,w.end_y]]
                        # Malformed/legacy zero-length wires can contain only
                        # one vertex. They have no outgoing direction, but must
                        # not abort a mouse-release handler for the whole sheet.
                        if len(vertices)<2:
                            continue
                        neighbour=QPointF(*(vertices[1] if s=="start" else vertices[-2]))
                        delta=neighbour-point
                        if delta.manhattanLength()>.001:
                            length=(delta.x()**2+delta.y()**2)**.5
                            unit=(round(delta.x()/length,5),round(delta.y()/length,5))
                            if unit not in directions: directions.append(unit)
                    # Show branch nodes and genuinely floating wire ends.
                    # A shared two-direction bend or a component-pin endpoint
                    # is connected already and therefore needs no endpoint dot.
                    floating_end = len(ends)==1 and not getattr(wire,side+"_component_id")
                    flags.append(len(directions)>=3 or floating_end)
                item.endpoint_dots=tuple(flags); item.update()

    def _routes_after_movement(self, wires, wire_ids):
        """Return the shortest legal routes for moved wires against the new layout."""
        if not wire_ids:
            return {}
        routing_sheet = copy(self._sheet)
        routing_sheet.wires = deepcopy(wires)
        # During a drag, always route against the geometry captured at press
        # time, not the previous mouse frame's just-rerouted paths. This keeps
        # junction branches from chasing each other and leaving tiny elbows.
        gesture_points = getattr(self, "_wire_gesture_points", {})
        for candidate in routing_sheet.wires:
            original = gesture_points.get(candidate.id)
            if original:
                candidate.points = deepcopy(original)
        return {wire_id: [QPointF(*point) for point in route]
                for wire_id, route in _compute_wire_routes(routing_sheet, wire_ids).items()}

    @staticmethod
    def _routing_snapshot(sheet):
        """Copy only the immutable page geometry and wires needed by the router."""
        snapshot = copy(sheet)
        snapshot.components = []
        snapshot.comments = []
        snapshot.wires = []
        for wire in sheet.wires:
            detached = copy(wire)
            detached.points = [list(point) for point in wire.points]
            snapshot.wires.append(detached)
        return snapshot

    def _schedule_wire_routes(self, wire_ids):
        if not self._sheet or not wire_ids:
            return
        present = {wire.id for wire in self._sheet.wires}
        self._route_pending_ids.update(set(wire_ids) & present)
        self._start_wire_route_task()

    def _start_wire_route_task(self):
        if self._route_task_running or not self._route_pending_ids or not self._sheet:
            return
        source_sheet = self._sheet
        wire_ids = set(self._route_pending_ids)
        self._route_pending_ids.clear()
        task = _WireRouteTask(self._routing_snapshot(source_sheet), source_sheet,
                              self._route_generation, wire_ids, self._route_result_queue)
        self._route_task_running = True
        self._route_task = task
        with _ACTIVE_WIRE_ROUTE_TASKS_LOCK:
            _ACTIVE_WIRE_ROUTE_TASKS.add(task)
        QThreadPool.globalInstance().start(task)
        if not self._route_poll_timer.isActive():
            self._route_poll_timer.start()

    def _poll_wire_route_result(self):
        try:
            result = self._route_result_queue.get_nowait()
        except Empty:
            return
        self._wire_routes_ready(result)

    def _wire_routes_ready(self, result):
        generation, source_sheet, requested_ids, routes, error = result
        self._route_task_running = False
        self._route_task = None
        self._last_route_error = error
        if self._sheet is source_sheet and generation == self._route_generation and not error:
            live = {wire.id: wire for wire in self._sheet.wires}
            applied = False
            for wire_id, points in routes.items():
                wire = live.get(wire_id)
                if wire is None or len(points) < 2:
                    continue
                # A generation check is the primary guard; endpoint checks are
                # a final safeguard if an external caller edited the model.
                if (QPointF(*points[0]) != self._end_point(wire, "start") or
                        QPointF(*points[-1]) != self._end_point(wire, "end")):
                    continue
                wire.points = [list(point) for point in points]
                item = self._wire_items.get(wire_id)
                if item:
                    item.set_points([QPointF(*point) for point in points])
                applied = True
            if applied and self.on_routes_updated:
                self.on_routes_updated()
        elif self._sheet is source_sheet and not error:
            # A newer edit happened while the worker was routing. Re-run its
            # requested wires against the latest model rather than applying a
            # stale path or silently leaving a provisional path behind.
            self._route_pending_ids.update(requested_ids)
        if self._route_pending_ids:
            self._start_wire_route_task()
        else:
            self._route_poll_timer.stop()

    def _refresh_attached_wires(self, force_reroute=False, defer_routing=False):
        if not self._sheet or self._refreshing:
            return set()
        self._refreshing = True
        try:
            if getattr(self,'cable_layer',None): self.cable_layer.follow_targets()
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
            forced_ids = (set(wire.id for wire in self._sheet.wires) if force_reroute is True
                          else set(force_reroute or ()))
            reroute_ids = set(forced_ids)
            baselines = {}
            for wire in self._sheet.wires:
                start, end = self._end_point(wire, "start"), self._end_point(wire, "end")
                baseline = getattr(self, "_wire_gesture_points", {}).get(wire.id, wire.points)
                baselines[wire.id] = baseline
                endpoints_unchanged = (len(baseline) >= 2 and
                                       QPointF(*baseline[0]) == start and QPointF(*baseline[-1]) == end)
                if not endpoints_unchanged or not baseline:
                    reroute_ids.add(wire.id)

            shortest_routes = ({} if defer_routing else
                               self._routes_after_movement(self._sheet.wires, reroute_ids))
            from app.canvas.wire_geometry import stretch, compact_route
            for wire in self._sheet.wires:
                start, end = self._end_point(wire, "start"), self._end_point(wire, "end")
                baseline = baselines[wire.id]
                if wire.id not in reroute_ids:
                    route = compact_route([QPointF(*point) for point in baseline])
                else:
                    route = shortest_routes.get(wire.id)
                if wire.id in reroute_ids and route is None:
                    # If overlap constraints make a legal shortest route impossible,
                    # keep the existing cable connected and within the drawing area.
                    route = stretch(baseline, start, end)
                    if not route_allowed(self._sheet, route):
                        route = self._route_in_drawing_area(start, end) or self._route_45_degrees(start, end)
                else:
                    route = compact_route(route)
                wire.points = [[p.x(), p.y()] for p in route]
                item = self._wire_items.get(wire.id)
                if item and item.points != route:
                    item.set_points(route)
            return reroute_ids
        finally:
            self._refreshing = False

    def _attach_end_if_near_pin(self, wire, is_start):
        side = "start" if is_start else "end"
        point = self._end_point(wire, side)
        candidates = self._wire_pin_candidates()
        if candidates:
            pin, comp, index = min(candidates, key=lambda t: QLineF(point, t[0]).length())
            if QLineF(point, pin).length() <= 6:
                setattr(wire, side+"_component_id", comp)
                setattr(wire, side+"_pin_index", index)
                setattr(wire, side+"_x", pin.x())
                setattr(wire, side+"_y", pin.y())

    def _attach_free_wire_ends_to_component_pins(self,join=True,refresh=True):
        attached = set()
        for wire, side in self._ends():
            if getattr(wire, side+"_component_id") is None:
                old_component = getattr(wire, side + "_component_id")
                self._attach_end_if_near_pin(wire, side == "start")
                if getattr(wire, side + "_component_id") != old_component:
                    attached.add(wire.id)
        if join: self._join_coincident_ends()
        if refresh:
            attached.update(self._refresh_attached_wires())
        return attached

    def _nearest_wire_endpoint(self, point):
        candidates = [(self._end_point(w, s), w.id, s == "start") for w, s in self._ends()]
        if not candidates:
            return None
        nearest = min(candidates, key=lambda t: QLineF(point, t[0]).length())
        return (nearest[1], nearest[2]) if QLineF(point, nearest[0]).length() <= 6 else None

    def _move_wire_endpoint(self, wire_id, is_start, point, component_id, pin_index):
        if any(QLineF(point,p).length()<8 for p,_,_,_ in self._jumper_contacts()): return
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

    def _jumper_contacts(self):
        for cid,item in self._component_items.items():
            d=item.definition
            if d.symbol=='goldpin':
                yield item.pin_positions()[0],cid,0,'female' if d.name=='Goldpin żeński' else 'male'
            elif d.symbol=='breadboard':
                for i,p in enumerate(item.pin_positions()): yield p,cid,i,'female'

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
                if isinstance(item,ComponentItem):
                    self._wire_gesture_points={w.id:deepcopy(w.points) for w in self._sheet.wires}
                if item and hasattr(item,'cable'):
                    super().mousePressEvent(event); return
                if item:
                    obj=item.component if item.data(0)=="component" else next((o for o in self._sheet.wires+self._sheet.comments if o.id==item.data(1)),None)
                    group=obj.properties.get("asset_group") if isinstance(obj,ComponentInstance) else getattr(obj,"group_id",None)
                    if group and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        ids={c.id for c in self._sheet.components if c.properties.get("asset_group")==group}
                        ids.update(o.id for o in self._sheet.wires+self._sheet.comments if o.group_id==group)
                        self.scene.clearSelection()
                        for candidate in self.scene.items():
                            if candidate.data(1) in ids: candidate.setSelected(True)
                        self._begin_selection_group(point); self._group_drag["asset"]=True
                        event.accept(); return
                    if group and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.scene.clearSelection()
                        item.setSelected(True)
                # Grupę przesuwamy jednym wektorem, zanim Qt rozpocznie
                # przeciąganie pojedynczego symbolu albo końcówki kabla.
                if item and item.isSelected() and len(self.scene.selectedItems()) > 1:
                    self._begin_selection_group(point)
                    event.accept()
                    return
                endpoint = self._nearest_wire_endpoint(point)
                if endpoint:
                    self._wire_gesture_points={w.id:deepcopy(w.points) for w in self._sheet.wires}
                    self._dragged_wire_end = endpoint
                    event.accept()
                    return
            if self.tool == "wire" and drawing_contains(self._sheet, point):
                if any(QLineF(point,p).length()<8 for p,_,_,_ in self._jumper_contacts()):
                    self.setToolTip('Dodaj kabel z kategorii Kable i przesuń jego końcówkę na złącze.' if self.settings and self.settings.language=='pl' else 'Add a cable from Cables and drag its plug onto the connector.')
                    event.accept(); return
                snapped = self._snap_to_pin(point)
                if not drawing_contains(self._sheet, snapped[0]):
                    event.accept()
                    return
                if self._wire_start is None:
                    self._start_wire_preview(snapped)
                # Defer completion until release. This gives click-click and
                # drag-to-draw a single, unambiguous commit point and prevents
                # Qt's default scene release handling from reusing the old start.
                self._wire_press_scene = QPointF(snapped[0])
                self._wire_press_from_anchor = snapped[0] == self._wire_start[0]
                self._wire_drag_moved = False
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
        if self.tool == "wire" and event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            if drawing_contains(self._sheet, point):
                snapped = self._snap_to_pin(point)
                self._wire_press_scene = QPointF(snapped[0])
                self._wire_press_from_anchor = snapped[0] == (self._wire_start[0] if self._wire_start else snapped[0])
                self._wire_drag_moved = False
            event.accept()
            return
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
            cursor=self.mapToScene(event.position().toPoint())
            if self._wire_press_scene is not None and QLineF(cursor,self._wire_press_scene).length() >= 4:
                self._wire_drag_moved=True
            end, _, _ = self._snap_to_pin(cursor)
            from app.canvas.routing import preview_route
            route = preview_route(self._sheet,self._wire_start[0],end)
            self._wire_preview.setPath(self._wire_path(route))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.tool == "wire" and event.button() == Qt.MouseButton.LeftButton:
            if self._wire_press_scene is not None and self._wire_start:
                dragged = self._wire_drag_moved
                from_anchor = self._wire_press_from_anchor
                self._wire_press_scene = None
                self._wire_press_from_anchor = False
                self._wire_drag_moved = False
                if dragged or not from_anchor:
                    point = self.mapToScene(event.position().toPoint())
                    if drawing_contains(self._sheet, point):
                        self._complete_wire_at(self._snap_to_pin(point))
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._group_drag is not None:
            group = self._group_drag
            moved = group["delta"] != QPointF()
            released_asset=bool(group.get("asset"))
            origin = group["origin"]
            moved_ids = group["ids"]
            deferred_routes = bool(group.get("defer_routing"))
            moved_wire_ids = set(group.get("moved_wire_ids", ()))
            self._group_drag = None
            self._wire_gesture_points={}
            if moved:
                # Moving geometry is not an instruction to join unrelated nets.
                if deferred_routes:
                    changed_wire_ids = self._attach_free_wire_ends_to_component_pins(
                        join=False, refresh=False)
                    changed_wire_ids.update(self._refresh_attached_wires(defer_routing=True))
                else:
                    changed_wire_ids = self._attach_free_wire_ends_to_component_pins(join=False)
                self._changed()
                if deferred_routes:
                    self._schedule_wire_routes(moved_wire_ids | changed_wire_ids)
            elif not event.modifiers() and not released_asset:
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
                self._merge_wire_overlaps({wire.id})
                self._split_wires_at_point(self._end_point(wire, "start" if start else "end"), wire.id)
            self._dragged_wire_end = None
            self._join_coincident_ends()
            self._refresh_attached_wires()
            self._changed()
            self._wire_gesture_points={}
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if self._sync_component_positions():
            self._attach_free_wire_ends_to_component_pins(join=False)
            self._changed()
        self._wire_gesture_points={}

    def keyPressEvent(self, event):
        # QGraphicsTextItem nie jest QWidget: litery R/S/D i Delete muszą
        # trafić do jego kursora tekstowego, nie do narzędzi schematu.
        if self.is_editing_text():
            super().keyPressEvent(event)
            return
        if event.key()==Qt.Key.Key_S and event.modifiers()==Qt.KeyboardModifier.ShiftModifier:
            self._show_hidden_wires=True; self.viewport().update(); event.accept(); return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            return
        if event.key() == Qt.Key.Key_R and event.modifiers() in {Qt.KeyboardModifier.NoModifier,Qt.KeyboardModifier.ControlModifier}:
            self.rotate_selected_components(opposite=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            return
        if event.key() == Qt.Key.Key_Escape:
            if self._group_drag is not None:
                self._move_selection_group(QPointF())
                self._group_drag = None
            self._wire_gesture_points={}
            self._clear_wire_preview()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key() in (Qt.Key.Key_S,Qt.Key.Key_Shift) and not event.isAutoRepeat():
            self._show_hidden_wires=False; self.viewport().update()
        super().keyReleaseEvent(event)

    def focusOutEvent(self,event):
        self._wire_gesture_points={}
        # A minimize/alt-tab can steal focus mid-gesture. Keep the current
        # free endpoint, but discard the stale press so restore cannot commit
        # a phantom segment from an earlier mouse-down.
        self._wire_press_scene=None
        self._wire_press_from_anchor=False
        self._wire_drag_moved=False
        self._show_hidden_wires=False; self.viewport().update(); super().focusOutEvent(event)

    def drawForeground(self,painter,rect):
        if not (self._show_hidden_wires or getattr(self.settings,'wires_through_cases',False)): return
        from app.canvas.wire_peek import draw
        draw(painter,self._component_items.values(),self._wire_items.values(),canvas_colors(self.settings)['wire'])

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
        bodies={i.data(1):self._component_items[i.data(1)] for i in selected if i.data(0)=='component' and i.data(1) in self._component_items}
        selected=list(bodies.values())+[i for i in selected if i.data(0)!='component']
        self._group_drag = {
            "origin": origin, "delta": QPointF(),
            "ids": {i.data(1) for i in selected},
            "items": [(i, QPointF(i.pos())) for i in selected if i.data(0) in {"component", "comment"}],
            "wires": deepcopy(self._sheet.wires),
            "moved_wire_ids": set(),
            "defer_routing": False,
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
        # The gesture snapshot is immutable. A shallow copy of each dataclass
        # is enough here because every changed waypoint list is replaced, never
        # mutated in place; avoid recursively copying all routes per mouse event.
        wires = [copy(wire) for wire in group["wires"]]
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
        moved_wire_ids = set()
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
                from app.canvas.wire_geometry import stretch
                route = stretch(wire.points,self._end_point(wire,"start"),self._end_point(wire,"end"))
            else:
                continue
            if not route:
                return False
            wire.points = [[p.x(), p.y()] for p in route]
            moved_wire_ids.add(wire.id)
        group["moved_wire_ids"].update(moved_wire_ids)
        defer_routing = (group["defer_routing"] or len(ids) >= 8 or
                         len(moved_wire_ids) >= 4 or len(moved_wire_ids) * len(wires) >= 64)
        group["defer_routing"] = defer_routing
        shortest_routes = {} if defer_routing else self._routes_after_movement(wires, moved_wire_ids)
        if not defer_routing and moved_wire_ids - shortest_routes.keys():
            return False
        for wire in wires:
            if wire.id in shortest_routes:
                wire.points = [[p.x(), p.y()] for p in shortest_routes[wire.id]]
            elif defer_routing and wire.id in moved_wire_ids:
                route = [QPointF(*point) for point in wire.points]
                if not route_allowed(self._sheet, route):
                    route = self._route_in_drawing_area(
                        self._end_point(wire, "start"), self._end_point(wire, "end"))
                    if not route:
                        return False
                    wire.points = [[point.x(), point.y()] for point in route]
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
        self._refresh_attached_wires(defer_routing=defer_routing)
        return True

    def _delete_item(self, item):
        if not self._sheet:
            return
        kind, key = item.data(0), item.data(1)
        if kind == "component":
            if not any(c.id==key for c in self._sheet.components): return
            from app.core.editor_operations import remove_component
            remove_component(self._sheet, key)
            body=self._component_items.pop(key, None)
            if body and body is not item: self.scene.removeItem(body)
            layer=getattr(self,'cable_layer',None)
            if layer:
                for cable in list(layer.usb_cables):
                    if cable.component.id==key:
                        for visual in [cable.path,*cable.plugs]:
                            if visual is not item: self.scene.removeItem(visual)
                        layer.usb_cables.remove(cable)
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

    def rotate_selected_components(self,opposite=False):
        sign=-1 if getattr(self.settings,'rotation_direction','cw')=='ccw' else 1
        if opposite: sign=-sign
        selected={i.component.id for i in self.scene.selectedItems() if i.data(0)=="component"}
        handled=set()
        blocked=set()
        groups={c.properties.get("asset_group") for c in self._sheet.components if c.id in selected}-{None,""}
        for group in groups:
            members=[c for c in self._sheet.components if c.properties.get("asset_group")==group]
            if len(members)<2 or not all(c.id in selected for c in members): continue
            wires=[w for w in self._sheet.wires if w.group_id==group]
            comments=[c for c in self._sheet.comments if c.group_id==group]
            points=[(c.x,c.y) for c in members+comments]
            points += [tuple(p) for w in wires for p in (w.points or [[w.start_x,w.start_y],[w.end_x,w.end_y]])]
            cx=round((min(x for x,y in points)+max(x for x,y in points))/40)*20
            cy=round((min(y for x,y in points)+max(y for x,y in points))/40)*20
            def rotate(x,y): return cx-sign*(y-cy),cy+sign*(x-cx)
            proposed=[(c,*rotate(c.x,c.y),(c.rotation+90*sign)%360) for c in members]
            if any(not drawing_contains(self._sheet,QTransform().rotate(angle).mapRect(self._component_items[c.id]._hit_rect).translated(x,y)) for c,x,y,angle in proposed):
                blocked.update(c.id for c in members)
                continue  # Reject the whole rotation at a sheet edge; never distort the asset.
            self._refreshing=True
            try:
                for c,x,y,angle in proposed:
                    c.x,c.y,c.rotation=x,y,angle
                    item=self._component_items[c.id]; item.setPos(x,y); item.setRotation(angle)
                for w in wires:
                    w.start_x,w.start_y=rotate(w.start_x,w.start_y)
                    w.end_x,w.end_y=rotate(w.end_x,w.end_y)
                    w.points=[list(rotate(*p)) for p in w.points]
                for c in comments:
                    c.x,c.y=rotate(c.x,c.y)
                    self._comment_items[c.id].setPos(c.x,c.y)
            finally: self._refreshing=False
            handled.update(c.id for c in members)
        changed = bool(handled)
        for item in {i.data(1):self._component_items[i.data(1)] for i in self.scene.selectedItems() if i.data(0)=='component' and i.data(1) in self._component_items}.values():
            if item.component.id not in handled|blocked:
                from app.core.editor_operations import set_rotation
                set_rotation(item.component, item.component.rotation + 90*sign)
                item.setRotation(item.component.rotation)
                changed = True
        if changed:
            self._sync_component_positions()
            self._refresh_attached_wires()
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
                from app.core.editor_operations import set_position
                set_position(model, item.x(), item.y())
                changed = True
        return changed

    def _sync_wire_positions(self):
        return False  # kabli nie przenosi się jako całych obiektów

    def _start_wire_preview(self, snapped):
        self._clear_wire_preview()
        self._wire_start = (QPointF(snapped[0]),snapped[1],snapped[2])
        self._wire_press_scene=None; self._wire_press_from_anchor=False; self._wire_drag_moved=False
        self._wire_preview = QGraphicsPathItem(self._wire_path([self._wire_start[0], self._wire_start[0]]))
        self._wire_preview.setPen(QPen(QColor("#e76f51"), 2, Qt.PenStyle.DashLine))
        self.scene.addItem(self._wire_preview)

    def _complete_wire_at(self,snapped):
        if self._wire_start is None:
            return False
        start,comp,pin=self._wire_start
        end,end_comp,end_pin=snapped
        if start==end:
            if end_comp is not None:
                self._clear_wire_preview()
            return False
        from app.canvas.routing import editor_route
        route=editor_route(self._sheet,start,end)
        if route is None:
            return False
        wire=Wire(start.x(),start.y(),end.x(),end.y(),start_component_id=comp,
                  start_pin_index=pin,end_component_id=end_comp,end_pin_index=end_pin)
        wire.points=[[point.x(),point.y()] for point in route]
        self._sheet.wires.append(wire)
        self._add_wire_item(wire)
        # Commit means this drawing gesture is over. Clear its anchor before
        # topology cleanup so even a malformed neighbouring wire cannot leave
        # the old start point active if cleanup encounters bad legacy data.
        self._clear_wire_preview()
        self._merge_wire_overlaps({wire.id})
        self._normalize_wire_junctions()
        self._join_coincident_ends()
        self._refresh_attached_wires()
        self._changed()
        return True

    def _clear_wire_preview(self):
        if self._wire_preview is not None:
            self.scene.removeItem(self._wire_preview)
        self._wire_start = self._wire_preview = None
        self._wire_press_scene = None
        self._wire_press_from_anchor = False
        self._wire_drag_moved = False

    def _begin_inline_comment(self, point, existing=None):
        if self._annotation_editor is not None:
            self._finish_inline_comment(self._annotation_editor.toPlainText())
        editor = InlineAnnotationEditor(existing.text if existing else "", existing.font_size if existing else 12)
        editor.setDefaultTextColor(QColor(canvas_colors(self.settings)["ink"]))
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
        editor.setDefaultTextColor(QColor(canvas_colors(self.settings)["ink"]))
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
        # Any model edit invalidates results computed against the previous
        # layout. Stale queued routes are retried against the current snapshot.
        self._route_generation += 1
        if self.on_change and not self._loading:
            self.on_change()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        if 0.08 <= self.transform().m11()*factor <= 8:
            self._auto_fit = False
            self.scale(factor, factor)
        event.accept()
