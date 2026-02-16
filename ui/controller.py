import sys
import uuid

import numpy as np
from PyQt6 import QtWidgets, QtCore, QtGui

from capture import WindowCapture
from translation import SugoiTranslator
from ocr.manager import OCRManager, EngineType
from ocr.preprocessing import PreprocessingPipeline
from perf_logger import PerformanceLogger
from preferences import Preferences

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

        # Set window flags for overlay behavior (no-focus to prevent game stalling)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Tool |
            QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Docking state
        self.is_expanded = False
        self.collapsed_width = 40
        self.expanded_width = 560
        self.tab_height = 100
        self.window_height = 720

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
        self._overlay_counter = 0  # For consecutive overlay naming

        # Initialize backend components FIRST (before UI creation)
        self.win_cap = WindowCapture()
        self.perf = PerformanceLogger()

        # Load user preferences
        self.prefs = Preferences()

        # Initialize backend (OCR manager + translator)
        path_to_model = "sugoi_model"
        self.ocr_manager = None
        self.translator = None
        self._initialize_backend(path_to_model)

        # Apply saved preferences to backend
        self._apply_saved_preferences()

        # Create pipeline
        self.pipeline = TranslationPipeline(
            self.win_cap, self.ocr_manager, self.translator, self.perf
        )

        # Initialize timer (before UI so settings page can connect to it)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.prefs.pipeline_interval)
        self.timer.timeout.connect(self._run_pipeline)

        # Track if translation is running
        self.is_running = False

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
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(20, 12, 20, 20)

        # ── Navigation bar ──
        nav_bar_widget = QtWidgets.QWidget()
        nav_bar_widget.setFixedHeight(40)
        nav_layout = QtWidgets.QHBoxLayout()
        nav_layout.setContentsMargins(2, 2, 2, 2)
        nav_layout.setSpacing(4)

        nav_btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                min-height: 0px;
                padding: 0px;
            }
        """

        self.nav_btn_main = IconButton("home", size=32)
        self.nav_btn_main.setStyleSheet(nav_btn_style)
        self.nav_btn_main.setToolTip("Main")
        self.nav_btn_main.clicked.connect(lambda: self._switch_page(0))
        nav_layout.addWidget(self.nav_btn_main)

        self.nav_btn_preprocess = IconButton("image-edit", size=32)
        self.nav_btn_preprocess.setStyleSheet(nav_btn_style)
        self.nav_btn_preprocess.setToolTip("Preprocessing")
        self.nav_btn_preprocess.clicked.connect(lambda: self._switch_page(1))
        nav_layout.addWidget(self.nav_btn_preprocess)

        self.nav_btn_settings = IconButton("gear", size=32)
        self.nav_btn_settings.setStyleSheet(nav_btn_style)
        self.nav_btn_settings.setToolTip("Settings")
        self.nav_btn_settings.clicked.connect(lambda: self._switch_page(2))
        nav_layout.addWidget(self.nav_btn_settings)

        nav_layout.addStretch()
        nav_bar_widget.setLayout(nav_layout)
        content_layout.addWidget(nav_bar_widget)

        # Separator line
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #404040; border: none;")
        content_layout.addWidget(separator)

        # ── Page stack ──
        self.page_stack = QtWidgets.QStackedWidget()

        # Page 0: Main page (overlay list + actions + window)
        main_page = QtWidgets.QWidget()
        main_page_layout = QtWidgets.QVBoxLayout()
        main_page_layout.setSpacing(16)
        main_page_layout.setContentsMargins(0, 12, 0, 0)

        overlay_list_section = self._create_overlay_list_section()
        main_page_layout.addWidget(overlay_list_section, 1)

        actions_section = self._create_actions_section()
        main_page_layout.addWidget(actions_section, 0)

        window_section = self._create_window_section()
        main_page_layout.addWidget(window_section, 0)

        main_page.setLayout(main_page_layout)
        self.page_stack.addWidget(main_page)

        # Page 1: Preprocessing editor
        from ui.preprocessing_editor import PreprocessingEditorWidget
        self.preprocess_page = PreprocessingEditorWidget(
            self.ocr_manager,
            capture_callback=self._get_region_crop,
            get_regions_callback=self._get_active_region_list,
            on_pipeline_changed=self._save_preprocessing_prefs,
        )
        self.page_stack.addWidget(self.preprocess_page)

        # Page 2: Settings
        from ui.settings_page import SettingsPageWidget
        self.settings_page = SettingsPageWidget(self.ocr_manager)
        self.settings_page.engine_changed.connect(self._on_engine_changed_from_settings)
        self.settings_page.interval_changed.connect(self._on_interval_changed)
        self.settings_page.preprocess_toggled.connect(
            lambda etype_val, enabled: self.prefs.set_preprocess_for_engine(etype_val, enabled)
        )
        self.settings_page.exit_requested.connect(self._exit_application)
        self.settings_page.overlay_bg_color_changed.connect(self._on_overlay_bg_color_changed)
        self.settings_page.overlay_text_color_changed.connect(self._on_overlay_text_color_changed)
        self.settings_page.set_translator_loaded(self.translator is not None)
        self.settings_page.set_interval(self.prefs.pipeline_interval)
        self.settings_page.set_overlay_colors(self.prefs.overlay_bg_color, self.prefs.overlay_text_color)
        self.page_stack.addWidget(self.settings_page)

        self.page_stack.setCurrentIndex(0)
        content_layout.addWidget(self.page_stack, 1)

        self.content_widget.setLayout(content_layout)
        self.content_widget.hide()  # Hidden initially
        container_layout.addWidget(self.content_widget)

        self.setLayout(container_layout)

        # Set initial nav button active state
        self._switch_page(0)

        # Position window on right edge immediately (before show())
        self._position_on_right_edge()
        # Start mouse tracking after a short delay to ensure window is fully rendered
        QtCore.QTimer.singleShot(100, self.mouse_check_timer.start)
        # Apply Win32 WS_EX_NOACTIVATE after window is shown
        QtCore.QTimer.singleShot(0, self._apply_noactivate_style)

    def _apply_noactivate_style(self):
        """Apply Win32 WS_EX_NOACTIVATE to prevent game focus loss on click."""
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except Exception:
            pass

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

    def _switch_page(self, index: int) -> None:
        """Switch visible page and update nav button states."""
        self.page_stack.setCurrentIndex(index)
        # Refresh overlay list when switching to preprocessing page
        if index == 1 and hasattr(self, 'preprocess_page'):
            self.preprocess_page.refresh_overlay_list()
        for i, btn in enumerate([self.nav_btn_main, self.nav_btn_preprocess,
                                  self.nav_btn_settings]):
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(60, 60, 60, 200);
                        border: none;
                        border-radius: 6px;
                        border-bottom: 2px solid #5A9FD4;
                        min-height: 0px;
                        padding: 0px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        border-radius: 6px;
                        min-height: 0px;
                        padding: 0px;
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
        self.combo_games.lineEdit().setPlaceholderText("Select a window...")
        self.combo_games.lineEdit().setReadOnly(True)
        self.combo_games.currentIndexChanged.connect(self.select_game_window)
        window_names = self.win_cap.list_window_names()
        if window_names:
            self.combo_games.addItems(window_names)
        self.combo_games.setCurrentIndex(-1)
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
        """Initialize OCR manager with engines and translation backend."""
        self.ocr_manager = OCRManager()

        # Register lightweight engine (always available, CPU-friendly)
        try:
            from ocr.manga_ocr_engine import MangaOCREngine
            manga_engine = MangaOCREngine(device="auto", force_cpu=False)
            self.ocr_manager.register_engine(EngineType.LIGHTWEIGHT, manga_engine)
        except Exception as e:
            print(f"Warning: Failed to register manga-ocr: {e}")

        # Register VLM engine (only if NVIDIA GPU with CUDA is available)
        has_cuda = False
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except ImportError:
            pass

        if has_cuda:
            try:
                from ocr.vlm_engine import QwenVLMEngine
                vlm_engine = QwenVLMEngine()
                self.ocr_manager.register_engine(EngineType.VLM, vlm_engine)
            except Exception as e:
                print(f"Warning: Failed to register Qwen VLM: {e}")
        else:
            print("Info: Qwen VLM not available (no NVIDIA GPU with CUDA detected)")

        # Default to lightweight
        try:
            self.ocr_manager.set_engine(EngineType.LIGHTWEIGHT)
        except ValueError:
            print("Warning: No OCR engines available!")

        # Translator (unchanged logic)
        try:
            self.translator = SugoiTranslator(path_to_model, device="auto")
        except Exception as e:
            print(f"Warning: Failed to initialize Translator: {e}")
            self.translator = None

    # ---- UI callbacks ----

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to update opacity")
    def update_opacity(self, value=None) -> None:
        current_val = self.slider_opacity.value()  # 0-255
        percentage = int(current_val / 255 * 100)
        self.lbl_opacity.setText(f"{percentage}%")

        # Only update opacity for enabled overlays
        for rid, data in list(self.active_regions.items()):
            if self.is_region_enabled(rid) and "overlay" in data:
                overlay = data["overlay"]
                if overlay:
                    overlay.set_background_opacity(current_val)

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to refresh window list")
    def refresh_window_list(self, checked=None) -> None:
        previous = self.combo_games.currentText()
        self.combo_games.blockSignals(True)
        try:
            self.combo_games.clear()
            window_names = self.win_cap.list_window_names()
            if window_names:
                self.combo_games.addItems(window_names)
            idx = self.combo_games.findText(previous) if previous else -1
            self.combo_games.setCurrentIndex(idx)
        finally:
            self.combo_games.blockSignals(False)
        # Only trigger selection if it actually changed
        if self.combo_games.currentText() != previous:
            self.select_game_window()

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to select game window")
    def select_game_window(self, index=None) -> None:
        title = self.combo_games.currentText()
        if title:
            self.win_cap.set_window_by_title(title)

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
            self._overlay_counter += 1

            # Create list item first (before overlay to avoid race conditions)
            try:
                list_item = OverlayListItem(f"Overlay {self._overlay_counter}", region_id)
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
                    bg_color=self.prefs.overlay_bg_color,
                    text_color=self.prefs.overlay_text_color,
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
                overlay.close_requested.connect(
                    lambda rid=region_id: self.delete_region_by_id(rid)
                )
                overlay.interaction_started.connect(self._on_overlay_interaction_started)
                overlay.interaction_finished.connect(self._on_overlay_interaction_finished)
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

            # No longer overwrite the user's custom overlay name on resize
        except Exception:
            pass

    def _on_overlay_interaction_started(self) -> None:
        """Pause translation while user is dragging/resizing an overlay."""
        if self.is_running and self.timer.isActive():
            self.timer.stop()

    def _on_overlay_interaction_finished(self) -> None:
        """Resume translation after user finishes dragging/resizing an overlay."""
        if self.is_running and not self.timer.isActive():
            self.timer.start()

    # ---- Preferences ----

    def _apply_saved_preferences(self) -> None:
        """Apply loaded preferences to backend components."""
        if not self.ocr_manager:
            return
        # Restore engine selection
        try:
            saved_engine = EngineType(self.prefs.engine_type)
            if saved_engine in self.ocr_manager._engines:
                self.ocr_manager.set_engine(saved_engine)
        except (ValueError, KeyError):
            pass

        # Restore per-engine preprocessing toggles
        for etype in EngineType:
            val = self.prefs.get_preprocess_for_engine(etype.value)
            if val is not None:
                self.ocr_manager._preprocess_by_engine[etype] = val

        # Restore preprocessing pipeline
        saved_pipeline = self.prefs.preprocessing_pipeline
        if saved_pipeline is not None:
            try:
                self.ocr_manager.pipeline = PreprocessingPipeline.from_dict(saved_pipeline)
            except Exception as e:
                print(f"Warning: Failed to restore preprocessing pipeline: {e}")

    def _save_preprocessing_prefs(self) -> None:
        """Save current preprocessing pipeline to preferences."""
        if self.ocr_manager:
            self.prefs.preprocessing_pipeline = self.ocr_manager.pipeline.to_dict()

    def _on_interval_changed(self, value: int) -> None:
        """Handle pipeline interval change from settings page."""
        self.timer.setInterval(value)
        self.prefs.pipeline_interval = value

    def _on_overlay_bg_color_changed(self, color_hex: str) -> None:
        """Handle overlay background color change from settings."""
        self.prefs.overlay_bg_color = color_hex
        for data in self.active_regions.values():
            overlay = data.get("overlay")
            if overlay:
                overlay.set_bg_color(color_hex)

    def _on_overlay_text_color_changed(self, color_hex: str) -> None:
        """Handle overlay text color change from settings."""
        self.prefs.overlay_text_color = color_hex
        for data in self.active_regions.values():
            overlay = data.get("overlay")
            if overlay:
                overlay.set_text_color(color_hex)

    def _exit_application(self) -> None:
        """Clean shutdown of the application."""
        # Stop translation
        self.timer.stop()
        self.mouse_check_timer.stop()
        self.hover_timer.stop()

        # Close all overlays
        for rid, data in list(self.active_regions.items()):
            try:
                overlay = data.get("overlay")
                if overlay:
                    overlay.close()
            except Exception:
                pass

        # Unload OCR engines
        if self.ocr_manager:
            self.ocr_manager.unload_all()

        QtWidgets.QApplication.quit()

    # ---- Engine change from settings ----

    def _on_engine_changed_from_settings(self, engine_type_value: int) -> None:
        """Handle OCR engine change from settings page."""
        try:
            engine_type = EngineType(engine_type_value)
            self.ocr_manager.set_engine(engine_type)
            self.prefs.engine_type = engine_type_value
        except Exception as e:
            print(f"Failed to switch engine: {e}")

    # ---- Preview capture helpers ----

    def _get_active_region_list(self) -> list[tuple[str, str]]:
        """Return (region_id, display_name) for all active regions."""
        result = []
        for rid, data in self.active_regions.items():
            item = data.get("item")
            name = item.name_label.text() if item and hasattr(item, "name_label") else f"Overlay {rid}"
            result.append((rid, name))
        return result

    def _get_region_crop(self, region_id: str):
        """Capture and crop a specific region by its ID."""
        try:
            if region_id not in self.active_regions:
                return None
            if not self.win_cap or not SafeWindowCapture.is_window_valid(self.win_cap.hwnd):
                return None

            full_img = self.win_cap.screenshot()
            if not SafeWindowCapture.validate_image(full_img):
                return None

            win_x, win_y, win_w, win_h = self.win_cap.get_window_rect()

            rect = self.active_regions[region_id].get("rect")
            if not rect or not validate_region_data(rect):
                return None

            rel_x = rect["left"] - win_x
            rel_y = rect["top"] - win_y
            rel_w = rect["width"]
            rel_h = rect["height"]

            if rel_x < 0 or rel_y < 0:
                return None
            if rel_x + rel_w > win_w or rel_y + rel_h > win_h:
                return None

            crop = full_img.crop((rel_x, rel_y, rel_x + rel_w, rel_y + rel_h))
            if SafeWindowCapture.validate_image(crop):
                return crop
            return None
        except Exception:
            return None

    # ---- Pipeline ----

    def _run_pipeline(self) -> None:
        """Timer callback that delegates to the TranslationPipeline."""
        self.pipeline.run(self.active_regions, self.last_images, self.is_region_enabled)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())
