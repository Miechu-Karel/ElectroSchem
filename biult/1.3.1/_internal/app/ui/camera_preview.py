"""Explicit session consent before any hardware camera is constructed/started."""
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QMessageBox


class CameraPreview(QDialog):
    frame=Signal(QImage)

    def __init__(self,parent=None,language="en"):
        super().__init__(parent); self.pl=language=="pl"
        self.camera=None; self.session=None; self.sink=None; self.devices=[]; self.consent=False
        self.setWindowTitle(self.t("Device camera","Kamera urządzenia")); self.resize(650,480)
        layout=QVBoxLayout(self)
        note=QLabel(self.t("Local live preview only. No microphone, recording, saving or network transfer. Camera starts only after your explicit permission.","Tylko lokalny podgląd na żywo. Bez mikrofonu, nagrywania, zapisu i wysyłania przez sieć. Kamera uruchomi się wyłącznie po Twojej zgodzie.")); note.setWordWrap(True); layout.addWidget(note)
        bar=QHBoxLayout(); self.selector=QComboBox(); bar.addWidget(self.selector,1)
        self.start_button=QPushButton(self.t("Allow and start","Zezwól i uruchom")); self.start_button.clicked.connect(self.request_start); bar.addWidget(self.start_button)
        self.stop_button=QPushButton(self.t("Stop camera","Zatrzymaj kamerę")); self.stop_button.clicked.connect(lambda:self.stop()); bar.addWidget(self.stop_button); layout.addLayout(bar)
        self.preview=QLabel(self.t("Camera is off","Kamera wyłączona")); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.preview,1)
        self.status=QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        # Enumeration is deferred until consent, too; constructing the dialog
        # itself must not touch a capture device.

    def t(self,en,pl): return pl if self.pl else en

    def request_start(self):
        if not self.consent:
            reply=QMessageBox.question(self,self.windowTitle(),self.t("Allow this simulation to use your device camera for a local live preview?","Zezwolić tej symulacji na użycie kamery urządzenia do lokalnego podglądu na żywo?"),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if reply!=QMessageBox.StandardButton.Yes: return
            self.consent=True
        self.start_authorized()

    def start_authorized(self):
        if not self.consent: return
        from PySide6.QtMultimedia import QMediaDevices,QCamera,QMediaCaptureSession,QVideoSink
        self.stop(revoke=False)
        self.devices=QMediaDevices.videoInputs()
        if not self.devices:
            self.status.setText(self.t("No camera is available. Check Windows camera privacy settings.","Brak dostępnej kamery. Sprawdź uprawnienia kamery w ustawieniach prywatności Windows.")); return
        selected=self.selector.currentIndex()
        self.selector.clear()
        for device in self.devices: self.selector.addItem(device.description())
        self.selector.setCurrentIndex(max(0,min(selected,len(self.devices)-1)))
        self.camera=QCamera(self.devices[self.selector.currentIndex()],self)
        self.session=QMediaCaptureSession(self); self.sink=QVideoSink(self)
        self.session.setCamera(self.camera); self.session.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self.receive)
        self.camera.errorOccurred.connect(lambda *args:self.status.setText(self.camera.errorString() if self.camera else ""))
        self.camera.start(); self.status.setText(self.t("Camera active; frames remain in memory.","Kamera aktywna; klatki pozostają tylko w pamięci."))

    def receive(self,video):
        if self.camera is None or not self.consent: return
        image=video.toImage()
        if image.isNull(): return
        image=image.scaled(640,480,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(QPixmap.fromImage(image)); self.frame.emit(image)

    def stop(self,revoke=True):
        if revoke: self.consent=False
        if self.camera is not None: self.camera.stop(); self.camera.deleteLater()
        if self.session is not None: self.session.setCamera(None); self.session.deleteLater()
        if self.sink is not None: self.sink.deleteLater()
        self.camera=self.session=self.sink=None
        self.preview.clear(); self.preview.setText(self.t("Camera is off","Kamera wyłączona"))
        self.frame.emit(QImage())

    def closeEvent(self,event):
        self.stop(); super().closeEvent(event)
