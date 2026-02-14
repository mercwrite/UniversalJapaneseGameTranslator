import sys
import uuid

import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui

from capture import WindowCapture
from translation import SugoiTranslator
from ocr import LocalVisionAI
from perf_logger import PerformanceLogger

from ui.text_overlay import TextBoxOverlay
from ui.snipper import Snipper
from ui.widgets import ModernComboBox, IconButton, OverlayListItem
from ui.styles import apply_dark_styles
from ui.pipeline import TranslationPipeline
from error_handler import (
    safe_execute,
    SafeWindowCapture,
    validate_region_data,
)


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

        # Create pipeline
        self.pipeline = TranslationPipeline(
            self.win_cap, self.vision_ai, self.translator, self.perf
        )

        # Apply dark theme styling
        apply_dark_styles(self)

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
        self.timer.timeout.connect(self._run_pipeline)

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
            # Stop both timers to prevent interference during snipper selection
            self.mouse_check_timer.stop()
            self.hover_timer.stop()

            self.snipper = Snipper()
            # Use QueuedConnection to process signal in next event loop iteration
            # This prevents crashes from processing during snipper's signal emission
            self.snipper.region_selected.connect(
                self.on_region_added,
                QtCore.Qt.ConnectionType.QueuedConnection
            )
            self.snipper.show()
        except Exception:
            # Restart timers on failure
            self.mouse_check_timer.start()
            raise

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to add region")
    def on_region_added(self, area: dict) -> None:
        """Handle region selection - called after snipper emits signal (queued)."""
        try:
            # Ensure controller is in valid state
            if not self.isVisible():
                self.show()

            # Clean up the snipper FIRST
            if hasattr(self, 'snipper') and self.snipper:
                try:
                    try:
                        self.snipper.region_selected.disconnect()
                    except Exception:
                        pass
                    self.snipper.deleteLater()
                    self.snipper = None
                except Exception:
                    pass

            # Store area as instance variable to avoid lambda capture issues
            self._pending_area = area.copy() if isinstance(area, dict) else dict(area)

            # Give Qt a moment to fully clean up the snipper before creating overlay
            QtCore.QTimer.singleShot(200, self._safe_create_overlay_callback)

        except Exception:
            # Ensure mouse timer restarts even on error
            if not self.mouse_check_timer.isActive():
                self.mouse_check_timer.start()

    def _safe_create_overlay_callback(self) -> None:
        """Safe wrapper for timer callback."""
        try:
            if not self or not isinstance(self, QtWidgets.QWidget):
                return
            self._create_overlay_from_pending()
        except Exception:
            try:
                if hasattr(self, 'mouse_check_timer') and not self.mouse_check_timer.isActive():
                    self.mouse_check_timer.start()
            except Exception:
                pass

    def _create_overlay_from_pending(self) -> None:
        """Create overlay from pending area data."""
        try:
            if not hasattr(self, '_pending_area') or not self._pending_area:
                if not self.mouse_check_timer.isActive():
                    self.mouse_check_timer.start()
                return

            area = self._pending_area
            self._pending_area = None

            if not validate_region_data(area):
                if not self.mouse_check_timer.isActive():
                    self.mouse_check_timer.start()
                return

            region_id = str(uuid.uuid4())[:8]

            # Create list item first (before overlay to avoid race conditions)
            try:
                list_item = OverlayListItem(f"Overlay {region_id}", region_id)
            except Exception:
                return

            # Create the overlay
            try:
                overlay = TextBoxOverlay(
                    area["left"],
                    area["top"],
                    area["width"],
                    area["height"],
                    initial_opacity=self.slider_opacity.value(),
                )
            except Exception:
                return

            # Store in active_regions BEFORE connecting signals
            self.active_regions[region_id] = {
                "rect": area,
                "overlay": overlay,
                "item": list_item,
            }

            # Connect signals (after everything is in active_regions)
            try:
                overlay.geometry_changed.connect(
                    lambda x, y, w, h, rid=region_id: self.on_overlay_geometry_changed(rid, x, y, w, h)
                )
            except Exception:
                pass

            try:
                list_item.delete_btn.clicked.connect(
                    lambda checked=False, rid=region_id: self.delete_region_by_id(rid)
                )
                list_item.toggle_btn.toggled.connect(
                    lambda checked, rid=region_id: self.on_overlay_toggle(rid, checked)
                )
            except Exception:
                pass

            # Add to layout (before stretch)
            try:
                self.list_layout.insertWidget(self.list_layout.count() - 1, list_item)
            except Exception:
                try:
                    overlay.close()
                    del self.active_regions[region_id]
                except Exception:
                    pass

            # Restart mouse check timer now that overlay is created
            if not self.mouse_check_timer.isActive():
                self.mouse_check_timer.start()

        except Exception as e:
            if not self.mouse_check_timer.isActive():
                self.mouse_check_timer.start()
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
            except Exception:
                pass
        except Exception:
            pass

    # ---- Pipeline ----

    def _run_pipeline(self) -> None:
        """Timer callback that delegates to the TranslationPipeline."""
        self.pipeline.run(self.active_regions, self.last_images, self.is_region_enabled)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())
