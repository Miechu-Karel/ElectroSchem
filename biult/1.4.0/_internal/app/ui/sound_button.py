from PySide6.QtWidgets import QPushButton

class SoundButton(QPushButton):
    """Mute is programmatic; a click advances the volume cycle instead."""
    def nextCheckState(self):
        pass
