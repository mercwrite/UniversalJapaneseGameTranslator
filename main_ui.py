"""Application entry point for the Universal Japanese Game Translator UI.

The main window and supporting widgets are implemented in the `ui` package.
"""

import sys
import traceback
import faulthandler
from PyQt6 import QtWidgets

# Enable faulthandler for debugging segfaults
faulthandler.enable()

from ui.controller import ControllerWindow
from error_handler import logger


def main() -> None:
    """Main entry point with error handling."""
    try:
        app = QtWidgets.QApplication(sys.argv)
        
        # Set up global exception handler for uncaught exceptions
        def exception_handler(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            logger.critical(
                "Uncaught exception",
                exc_info=(exc_type, exc_value, exc_traceback)
            )
            
            # Show user-friendly error message
            error_msg = QtWidgets.QMessageBox()
            error_msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            error_msg.setWindowTitle("Application Error")
            error_msg.setText("An unexpected error occurred. The application will continue running.")
            error_msg.setDetailedText("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            error_msg.exec()
        
        sys.excepthook = exception_handler
        
        window = ControllerWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Failed to start application: {e}", exc_info=True)
        # Try to show error dialog
        try:
            app = QtWidgets.QApplication(sys.argv)
            error_msg = QtWidgets.QMessageBox()
            error_msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            error_msg.setWindowTitle("Startup Error")
            error_msg.setText(f"Failed to start application: {str(e)}")
            error_msg.exec()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":  
    main()