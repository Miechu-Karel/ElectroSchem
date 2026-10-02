"""Punkt wejścia desktopowej aplikacji ElectroSchem."""

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import APP_VERSION, ICON_DIR, MainWindow
from app.ui.theme import application_icon


WINDOWS_APP_ID = "ElectroSchem.Desktop"


def configure_taskbar_identity() -> bool:
    """Separate ElectroSchem's taskbar group from the Python interpreter."""
    if sys.platform != "win32":
        return False
    import ctypes
    try:
        set_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        return set_id(WINDOWS_APP_ID) == 0
    except (AttributeError, OSError):
        return False


def main() -> int:
    """Uruchamia pojedynczą instancję graficznego edytora."""
    # Windows identity must be set before creating any application windows.
    configure_taskbar_identity()
    app = QApplication(sys.argv)
    # QSettings zapisuje dane użytkownika w %APPDATA%/ElectroSchem.
    app.setApplicationName("ElectroSchem")
    app.setOrganizationName("ElectroSchem")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(application_icon(ICON_DIR))

    window = MainWindow()
    from app.ui.window_mode import show_window
    show_window(window,window.settings)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
