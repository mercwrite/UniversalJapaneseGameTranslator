"""Application entry point for the Universal Japanese Game Translator UI.

The main window and supporting widgets are implemented in the `ui` package.
"""

import sys

from PyQt6 import QtWidgets

from ui.controller import ControllerWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()