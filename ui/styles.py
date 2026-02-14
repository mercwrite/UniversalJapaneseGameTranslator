"""Dark theme stylesheet for the controller window."""

from PyQt6 import QtWidgets

DARK_THEME_STYLESHEET = """
    /* Main window - transparent for overlay */
    QWidget#ControllerWindow {
        background-color: transparent;
        border: none;
    }

    /* Base widget styling */
    QWidget {
        font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
        font-size: 10pt;
        color: #EEEEEE;
    }

    /* Overlay List Container - modern dark container */
    QWidget#OverlayListContainer {
        background-color: #1A1A1A;
        border: 1px solid #404040;
        border-radius: 8px;
    }

    /* Scroll area styling */
    QScrollArea {
        border: none;
        background-color: transparent;
    }

    QScrollBar:vertical {
        background-color: #1A1A1A;
        width: 10px;
        border: none;
        border-radius: 5px;
    }

    QScrollBar::handle:vertical {
        background-color: #404040;
        border-radius: 5px;
        min-height: 30px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #505050;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    /* Buttons */
    QPushButton {
        background-color: #2A2A2A;
        color: #EEEEEE;
        border: 1px solid #505050;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 400;
        min-height: 36px;
    }

    QPushButton:hover {
        background-color: #353535;
        border-color: #606060;
    }

    QPushButton:pressed {
        background-color: #404040;
    }

    /* ComboBox styling */
    QComboBox {
        border: 1px solid #505050;
        border-radius: 8px;
        padding: 10px 40px 10px 16px;
        background-color: #2A2A2A;
        color: #EEEEEE;
        min-height: 36px;
        font-size: 12px;
    }

    QComboBox:hover {
        border-color: #606060;
        background-color: #303030;
    }

    QComboBox:focus {
        border-color: #707070;
    }

    QComboBox::drop-down {
        border: none;
        width: 40px;
        background-color: transparent;
    }

    QComboBox::down-arrow {
        image: none;
        border: none;
        width: 0;
        height: 0;
    }

    QComboBox QAbstractItemView {
        border: 1px solid #505050;
        border-radius: 8px;
        background-color: #2A2A2A;
        selection-background-color: #404040;
        selection-color: #EEEEEE;
        padding: 4px;
        color: #EEEEEE;
        outline: none;
    }

    QComboBox QAbstractItemView::item {
        padding: 10px 16px;
        background-color: transparent;
        color: #EEEEEE;
        min-height: 28px;
        border-radius: 4px;
    }

    QComboBox QAbstractItemView::item:hover {
        background-color: #353535;
    }

    QComboBox QAbstractItemView::item:selected {
        background-color: #404040;
        color: #EEEEEE;
    }

    QLineEdit {
        background-color: transparent;
        border: none;
        color: #EEEEEE;
        padding: 0px;
    }

    /* Slider styling */
    QSlider::groove:horizontal {
        border: none;
        height: 6px;
        background: #2A2A2A;
        border-radius: 3px;
    }

    QSlider::sub-page:horizontal {
        background: #505050;
        border-radius: 3px;
    }

    QSlider::handle:horizontal {
        background: #DDDDDD;
        border: 2px solid #505050;
        width: 18px;
        height: 18px;
        margin: -7px 0;
        border-radius: 9px;
    }

    QSlider::handle:horizontal:hover {
        background: #FFFFFF;
        border-color: #707070;
    }

    QSlider::handle:horizontal:pressed {
        background: #CCCCCC;
    }

    /* Labels */
    QLabel {
        background-color: transparent;
        color: #EEEEEE;
        font-weight: 400;
    }
"""


def apply_dark_styles(widget: QtWidgets.QWidget) -> None:
    """Apply the dark theme stylesheet to the given widget."""
    widget.setStyleSheet(DARK_THEME_STYLESHEET)
