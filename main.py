"""Punkt wejścia desktopowej aplikacji ElectroSchem."""

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    """Uruchamia pojedynczą instancję graficznego edytora."""
    app = QApplication(sys.argv)
    # QSettings zapisuje dane użytkownika w %APPDATA%/ElectroSchem.
    app.setApplicationName("ElectroSchem")
    app.setOrganizationName("ElectroSchem")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
