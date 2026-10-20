"""Thumbnail plus editable enlarged proposal, isolated from the live project."""
from copy import deepcopy
from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView, QGraphicsScene, QLabel, QMessageBox
from PySide6.QtGui import QPixmap


class PreviewView(QGraphicsView):
    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        scale = self.transform().m11()
        if .02 <= scale*factor <= 8: self.scale(factor, factor)
        event.accept()
from app.canvas.schematic_view import SchematicView


class ProposalView(SchematicView):
    """Geometry-only editor: moving a part must not attach or merge new nets."""
    def _merge_wire_overlaps(self,*args,**kwargs): pass
    def _attach_free_wire_ends_to_component_pins(self,*args,**kwargs): pass
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_R,Qt.Key.Key_Escape,Qt.Key.Key_S,Qt.Key.Key_Shift): super().keyPressEvent(event)
        else: event.ignore()
    def mouseDoubleClickEvent(self,event): event.accept()


def connectivity(project,index):
    from app.simulation.netlist import build_netlist
    netlist=build_netlist(project.sheets[index],project.custom_components)
    groups={}
    for pin,node in netlist.pins.items(): groups.setdefault(node,[]).append(pin)
    return sorted(tuple(sorted(pins)) for pins in groups.values())


class AiPreview(QWidget):
    projectEdited=Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.setMinimumHeight(180)
        self.setMaximumHeight(250)
        self.setToolTip("Zoomable preview / Podgląd z powiększaniem")
        self.language = "en"
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.image.isNull():
            self.inspect(self.language); event.accept(); return
        super().mousePressEvent(event)

    def sizeHint(self):
        return QSize(380, 210)

    def set_project(self, project, index, settings):
        self.project=deepcopy(project); self.sheet_index=index; self.settings=settings
        self.language = settings.language
        self.setToolTip("Kliknij, aby powiększyć podgląd" if self.language == "pl" else "Click to inspect and zoom")
        view = SchematicView(project=project, settings=settings, sheet=project.sheets[index])
        try:
            self.image = QImage(2400, 1700, QImage.Format.Format_ARGB32_Premultiplied)
            self.image.fill(Qt.GlobalColor.white)
            painter = QPainter(self.image)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                # W małej karcie powiększamy układ zamiast całej pustej kartki.
                content = list(view._component_items.values()) + list(view._wire_items.values()) + list(view._comment_items.values())
                source = QRectF()
                for item in content: source = source.united(item.sceneBoundingRect())
                if not content:
                    source = view.paper_rect()
                else: source = source.adjusted(-30, -30, 30, 30)
                view.scene.render(painter, QRectF(0, 0, 2400, 1700), source)
            finally:
                painter.end()
        finally:
            view.deleteLater()
        self.update()

    def inspect(self, language="en"):
        if self.image.isNull(): return
        pl = language == "pl"
        dialog = QDialog(self)
        dialog.setWindowTitle("Podgląd propozycji" if pl else "Proposal preview")
        dialog.resize(1200, 850)
        layout = QVBoxLayout(dialog)
        editable=deepcopy(self.project)
        view = ProposalView(dialog,project=editable,settings=self.settings,sheet=editable.sheets[self.sheet_index])
        view._auto_fit=False; view._page_fitted=True
        scene=view.scene
        view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        layout.addWidget(QLabel('Przesuwaj elementy LMB. R: obrót, Ctrl+R: przeciwny. Zmiany zapisujesz tylko do propozycji roboczej.' if pl else
            'Drag parts with LMB. R rotates; Ctrl+R reverses. Changes are saved only to the working proposal.'))
        layout.addWidget(view)
        self.inspection_view=view
        def save():
            view.finish_text_editing(); view._sync_component_positions(); view._refresh_attached_wires()
            if connectivity(editable,self.sheet_index)!=connectivity(self.project,self.sheet_index):
                QMessageBox.warning(dialog,'ElectroSchem', 'Przesunięcie utworzyło nowe zwarcie lub rozłączenie. Rozsuń elementy/przewody przed zapisaniem.' if pl else
                    'The move introduced a short or disconnection. Separate the parts/wires before saving.')
                return
            dialog.accept()
        buttons = QHBoxLayout(); layout.addLayout(buttons)
        for label, callback in (("+", lambda: view.scale(1.25, 1.25)), ("−", lambda: view.scale(.8, .8)),
            ("Dopasuj" if pl else "Fit", lambda: view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)),
            ("Zapisz do propozycji" if pl else "Save to proposal", save),
            ("Anuluj" if pl else "Cancel", dialog.reject)):
            button = QPushButton(label); button.clicked.connect(callback); buttons.addWidget(button)
        dialog.setModal(True)
        self.inspection_dialog = dialog
        QTimer.singleShot(0, lambda: view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio))
        if dialog.exec()==QDialog.DialogCode.Accepted:
            view.finish_text_editing()
            self.projectEdited.emit(editable)
        self.inspection_dialog = None
        self.inspection_view=None
        dialog.deleteLater()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self.image.isNull():
            size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            painter.drawImage(QRectF((self.width()-size.width())/2, (self.height()-size.height())/2,
                                     size.width(), size.height()), self.image)
