"""Settings page widget for OCR engine selection and app configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6 import QtWidgets, QtCore, QtGui

from ui.widgets import ModernComboBox

if TYPE_CHECKING:
    from ocr.manager import OCRManager


class SettingsPageWidget(QtWidgets.QWidget):
    """Application settings: engine selection, translation status, performance."""

    engine_changed = QtCore.pyqtSignal(int)
    interval_changed = QtCore.pyqtSignal(int)
    preprocess_toggled = QtCore.pyqtSignal(int, bool)  # (engine_type_value, enabled)
    overlay_bg_color_changed = QtCore.pyqtSignal(str)    # hex color
    overlay_text_color_changed = QtCore.pyqtSignal(str)  # hex color
    exit_requested = QtCore.pyqtSignal()

    def __init__(self, ocr_manager: OCRManager, parent=None):
        super().__init__(parent)
        self._ocr_manager = ocr_manager
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(20)

        # ── Section 1: OCR Engine ──
        engine_section = self._create_section("OCR Engine")
        engine_layout = engine_section.layout()

        # Engine selector
        self.engine_combo = ModernComboBox()
        for etype, name, requires_gpu in self._ocr_manager.available_engines():
            self.engine_combo.addItem(name, etype.value)
        # Set current selection
        current_type = self._ocr_manager.active_engine_type
        for i in range(self.engine_combo.count()):
            if self.engine_combo.itemData(i) == current_type.value:
                self.engine_combo.setCurrentIndex(i)
                break
        self.engine_combo.currentIndexChanged.connect(self._on_engine_selected)
        engine_layout.addWidget(self.engine_combo)

        # GPU info label
        self.gpu_info_label = QtWidgets.QLabel()
        self.gpu_info_label.setStyleSheet(
            "background-color: transparent; font-size: 11px; padding: 2px 0px;"
        )
        self._update_gpu_info()
        engine_layout.addWidget(self.gpu_info_label)

        # Preprocessing toggle
        self.preprocess_check = QtWidgets.QCheckBox("Apply preprocessing to this engine")
        self.preprocess_check.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; font-size: 11px;"
        )
        self.preprocess_check.setChecked(self._ocr_manager.should_preprocess)
        self.preprocess_check.setToolTip(
            "VLM engines typically perform better without preprocessing.\n"
            "Lightweight engines benefit from preprocessing."
        )
        self.preprocess_check.toggled.connect(self._on_preprocess_toggled)
        engine_layout.addWidget(self.preprocess_check)

        layout.addWidget(engine_section)

        # ── Section 2: Translation ──
        trans_section = self._create_section("Translation Engine")
        trans_layout = trans_section.layout()

        self.translator_status = QtWidgets.QLabel()
        self.translator_status.setStyleSheet(
            "background-color: transparent; font-size: 11px; padding: 2px 0px;"
        )
        self._update_translator_status()
        trans_layout.addWidget(self.translator_status)

        path_label = QtWidgets.QLabel("Model Path")
        path_label.setStyleSheet(
            "color: #999999; background-color: transparent; font-size: 10px;"
        )
        trans_layout.addWidget(path_label)

        path_field = QtWidgets.QLineEdit("sugoi_model")
        path_field.setReadOnly(True)
        path_field.setStyleSheet("""
            QLineEdit {
                background-color: #1A1A1A;
                color: #AAAAAA;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
        """)
        trans_layout.addWidget(path_field)

        layout.addWidget(trans_section)

        # ── Section 3: Performance ──
        perf_section = self._create_section("Pipeline Interval")
        perf_layout = perf_section.layout()

        slider_row = QtWidgets.QHBoxLayout()
        slider_row.setContentsMargins(0, 0, 0, 0)

        self.interval_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.interval_slider.setRange(50, 2000)
        self.interval_slider.setValue(100)
        self.interval_slider.setToolTip(
            "How often the translation pipeline runs.\n"
            "Lower = faster updates but more CPU/GPU usage."
        )
        self.interval_slider.valueChanged.connect(self._on_interval_changed)
        slider_row.addWidget(self.interval_slider)

        self.interval_label = QtWidgets.QLabel("100ms")
        self.interval_label.setStyleSheet(
            "color: #AAAAAA; background-color: transparent; min-width: 55px; font-size: 11px;"
        )
        self.interval_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        slider_row.addWidget(self.interval_label)

        perf_layout.addLayout(slider_row)
        layout.addWidget(perf_section)

        # ── Section 4: Overlay Colors ──
        color_section = self._create_section("Overlay Colors")
        color_layout = color_section.layout()

        # Background color row
        bg_row = QtWidgets.QHBoxLayout()
        bg_row.setContentsMargins(0, 0, 0, 0)
        bg_row.setSpacing(12)

        bg_label = QtWidgets.QLabel("Background Color")
        bg_label.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; font-size: 11px;"
        )
        bg_row.addWidget(bg_label)
        bg_row.addStretch()

        self.bg_color_swatch = ColorSwatch("#0D0D0D")
        self.bg_color_swatch.clicked.connect(self._pick_bg_color)
        bg_row.addWidget(self.bg_color_swatch)

        color_layout.addLayout(bg_row)

        # Text color row
        text_row = QtWidgets.QHBoxLayout()
        text_row.setContentsMargins(0, 0, 0, 0)
        text_row.setSpacing(12)

        text_label = QtWidgets.QLabel("Text Color")
        text_label.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; font-size: 11px;"
        )
        text_row.addWidget(text_label)
        text_row.addStretch()

        self.text_color_swatch = ColorSwatch("#EEEEEE")
        self.text_color_swatch.clicked.connect(self._pick_text_color)
        text_row.addWidget(self.text_color_swatch)

        color_layout.addLayout(text_row)
        layout.addWidget(color_section)

        # ── Section 5: About ──
        about_label = QtWidgets.QLabel("Universal Japanese Game Translator v0.1")
        about_label.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; font-size: 11px;"
        )
        about_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(about_label)

        about_sub = QtWidgets.QLabel("OCR + Translation Pipeline")
        about_sub.setStyleSheet(
            "color: #888888; background-color: transparent; font-size: 10px;"
        )
        about_sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(about_sub)

        layout.addStretch()

        # ── Exit button ──
        btn_exit = QtWidgets.QPushButton("Exit Application")
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #8B2020;
                color: #EEEEEE;
                border: 1px solid #A03030;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #A03030;
                border-color: #C04040;
            }
            QPushButton:pressed {
                background-color: #6B1515;
            }
        """)
        btn_exit.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_exit.clicked.connect(self.exit_requested.emit)
        layout.addWidget(btn_exit)

        self.setLayout(layout)

    def _create_section(self, title: str) -> QtWidgets.QWidget:
        """Create a labeled section container."""
        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)

        label = QtWidgets.QLabel(title)
        label.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; "
            "font-weight: 500; font-size: 11px;"
        )
        container_layout.addWidget(label)

        container.setLayout(container_layout)
        return container

    def _update_gpu_info(self) -> None:
        try:
            engine = self._ocr_manager.active_engine
            if engine.requires_gpu:
                self.gpu_info_label.setText("⚡ Requires NVIDIA GPU")
                self.gpu_info_label.setStyleSheet(
                    "color: #FFB347; background-color: transparent; font-size: 11px; padding: 2px 0px;"
                )
            else:
                self.gpu_info_label.setText("✓ Runs on CPU")
                self.gpu_info_label.setStyleSheet(
                    "color: #7BC67E; background-color: transparent; font-size: 11px; padding: 2px 0px;"
                )
        except Exception:
            self.gpu_info_label.setText("No engine selected")
            self.gpu_info_label.setStyleSheet(
                "color: #888888; background-color: transparent; font-size: 11px; padding: 2px 0px;"
            )

    def _update_translator_status(self) -> None:
        # Check parent chain for translator reference
        controller = self.parent()
        has_translator = False
        if controller and hasattr(controller, 'parent'):
            # Navigate up to find ControllerWindow
            win = controller
            while win is not None:
                if hasattr(win, 'translator'):
                    has_translator = win.translator is not None
                    break
                win = win.parent() if hasattr(win, 'parent') and callable(win.parent) else None

        if has_translator:
            self.translator_status.setText("Sugoi Translator: ✓ Loaded")
            self.translator_status.setStyleSheet(
                "color: #7BC67E; background-color: transparent; font-size: 11px; padding: 2px 0px;"
            )
        else:
            self.translator_status.setText("Sugoi Translator: ✗ Not loaded")
            self.translator_status.setStyleSheet(
                "color: #FF6B6B; background-color: transparent; font-size: 11px; padding: 2px 0px;"
            )

    def _on_engine_selected(self, index: int) -> None:
        if index < 0:
            return
        engine_type_val = self.engine_combo.itemData(index)
        if engine_type_val is not None:
            self.engine_changed.emit(engine_type_val)
            self._update_gpu_info()
            # Update preprocessing checkbox for new engine
            from ocr.manager import EngineType
            try:
                etype = EngineType(engine_type_val)
                self._ocr_manager.set_engine(etype)
                self.preprocess_check.setChecked(self._ocr_manager.should_preprocess)
            except Exception:
                pass

    def _on_preprocess_toggled(self, checked: bool) -> None:
        self._ocr_manager.should_preprocess = checked
        self.preprocess_toggled.emit(self._ocr_manager.active_engine_type.value, checked)

    def _on_interval_changed(self, value: int) -> None:
        self.interval_label.setText(f"{value}ms")
        self.interval_changed.emit(value)

    def set_interval(self, value: int) -> None:
        """Set the interval slider value (used when loading saved preferences)."""
        self.interval_slider.setValue(value)

    def set_translator_loaded(self, loaded: bool) -> None:
        """Update translator status display."""
        if loaded:
            self.translator_status.setText("Sugoi Translator: ✓ Loaded")
            self.translator_status.setStyleSheet(
                "color: #7BC67E; background-color: transparent; font-size: 11px; padding: 2px 0px;"
            )
        else:
            self.translator_status.setText("Sugoi Translator: ✗ Not loaded")
            self.translator_status.setStyleSheet(
                "color: #FF6B6B; background-color: transparent; font-size: 11px; padding: 2px 0px;"
            )

    def set_overlay_colors(self, bg_color: str, text_color: str) -> None:
        """Set the color swatches to reflect saved preferences."""
        self.bg_color_swatch.set_color(bg_color)
        self.text_color_swatch.set_color(text_color)

    def _pick_bg_color(self) -> None:
        """Open color picker for overlay background color."""
        current = QtGui.QColor(self.bg_color_swatch.color)
        color = QtWidgets.QColorDialog.getColor(
            current, self, "Overlay Background Color",
            QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog
        )
        if color.isValid():
            hex_color = color.name()
            self.bg_color_swatch.set_color(hex_color)
            self.overlay_bg_color_changed.emit(hex_color)

    def _pick_text_color(self) -> None:
        """Open color picker for overlay text color."""
        current = QtGui.QColor(self.text_color_swatch.color)
        color = QtWidgets.QColorDialog.getColor(
            current, self, "Overlay Text Color",
            QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog
        )
        if color.isValid():
            hex_color = color.name()
            self.text_color_swatch.set_color(hex_color)
            self.overlay_text_color_changed.emit(hex_color)


class ColorSwatch(QtWidgets.QPushButton):
    """A small clickable rectangle that displays a color."""

    def __init__(self, color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(36, 24)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def set_color(self, color: str) -> None:
        self.color = color
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color};
                border: 1px solid #606060;
                border-radius: 4px;
                min-height: 0px;
                padding: 0px;
            }}
            QPushButton:hover {{
                border-color: #909090;
                border-width: 2px;
            }}
        """)
