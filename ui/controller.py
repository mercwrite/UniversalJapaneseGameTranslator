import sys
import uuid

import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui

from window_capture import WindowCapture
from sugoi_wrapper import SugoiTranslator
from image_processor import ImagePreprocessor  # noqa: F401  (kept for future use)
from winocr_wrapper import WindowsOCR  # noqa: F401  (kept for future use)
from qwen_wrapper import LocalVisionAI
from perf_logger import PerformanceLogger
from deepseekocr_wrapper import DeepSeekLocalVisionAi  # noqa: F401  (kept for future use)

from ui.text_overlay import TextBoxOverlay
from ui.snipper import Snipper
from error_handler import (
    safe_execute,
    SafeWindowCapture,
    validate_region_data,
)


class ModernComboBox(QtWidgets.QComboBox):
    """Custom ComboBox with animated arrow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_popup_shown = False

    def showPopup(self):
        """Override to show popup below and track state."""
        self.is_popup_shown = True
        self.update()
        super().showPopup()

    def hidePopup(self):
        """Override to track state."""
        self.is_popup_shown = False
        self.update()
        super().hidePopup()

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Custom paint to draw arrow."""
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Draw arrow on the right side
        arrow_x = self.width() - 24
        arrow_y = self.height() // 2

        painter.setPen(QtGui.QPen(QtGui.QColor(170, 170, 170), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))

        if self.is_popup_shown:
            # Down-pointing triangle when open
            triangle = QtGui.QPolygon([
                QtCore.QPoint(arrow_x - 4, arrow_y - 2),
                QtCore.QPoint(arrow_x + 4, arrow_y - 2),
                QtCore.QPoint(arrow_x, arrow_y + 3)
            ])
        else:
            # Right-pointing triangle when closed
            triangle = QtGui.QPolygon([
                QtCore.QPoint(arrow_x - 2, arrow_y - 4),
                QtCore.QPoint(arrow_x - 2, arrow_y + 4),
                QtCore.QPoint(arrow_x + 3, arrow_y)
            ])

        painter.setBrush(QtGui.QColor(170, 170, 170))
        painter.drawPolygon(triangle)


class IconButton(QtWidgets.QPushButton):
    """Custom button with icon drawing capabilities."""

    def __init__(self, icon_type: str, size: int = 32, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.icon_size = size
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Custom paint for modern icon buttons."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Background on hover
        if self.underMouse():
            painter.setBrush(QtGui.QColor(70, 70, 70, 150))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 6, 6)

        # Draw icon
        painter.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))

        center_x = self.width() // 2
        center_y = self.height() // 2

        if self.icon_type == "eye":
            # Draw eye icon
            painter.drawEllipse(center_x - 8, center_y - 4, 16, 8)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)

        elif self.icon_type == "eye-slash":
            # Draw eye with slash
            painter.drawEllipse(center_x - 8, center_y - 4, 16, 8)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)
            painter.drawLine(center_x - 10, center_y - 6, center_x + 10, center_y + 6)

        elif self.icon_type == "close":
            # Draw X icon
            painter.drawLine(center_x - 6, center_y - 6, center_x + 6, center_y + 6)
            painter.drawLine(center_x + 6, center_y - 6, center_x - 6, center_y + 6)

        elif self.icon_type == "plus":
            # Draw + icon
            line_length = self.icon_size // 3
            painter.drawLine(center_x, center_y - line_length, center_x, center_y + line_length)
            painter.drawLine(center_x - line_length, center_y, center_x + line_length, center_y)

        elif self.icon_type == "play":
            # Draw play triangle (larger to match plus icon scale)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            triangle = QtGui.QPolygon([
                QtCore.QPoint(center_x - 6, center_y - 9),
                QtCore.QPoint(center_x - 6, center_y + 9),
                QtCore.QPoint(center_x + 10, center_y)
            ])
            painter.drawPolygon(triangle)

        elif self.icon_type == "stop":
            # Draw stop square
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawRect(center_x - 6, center_y - 6, 12, 12)

        elif self.icon_type == "refresh":
            # Draw circular arrow (refresh icon)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # Draw arc
            rect = QtCore.QRect(center_x - 8, center_y - 8, 16, 16)
            painter.drawArc(rect, 45 * 16, 270 * 16)
            # Draw arrow head
            arrow_points = QtGui.QPolygon([
                QtCore.QPoint(center_x + 6, center_y - 8),
                QtCore.QPoint(center_x + 6, center_y - 2),
                QtCore.QPoint(center_x + 10, center_y - 5)
            ])
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawPolygon(arrow_points)

        elif self.icon_type == "chevron-left":
            # Draw left-pointing chevron (double arrow)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # First chevron
            painter.drawLine(center_x + 2, center_y - 6, center_x - 3, center_y)
            painter.drawLine(center_x - 3, center_y, center_x + 2, center_y + 6)
            # Second chevron
            painter.drawLine(center_x + 6, center_y - 6, center_x + 1, center_y)
            painter.drawLine(center_x + 1, center_y, center_x + 6, center_y + 6)

        elif self.icon_type == "chevron-right":
            # Draw right-pointing chevron (double arrow)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # First chevron
            painter.drawLine(center_x - 6, center_y - 6, center_x - 1, center_y)
            painter.drawLine(center_x - 1, center_y, center_x - 6, center_y + 6)
            # Second chevron
            painter.drawLine(center_x - 2, center_y - 6, center_x + 3, center_y)
            painter.drawLine(center_x + 3, center_y, center_x - 2, center_y + 6)


