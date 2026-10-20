"""Local visual diagnostics, deliberately separate from electrical validation."""
from math import hypot
from PySide6.QtCore import QPointF
from PySide6.QtGui import QTransform
from app.canvas.component_item import ComponentItem
from app.canvas.routing import overlap_length
from app.libraries.built_in import get_instance_definition


def _intersects_rect(a, b, rect):
    # Liang–Barsky clipping, including diagonals. Degenerate segments are ignored.
    dx, dy = b.x()-a.x(), b.y()-a.y()
    if hypot(dx, dy) < 1e-6: return False
    lo, hi = 0., 1.
    for p, q in ((-dx,a.x()-rect.left()), (dx,rect.right()-a.x()),
                 (-dy,a.y()-rect.top()), (dy,rect.bottom()-a.y())):
        if abs(p) < 1e-9:
            if q < 0: return False
        elif p < 0: lo = max(lo, q/p)
        else: hi = min(hi, q/p)
        if lo > hi: return False
    return True


def review(project, sheet_index=0):
    sheet = project.sheets[sheet_index]
    envelopes, issues = [], []
    for component in sheet.components:
        definition = get_instance_definition(component, project.custom_components)
        rect = ComponentItem.selection_rect(definition, show_name=component.show_name)
        rect = QTransform().rotate(component.rotation).mapRect(rect).translated(component.x,component.y)
        envelopes.append((component,rect))
    def add(code, components=(), wires=()):
        issues.append(dict(code=code, components=list(components), wires=list(wires)))
    for i,(a,ra) in enumerate(envelopes):
        for b,rb in envelopes[i+1:]:
            if ra.intersects(rb): add('overlapping_symbols', (a.reference,b.reference))
            elif ra.adjusted(-40,-40,40,40).intersects(rb): add('crowded_symbols',(a.reference,b.reference))
    segments=[]
    for wire in sheet.wires:
        points=[QPointF(*p) for p in wire.points] or [QPointF(wire.start_x,wire.start_y),QPointF(wire.end_x,wire.end_y)]
        parts=list(zip(points,points[1:])); segments.append((wire,parts))
        length=sum(hypot(b.x()-a.x(),b.y()-a.y()) for a,b in parts)
        direct=hypot(points[-1].x()-points[0].x(),points[-1].y()-points[0].y())
        if len(parts)>5 or (direct>40 and length>2.5*direct): add('detour',wires=(wire.id,))
        for component,rect in envelopes:
            if component.id in (wire.start_component_id,wire.end_component_id): continue
            if any(_intersects_rect(a,b,rect.adjusted(2,2,-2,-2)) for a,b in parts):
                add('wire_through_symbol_or_label',(component.reference,),(wire.id,))
    for i,(wa,sa) in enumerate(segments):
        for wb,sb in segments[i+1:]:
            if any(overlap_length(a,b,c,d)>10.000001 for a,b in sa for c,d in sb):
                add('stacked_wires',wires=(wa.id,wb.id)); continue
            crossing=False
            for a,b in sa:
                for c,d in sb:
                    dx,dy=b.x()-a.x(),b.y()-a.y(); ex,ey=d.x()-c.x(),d.y()-c.y()
                    det=dx*ey-dy*ex
                    if abs(det)<1e-9: continue
                    u=((c.x()-a.x())*ey-(c.y()-a.y())*ex)/det
                    v=((c.x()-a.x())*dy-(c.y()-a.y())*dx)/det
                    if 1e-6<u<1-1e-6 and 1e-6<v<1-1e-6: crossing=True
            if crossing: add('crossing_wires',wires=(wa.id,wb.id))
    return dict(status='warnings' if issues else 'no_detected_issues',issues=issues,
                envelopes=[dict(reference=c.reference, left=r.left(),top=r.top(),right=r.right(),bottom=r.bottom()) for c,r in envelopes],
                scope='Geometry heuristics, not a guarantee of aesthetic quality or electrical validity.')


def describe(issue, language='en'):
    messages={
        'overlapping_symbols':('Overlapping symbols/labels','Nakładające się symbole lub opisy'),
        'crowded_symbols':('Insufficient spacing','Za mały odstęp'),
        'detour':('Long or overly bent wire','Długi lub zbyt pokręcony przewód'),
        'wire_through_symbol_or_label':('Wire crosses a symbol/label','Przewód przechodzi przez symbol lub opis'),
        'stacked_wires':('Stacked wire routes','Nakładające się trasy przewodów'),
        'crossing_wires':('Wire crossing to simplify','Skrzyżowanie przewodów do uproszczenia'),
    }
    label=messages[issue['code']][language=='pl']
    return label+': '+', '.join(issue['components']+issue['wires'])