class OverlayListItem(QtWidgets.QWidget):
    """Custom widget for overlay list items with name, toggle, and delete button."""

    def __init__(self, name: str, region_id: str, parent=None):
        super().__init__(parent)
        self.region_id = region_id
        self.setup_ui(name)

    def setup_ui(self, name: str):
        """Set up the UI for the list item."""
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Name label on the left
        self.name_label = QtWidgets.QLabel(name)
        self.name_label.setStyleSheet("""
            color: #EEEEEE;
            background-color: transparent;
            font-size: 13px;
            font-weight: 400;
        """)
        layout.addWidget(self.name_label, 1)  # Stretch factor

        # Toggle button (Eye icon) - acts as a toggle switch
        self.toggle_btn = IconButton("eye")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)  # Enabled by default
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
        """)
        self.toggle_btn.toggled.connect(self._update_toggle_icon)
        layout.addWidget(self.toggle_btn, 0)

        # Delete button (X icon)
        self.delete_btn = IconButton("close")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.delete_btn, 0)

        self.setLayout(layout)
        self.setStyleSheet("""
            OverlayListItem {
                background-color: transparent;
                border-radius: 6px;
                padding: 2px;
            }
            OverlayListItem:hover {
                background-color: rgba(70, 70, 70, 120);
            }
        """)

    def _update_toggle_icon(self, checked: bool):
        """Update the toggle button icon based on state."""
        self.toggle_btn.icon_type = "eye" if checked else "eye-slash"
        self.toggle_btn.update()


class ControllerWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ControllerWindow")
        self.setWindowTitle("Universal Japanese Game Translator")

        # Set window flags for overlay behavior
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Docking state
        self.is_expanded = False
        self.collapsed_width = 40
        self.expanded_width = 520
        self.tab_height = 100
        self.window_height = 680

        # Hover management
        self.hover_timer = QtCore.QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._check_mouse_position)
        self.mouse_check_timer = QtCore.QTimer()
        self.mouse_check_timer.setInterval(100)
        self.mouse_check_timer.timeout.connect(self._check_mouse_position)

        # Animation
        self.animation = QtCore.QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(250)  # 250ms for swift animation
        self.animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        # Set initial size (small tab only)
        self.resize(self.collapsed_width, self.tab_height)
        self.setMinimumSize(self.collapsed_width, self.tab_height)
        self.setMaximumSize(16777215, 16777215)  # Remove max size limit for expansion

        # Data storage:
        # { 'uuid_string': { 'rect': dict, 'overlay': TextBoxOverlay, 'item': OverlayListItem } }
        self.active_regions: dict[str, dict] = {}
        self.last_images: dict[str, "np.ndarray"] = {}
        self._pending_area = None  # For delayed overlay creation

        # Initialize backend components FIRST (before UI creation)
        self.win_cap = WindowCapture()
        self.perf = PerformanceLogger()
        
        # Initialize backend
        path_to_model = "sugoi_model"
        self.vision_ai = None
        self.translator = None
        self._initialize_backend(path_to_model)

        # Apply dark theme styling
        self._apply_dark_styles()

        # Create main horizontal layout
        container_layout = QtWidgets.QHBoxLayout()
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget (visible when collapsed)
        self.tab_widget = self._create_tab_widget()
        container_layout.addWidget(self.tab_widget)

        # Create main content widget
        self.content_widget = QtWidgets.QWidget()
        self.content_widget.setObjectName("ContentWidget")
        self.content_widget.setStyleSheet("""
            QWidget#ContentWidget {
                background-color: #0D0D0D;
                border: 1px solid #303030;
                border-left: none;
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
        """)
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # Top Section: Overlay List Container
        overlay_list_section = self._create_overlay_list_section()
        content_layout.addWidget(overlay_list_section, 1)

        # Middle Section: Actions & Settings
        actions_section = self._create_actions_section()
        content_layout.addWidget(actions_section, 0)

        # Bottom Section: Window Selection
        window_section = self._create_window_section()
        content_layout.addWidget(window_section, 0)

        self.content_widget.setLayout(content_layout)
        self.content_widget.hide()  # Hidden initially
        container_layout.addWidget(self.content_widget)

        self.setLayout(container_layout)

        # Initialize timer
        self.timer = QtCore.QTimer()
        self.timer.setInterval(100)  # ms
        self.timer.timeout.connect(self.run_batch_pipeline)

        # Track if translation is running
        self.is_running = False

        # Position window on right edge after a short delay
        QtCore.QTimer.singleShot(100, self._position_on_right_edge)

    def _create_tab_widget(self) -> QtWidgets.QWidget:
        """Create the tab widget shown when collapsed - small button."""
        tab = QtWidgets.QWidget()
        tab.setFixedSize(self.collapsed_width, self.tab_height)
        tab.setObjectName("TabWidget")
        tab.setStyleSheet("""
            QWidget#TabWidget {
                background-color: rgba(26, 26, 26, 220);
                border: 1px solid rgba(60, 60, 60, 200);
                border-right: none;
                border-radius: 12px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)

        # Tab layout
        tab_layout = QtWidgets.QVBoxLayout()
        tab_layout.setContentsMargins(4, 0, 4, 0)
        tab_layout.setSpacing(0)

        # Arrow button centered
        self.tab_arrow = IconButton("chevron-left", size=32)
        self.tab_arrow.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
        """)
        tab_layout.addStretch()
        tab_layout.addWidget(self.tab_arrow, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        tab_layout.addStretch()

        tab.setLayout(tab_layout)
        return tab

    def _position_on_right_edge(self):
        """Position the small tab on the right edge of the screen."""
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = screen.width() - self.collapsed_width
        y = (screen.height() - self.tab_height) // 2
        self.move(x, y)
        # Start checking mouse position
        self.mouse_check_timer.start()

    def enterEvent(self, event: QtCore.QEvent) -> None:
        """Handle mouse entering the widget."""
        super().enterEvent(event)
        if not self.is_expanded and not self.animation.state() == QtCore.QAbstractAnimation.State.Running:
            self._expand()

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        """Handle mouse leaving - but don't collapse immediately."""
        super().leaveEvent(event)
        # Start timer to check if mouse is really gone
        if self.is_expanded:
            self.hover_timer.start(300)  # 300ms delay before checking

    def _check_mouse_position(self):
        """Check if mouse is still over the window."""
        if not self.isVisible():
            return

        # Get global mouse position
        global_pos = QtGui.QCursor.pos()
        # Check if mouse is within window bounds (with small margin)
        window_rect = self.geometry()
        margin = 10
        expanded_rect = window_rect.adjusted(-margin, -margin, margin, margin)

        if expanded_rect.contains(global_pos):
            # Mouse is over window
            if not self.is_expanded and not self.animation.state() == QtCore.QAbstractAnimation.State.Running:
                self._expand()
        else:
            # Mouse is away from window
            if self.is_expanded and not self.animation.state() == QtCore.QAbstractAnimation.State.Running:
                self._collapse()

    def _expand(self):
        """Animate expansion of the window."""
        if self.is_expanded or self.animation.state() == QtCore.QAbstractAnimation.State.Running:
            return

        self.is_expanded = True
        self.content_widget.show()
        self.tab_arrow.icon_type = "chevron-right"
        self.tab_arrow.update()

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = screen.width() - self.expanded_width
        y = (screen.height() - self.window_height) // 2

        start_rect = self.geometry()
        end_rect = QtCore.QRect(x, y, self.expanded_width, self.window_height)

        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()

    def _collapse(self):
        """Animate collapse of the window."""
        if not self.is_expanded or self.animation.state() == QtCore.QAbstractAnimation.State.Running:
            return

        self.is_expanded = False
        self.tab_arrow.icon_type = "chevron-left"
        self.tab_arrow.update()

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = screen.width() - self.collapsed_width
        y = (screen.height() - self.tab_height) // 2

        start_rect = self.geometry()
        end_rect = QtCore.QRect(x, y, self.collapsed_width, self.tab_height)

        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()

        # Hide content after animation
        QtCore.QTimer.singleShot(self.animation.duration(), self.content_widget.hide)

    def _apply_dark_styles(self) -> None:
        """Apply dark theme CSS styling to the window."""
        self.setStyleSheet("""
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
        """)

    def _create_overlay_list_section(self) -> QtWidgets.QWidget:
        """Create the overlay list container section."""
        container = QtWidgets.QWidget()
        container.setObjectName("OverlayListContainer")
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)
        
        # Scroll area for the list
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget to hold list items
        self.list_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout()
        self.list_layout.setContentsMargins(4, 4, 4, 4)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()  # Push items to top
        self.list_widget.setLayout(self.list_layout)
        
        scroll_area.setWidget(self.list_widget)
        container_layout.addWidget(scroll_area)
        
        container.setLayout(container_layout)
        return container

    def _create_actions_section(self) -> QtWidgets.QWidget:
        """Create the actions and settings section."""
        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(12)
        
        # Button row
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add button with Plus icon
        self.btn_add = IconButton("plus", size=48)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                border: 1px solid #505050;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
        """)
        self.btn_add.setToolTip("Add Overlay")
        self.btn_add.clicked.connect(self.activate_snipper)
        button_layout.addWidget(self.btn_add)

        # Start/Stop button with Play/Square icon
        self.btn_start_stop = IconButton("play", size=48)
        self.btn_start_stop.setCheckable(True)
        self.btn_start_stop.setChecked(False)
        self.btn_start_stop.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                border: 1px solid #505050;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
            QPushButton:checked {
                background-color: #353535;
                border-color: #707070;
            }
        """)
        self.btn_start_stop.setToolTip("Start Translation")
        self.btn_start_stop.clicked.connect(self.toggle_translation)
        button_layout.addWidget(self.btn_start_stop)
        
        button_layout.addStretch()
        container_layout.addLayout(button_layout)
        
        # Opacity slider
        opacity_layout = QtWidgets.QVBoxLayout()
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(8)
        
        opacity_label = QtWidgets.QLabel("Opacity")
        opacity_label.setStyleSheet("color: #CCCCCC; background-color: transparent; font-weight: 500; font-size: 11px;")
        opacity_layout.addWidget(opacity_label)
        
        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.setContentsMargins(0, 0, 0, 0)
        
        self.slider_opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 255)
        self.slider_opacity.setValue(200)
        self.slider_opacity.valueChanged.connect(self.update_opacity)
        slider_layout.addWidget(self.slider_opacity)
        
        self.lbl_opacity = QtWidgets.QLabel("78%")
        self.lbl_opacity.setStyleSheet("color: #AAAAAA; background-color: transparent; min-width: 45px; font-size: 11px;")
        self.lbl_opacity.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        slider_layout.addWidget(self.lbl_opacity)
        
        opacity_layout.addLayout(slider_layout)
        container_layout.addLayout(opacity_layout)
        
        container.setLayout(container_layout)
        return container

    def _create_window_section(self) -> QtWidgets.QWidget:
        """Create the window selection section."""
        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)
        
        # Label
        window_label = QtWidgets.QLabel("Window")
        window_label.setStyleSheet("color: #CCCCCC; background-color: transparent; font-weight: 500; font-size: 11px;")
        container_layout.addWidget(window_label)
        
        # Selection row
        selection_layout = QtWidgets.QHBoxLayout()
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(12)
        
        # ComboBox with placeholder
        self.combo_games = ModernComboBox()
        self.combo_games.setEditable(True)
        self.combo_games.lineEdit().setPlaceholderText("Selected Window Here...")
        self.combo_games.lineEdit().setReadOnly(True)
        window_names = self.win_cap.list_window_names()
        if window_names:
            self.combo_games.addItems(window_names)
        else:
            self.combo_games.addItem("No windows available")
        self.combo_games.currentIndexChanged.connect(self.select_game_window)
        selection_layout.addWidget(self.combo_games, 1)  # Stretch factor
        
        # Refresh button with circular arrows icon
        self.btn_refresh = IconButton("refresh", size=48)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                border: 1px solid #505050;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #606060;
            }
            QPushButton:pressed {
                background-color: #404040;
            }
        """)
        self.btn_refresh.setToolTip("Refresh Window List")
        self.btn_refresh.clicked.connect(self.refresh_window_list)
        selection_layout.addWidget(self.btn_refresh, 0)
        
        container_layout.addLayout(selection_layout)
        container.setLayout(container_layout)
        return container

    def _initialize_backend(self, path_to_model: str) -> None:
        """Safely initialize backend components."""
        try:
            self.vision_ai = LocalVisionAI()
        except Exception as e:
            print(f"Warning: Failed to initialize Vision AI: {e}")
            self.vision_ai = None
        
        try:
            self.translator = SugoiTranslator(path_to_model, device="auto")
        except Exception as e:
            print(f"Warning: Failed to initialize Translator: {e}")
            self.translator = None

    # ---- UI callbacks ----

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to update opacity")
    def update_opacity(self, value=None) -> None:
        try:
            current_val = self.slider_opacity.value()  # 0-255
            percentage = int(current_val / 255 * 100)
            self.lbl_opacity.setText(f"{percentage}%")

            # Only update opacity for enabled overlays
            for rid, data in list(self.active_regions.items()):
                try:
                    if self.is_region_enabled(rid) and "overlay" in data:
                        overlay = data["overlay"]
                        if overlay:
                            overlay.set_background_opacity(current_val)
                except Exception:
                    continue
        except Exception:
            pass

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to refresh window list")
    def refresh_window_list(self, checked=None) -> None:
        try:
            current = self.combo_games.currentText()
            self.combo_games.clear()
            window_names = self.win_cap.list_window_names()
            if window_names:
                self.combo_games.addItems(window_names)
                try:
                    self.combo_games.setCurrentText(current)
                except Exception:
                    pass
        except Exception:
            pass

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to select game window")
    def select_game_window(self, index=None) -> None:
        try:
            title = self.combo_games.currentText()
            if title:
                self.win_cap.set_window_by_title(title)
        except Exception:
            pass

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to activate snipper")
    def activate_snipper(self, checked: bool = False) -> None:
        try:
            print("[DEBUG] activate_snipper called")
            # Don't hide the docked window - it should stay visible
            # Stop both timers to prevent interference during snipper selection
            self.mouse_check_timer.stop()
            print("[DEBUG] Mouse check timer stopped")
            self.hover_timer.stop()
            print("[DEBUG] Hover timer stopped")

            self.snipper = Snipper()
            print("[DEBUG] Snipper created")
            # Use QueuedConnection to process signal in next event loop iteration
            # This prevents crashes from processing during snipper's signal emission
            self.snipper.region_selected.connect(
                self.on_region_added,
                QtCore.Qt.ConnectionType.QueuedConnection
            )
            print("[DEBUG] Signal connected (queued)")
            self.snipper.show()
            print("[DEBUG] Snipper shown")
        except Exception as e:
            print(f"[ERROR] activate_snipper failed: {e}")
            # Restart timers on failure
            self.mouse_check_timer.start()
            raise

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to add region")
    def on_region_added(self, area: dict) -> None:
        """Handle region selection - called after snipper emits signal (queued)."""
        try:
            print(f"[DEBUG] ===== on_region_added START =====")
            print(f"[DEBUG] Received area: {area}")
            print(f"[DEBUG] Controller visible: {self.isVisible()}")
            print(f"[DEBUG] Controller geometry: {self.geometry()}")

            # Ensure controller is in valid state
            if not self.isVisible():
                print("[DEBUG] Controller not visible, making visible")
                self.show()

            # Clean up the snipper FIRST
            if hasattr(self, 'snipper') and self.snipper:
                print("[DEBUG] Cleaning up snipper from controller...")
                try:
                    # Disconnect signals before deletion
                    try:
                        self.snipper.region_selected.disconnect()
                        print("[DEBUG] Snipper signals disconnected")
                    except:
                        pass

                    # Use deleteLater for safe Qt cleanup
                    self.snipper.deleteLater()
                    self.snipper = None
                    print("[DEBUG] Snipper scheduled for deletion")
                except Exception as e:
                    print(f"[ERROR] Failed to clean up snipper: {e}")
                    import traceback
                    traceback.print_exc()

            # Store area as instance variable to avoid lambda capture issues
            self._pending_area = area.copy() if isinstance(area, dict) else dict(area)
            print(f"[DEBUG] Stored pending area: {self._pending_area}")

            # Give Qt a moment to fully clean up the snipper before creating overlay
            print("[DEBUG] Scheduling delayed overlay creation...")
            try:
                # Don't use processEvents() - can cause issues with queued connections
                # Wrap callback to catch any exceptions
                QtCore.QTimer.singleShot(200, self._safe_create_overlay_callback)
                print("[DEBUG] Timer scheduled successfully (200ms delay)")
            except Exception as e:
                print(f"[ERROR] Failed to schedule timer: {e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"[ERROR] ===== on_region_added EXCEPTION =====")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            print(f"[ERROR] Exception message: {e}")
            import traceback
            traceback.print_exc()
            print(f"[ERROR] ===== END EXCEPTION =====")

            # Ensure mouse timer restarts even on error
            if not self.mouse_check_timer.isActive():
                print("[DEBUG] Restarting mouse check timer after error")
                self.mouse_check_timer.start()

    def _safe_create_overlay_callback(self) -> None:
        """Safe wrapper for timer callback."""
        try:
            print("[DEBUG] ===== Timer callback executing =====")
            print(f"[DEBUG] self exists: {self is not None}")
            print(f"[DEBUG] self type: {type(self)}")
            print(f"[DEBUG] Has _pending_area: {hasattr(self, '_pending_area')}")

            # Double-check the controller is still valid
            if not self or not isinstance(self, QtWidgets.QWidget):
                print("[ERROR] Controller object is invalid!")
                return

            self._create_overlay_from_pending()

        except Exception as e:
            print(f"[ERROR] ===== TIMER CALLBACK CRASHED =====")
            print(f"[ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()
            print(f"[ERROR] ===== END CRASH =====")

            # Try to restart mouse timer even on crash
            try:
                if hasattr(self, 'mouse_check_timer') and not self.mouse_check_timer.isActive():
                    self.mouse_check_timer.start()
            except:
                pass

    def _create_overlay_from_pending(self) -> None:
        """Create overlay from pending area data."""
        print("[DEBUG] ===== _create_overlay_from_pending START =====")
        print(f"[DEBUG] Timer callback fired successfully")
        print(f"[DEBUG] Controller still visible: {self.isVisible()}")

        try:
            if not hasattr(self, '_pending_area') or not self._pending_area:
                print("[ERROR] No pending area data!")
                # Restart timers even on error
                if not self.mouse_check_timer.isActive():
                    self.mouse_check_timer.start()
                return

            area = self._pending_area
            self._pending_area = None  # Clear it
            print(f"[DEBUG] Retrieved pending area: {area}")

            if not validate_region_data(area):
                print("Invalid region data provided")
                # Restart timers
                if not self.mouse_check_timer.isActive():
                    self.mouse_check_timer.start()
                return

            region_id = str(uuid.uuid4())[:8]
            print(f"[DEBUG] Generated region_id: {region_id}")

            # Create list item first (before overlay to avoid race conditions)
            try:
                print("[DEBUG] Creating list item...")
                item_name = f"Overlay {region_id}"
                list_item = OverlayListItem(item_name, region_id)
                print("[DEBUG] List item created successfully")
            except Exception as e:
                print(f"[ERROR] Failed to create list item: {e}")
                import traceback
                traceback.print_exc()
                return

            # Create the overlay
            try:
                print(f"[DEBUG] Creating overlay at ({area['left']}, {area['top']}) size {area['width']}x{area['height']}")
                print(f"[DEBUG] Initial opacity: {self.slider_opacity.value()}")

                overlay = TextBoxOverlay(
                    area["left"],
                    area["top"],
                    area["width"],
                    area["height"],
                    initial_opacity=self.slider_opacity.value(),
                )
                print("[DEBUG] Overlay created successfully")
            except Exception as e:
                print(f"[ERROR] Failed to create overlay: {e}")
                import traceback
                traceback.print_exc()
                return

            # Store in active_regions BEFORE connecting signals
            self.active_regions[region_id] = {
                "rect": area,
                "overlay": overlay,
                "item": list_item,
            }

            # Now connect signals (after everything is in active_regions)
            try:
                overlay.geometry_changed.connect(
                    lambda x, y, w, h, rid=region_id: self.on_overlay_geometry_changed(rid, x, y, w, h)
                )
            except Exception as e:
                print(f"Failed to connect geometry signal: {e}")

            # Connect list item signals
            try:
                list_item.delete_btn.clicked.connect(
                    lambda checked=False, rid=region_id: self.delete_region_by_id(rid)
                )
                list_item.toggle_btn.toggled.connect(
                    lambda checked, rid=region_id: self.on_overlay_toggle(rid, checked)
                )
            except Exception as e:
                print(f"Failed to connect list item signals: {e}")

            # Add to layout (before stretch)
            try:
                self.list_layout.insertWidget(self.list_layout.count() - 1, list_item)
                print("[DEBUG] List item added to layout successfully")
            except Exception as e:
                print(f"[ERROR] Failed to add item to layout: {e}")
                import traceback
                traceback.print_exc()
                try:
                    overlay.close()
                    del self.active_regions[region_id]
                except Exception:
                    pass

            print(f"[DEBUG] Region {region_id} added successfully!")

            # Restart mouse check timer now that overlay is created
            print("[DEBUG] Restarting mouse check timer...")
            if not self.mouse_check_timer.isActive():
                self.mouse_check_timer.start()
                print("[DEBUG] Mouse check timer restarted")

        except Exception as e:
            print(f"[ERROR] _create_overlay_from_pending failed: {e}")
            import traceback
            traceback.print_exc()
            # Restart mouse check timer if it failed
            if not self.mouse_check_timer.isActive():
                self.mouse_check_timer.start()
            # Show error to user
            try:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error Creating Overlay",
                    f"Failed to create overlay: {str(e)}\n\nCheck console for details."
                )
            except Exception:
                pass

    def delete_region_by_id(self, region_id: str) -> None:
        """Delete a region by its ID."""
        try:
            if region_id not in self.active_regions:
                return

            # Close overlay
            try:
                overlay = self.active_regions[region_id].get("overlay")
                if overlay:
                    overlay.close()
            except Exception:
                pass

            # Remove list item widget
            try:
                item = self.active_regions[region_id].get("item")
                if item:
                    self.list_layout.removeWidget(item)
                    item.deleteLater()
            except Exception:
                pass

            # Clean up
            del self.active_regions[region_id]
            if region_id in self.last_images:
                del self.last_images[region_id]
        except Exception:
            pass

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to delete region")
    def delete_region(self) -> None:
        """Legacy method - kept for compatibility."""
        # This method is kept for compatibility but may not be used
        # with the new UI design
        pass

    def toggle_translation(self, checked=None) -> None:
        """Toggle translation on/off."""
        self.is_running = self.btn_start_stop.isChecked()

        if self.is_running:
            # Switch to Stop icon (Square)
            self.btn_start_stop.icon_type = "stop"
            self.btn_start_stop.setToolTip("Stop Translation")
            self.btn_start_stop.update()
            self.timer.start()
        else:
            # Switch to Play icon (Triangle)
            self.btn_start_stop.icon_type = "play"
            self.btn_start_stop.setToolTip("Start Translation")
            self.btn_start_stop.update()
            self.timer.stop()

    def on_overlay_toggle(self, region_id: str, checked: bool) -> None:
        """Handle overlay toggle state change."""
        try:
            if region_id not in self.active_regions:
                return

            overlay = self.active_regions[region_id].get("overlay")
            if not overlay:
                return

            if checked:
                try:
                    overlay.show()
                    overlay.set_background_opacity(self.slider_opacity.value())
                except Exception:
                    pass
            else:
                try:
                    overlay.hide()
                except Exception:
                    pass
        except Exception:
            pass

    @safe_execute(default_return=False, log_errors=False, error_message="Failed to check region enabled state")
    def is_region_enabled(self, region_id: str) -> bool:
        """Check if a region is enabled."""
        if not region_id or region_id not in self.active_regions:
            return False
        try:
            item = self.active_regions[region_id].get("item")
            if item and item.toggle_btn:
                return item.toggle_btn.isChecked()
        except Exception:
            pass
        return False

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to update geometry")
    def on_overlay_geometry_changed(
        self, region_id: str, x: int, y: int, width: int, height: int
    ) -> None:
        """Handle overlay position/size changes from user interaction."""
        try:
            if not region_id or region_id not in self.active_regions:
                return

            if width <= 0 or height <= 0 or width > 10000 or height > 10000:
                return

            # Safely update rect
            if "rect" not in self.active_regions[region_id]:
                self.active_regions[region_id]["rect"] = {}

            self.active_regions[region_id]["rect"] = {
                "left": x,
                "top": y,
                "width": width,
                "height": height,
            }

            # Update list item text if needed
            try:
                item = self.active_regions[region_id].get("item")
                if item and hasattr(item, "name_label"):
                    item.name_label.setText(f"Overlay {region_id} • {width}×{height}px")
            except Exception as e:
                print(f"Failed to update list item text: {e}")
        except Exception as e:
            print(f"Error in on_overlay_geometry_changed: {e}")

    # ---- Image / OCR pipeline ----

    @staticmethod
    @safe_execute(default_return=1000.0, log_errors=False, error_message="Failed to calculate image diff")
    def calculate_image_diff(img1, img2) -> float:
        """
        Returns a 'difference score' between two images.
        0 = Identical. Higher numbers = more different.
        """
        try:
            if img1 is None or img2 is None:
                return 1000.0

            if not SafeWindowCapture.validate_image(img1) or not SafeWindowCapture.validate_image(img2):
                return 1000.0

            if img1.size != img2.size:
                return 1000.0

            arr1 = np.array(img1.convert("L"), dtype=np.int16)
            arr2 = np.array(img2.convert("L"), dtype=np.int16)

            diff = np.abs(arr1 - arr2)
            return float(np.mean(diff))
        except Exception:
            return 1000.0

    @safe_execute(default_return=None, log_errors=True, error_message="Pipeline error")
    def run_batch_pipeline(self) -> None:
        """Run OCR on all active regions."""
        try:
            if not self.active_regions:
                return
            
            if not self.win_cap or not SafeWindowCapture.is_window_valid(self.win_cap.hwnd):
                return

            if not self.vision_ai or not self.translator:
                return

            self.perf.start_cycle()

            full_window_img = self.win_cap.screenshot()
            if not SafeWindowCapture.validate_image(full_window_img):
                return

            win_x, win_y, win_w, win_h = self.win_cap.get_window_rect()
            if win_w <= 0 or win_h <= 0:
                return

            for rid, data in list(self.active_regions.items()):
                try:
                    if not self.is_region_enabled(rid):
                        continue

                    if "rect" not in data or "overlay" not in data:
                        continue

                    screen_rect = data["rect"]
                    if not validate_region_data(screen_rect):
                        continue

                    rel_x = screen_rect["left"] - win_x
                    rel_y = screen_rect["top"] - win_y
                    rel_w = screen_rect["width"]
                    rel_h = screen_rect["height"]

                    if rel_x < 0 or rel_y < 0:
                        continue
                    if rel_x + rel_w > win_w or rel_y + rel_h > win_h:
                        continue
                    if rel_w <= 0 or rel_h <= 0:
                        continue

                    try:
                        current_crop = full_window_img.crop(
                            (rel_x, rel_y, rel_x + rel_w, rel_y + rel_h)
                        )
                        if not SafeWindowCapture.validate_image(current_crop):
                            continue
                    except Exception:
                        continue

                    last_img = self.last_images.get(rid)
                    diff_score = self.calculate_image_diff(current_crop, last_img)

                    if diff_score < 2.0:
                        continue

                    self.last_images[rid] = current_crop

                    try:
                        self.perf.start_ocr()
                        jap_text = self.vision_ai.analyze(current_crop, mode="ocr")
                        if not jap_text or not isinstance(jap_text, str):
                            continue
                    except Exception as e:
                        print(f"OCR error for region {rid}: {e}")
                        continue

                    try:
                        self.perf.start_translation()
                        eng_text = self.translator.translate(jap_text)
                        if not eng_text or not isinstance(eng_text, str):
                            eng_text = "Translation error"
                    except Exception as e:
                        print(f"Translation error for region {rid}: {e}")
                        eng_text = "Translation error"

                    try:
                        stats = self.perf.end_cycle()
                        print(
                            f"[PERF] OCR: {stats['ocr_ms']}ms | "
                            f"Trans: {stats['trans_ms']}ms | "
                            f"Total: {stats['total_ms']}ms"
                        )
                    except Exception:
                        pass

                    try:
                        overlay = data.get("overlay")
                        if overlay:
                            overlay.update_text(eng_text)
                    except Exception:
                        pass

                except Exception:
                    continue

        except Exception:
            pass


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())
