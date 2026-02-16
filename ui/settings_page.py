"""Settings page widget for OCR engine selection and app configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6 import QtWidgets, QtCore, QtGui

from ui.widgets import SpinnerWidget

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

    def __init__(self, ocr_manager: OCRManager, has_cuda: bool = False, parent=None):
        super().__init__(parent)
        self._ocr_manager = ocr_manager
        self._has_cuda = has_cuda
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(20)

        # ── Section 1: OCR Engine ──
        engine_section = self._create_section("OCR Engine")
        engine_layout = engine_section.layout()

        # Radio button style
        radio_style = (
            "QRadioButton { color: #CCCCCC; background-color: transparent; "
            "font-size: 11px; spacing: 6px; }"
            "QRadioButton::indicator { width: 14px; height: 14px; }"
            "QRadioButton::indicator:unchecked { "
            "  border: 2px solid #606060; border-radius: 8px; background-color: transparent; }"
            "QRadioButton::indicator:checked { "
            "  border: 2px solid #5599FF; border-radius: 8px; "
            "  background-color: #5599FF; }"
        )
        radio_disabled_style = (
            "QRadioButton { color: #666666; background-color: transparent; "
            "font-size: 11px; spacing: 6px; }"
            "QRadioButton::indicator { width: 14px; height: 14px; }"
            "QRadioButton::indicator:unchecked { "
            "  border: 2px solid #404040; border-radius: 8px; background-color: transparent; }"
        )

        from ocr.manager import EngineType

        self._engine_button_group = QtWidgets.QButtonGroup(self)
        self._engine_button_group.setExclusive(True)

        # manga-ocr radio button (always available)
        self._radio_lightweight = QtWidgets.QRadioButton("manga-ocr (Lightweight)")
        self._radio_lightweight.setStyleSheet(radio_style)
        self._radio_lightweight.setToolTip("CPU-friendly OCR engine, works on any hardware.")
        self._engine_button_group.addButton(self._radio_lightweight, EngineType.LIGHTWEIGHT)
        engine_layout.addWidget(self._radio_lightweight)

        # Qwen VLM radio button + GPU note
        vlm_row = QtWidgets.QHBoxLayout()
        vlm_row.setContentsMargins(0, 0, 0, 0)
        vlm_row.setSpacing(8)

        self._radio_vlm = QtWidgets.QRadioButton("Qwen VLM (High Accuracy)")
        self._engine_button_group.addButton(self._radio_vlm, EngineType.VLM)

        if self._has_cuda:
            self._radio_vlm.setStyleSheet(radio_style)
            self._radio_vlm.setToolTip("High-accuracy VLM engine using NVIDIA GPU.")
        else:
            self._radio_vlm.setStyleSheet(radio_disabled_style)
            self._radio_vlm.setEnabled(False)
            self._radio_vlm.setToolTip("Requires an NVIDIA GPU with CUDA support.")

        vlm_row.addWidget(self._radio_vlm)

        if not self._has_cuda:
            gpu_note = QtWidgets.QLabel("Requires NVIDIA GPU")
            gpu_note.setStyleSheet(
                "color: #777777; background-color: transparent; "
                "font-size: 10px; font-style: italic;"
            )
            vlm_row.addWidget(gpu_note)

        vlm_row.addStretch()
        engine_layout.addLayout(vlm_row)

        # Set current selection
        current_type = self._ocr_manager.active_engine_type
        if current_type == EngineType.VLM and self._has_cuda:
            self._radio_vlm.setChecked(True)
        else:
            self._radio_lightweight.setChecked(True)

        self._engine_button_group.idToggled.connect(self._on_engine_radio_toggled)

        # Engine loading status
        self._current_engine_status = ""
        status_row = QtWidgets.QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(6)

        self._engine_spinner = SpinnerWidget(size=14, color="#5599FF")
        status_row.addWidget(self._engine_spinner)

        self._engine_status_label = QtWidgets.QLabel("Not loaded — will load on first scan")
        self._engine_status_label.setStyleSheet(
            "color: #888888; background-color: transparent; font-size: 10px;"
        )
        status_row.addWidget(self._engine_status_label)
        status_row.addStretch()
        engine_layout.addLayout(status_row)

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

        # ── Section 3: Translation Frequency ──
        freq_section = self._create_section("Automatic Translation Frequency")
        freq_layout = freq_section.layout()

        freq_row = QtWidgets.QHBoxLayout()
        freq_row.setContentsMargins(0, 0, 0, 0)
        freq_row.setSpacing(6)

        scan_label = QtWidgets.QLabel("Scan every")
        scan_label.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; font-size: 11px;"
        )
        freq_row.addWidget(scan_label)

        self.interval_spinbox = QtWidgets.QSpinBox()
        self.interval_spinbox.setRange(50, 10000)
        self.interval_spinbox.setValue(100)
        self.interval_spinbox.setSuffix("")
        self.interval_spinbox.setToolTip(
            "How often the translation pipeline scans for new text.\n"
            "Lower = faster updates but more CPU/GPU usage.\n"
            "Minimum: 50ms, Maximum: 10000ms"
        )
        self.interval_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #1A1A1A;
                color: #EEEEEE;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                min-width: 70px;
            }
            QSpinBox:focus {
                border-color: #5599FF;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #2A2A2A;
                border: 1px solid #404040;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #3A3A3A;
            }
            QSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #AAAAAA;
                width: 0px; height: 0px;
            }
            QSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #AAAAAA;
                width: 0px; height: 0px;
            }
        """)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        freq_row.addWidget(self.interval_spinbox)

        ms_label = QtWidgets.QLabel("ms")
        ms_label.setStyleSheet(
            "color: #CCCCCC; background-color: transparent; font-size: 11px;"
        )
        freq_row.addWidget(ms_label)

        freq_row.addStretch()
        freq_layout.addLayout(freq_row)
        layout.addWidget(freq_section)

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

    def _on_engine_radio_toggled(self, button_id: int, checked: bool) -> None:
        if not checked:
            return
        self.engine_changed.emit(button_id)
        # Update preprocessing checkbox for new engine
        from ocr.manager import EngineType
        try:
            etype = EngineType(button_id)
            self._ocr_manager.set_engine(etype)
            self.preprocess_check.setChecked(self._ocr_manager.should_preprocess)
        except Exception:
            pass

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

    def _on_preprocess_toggled(self, checked: bool) -> None:
        self._ocr_manager.should_preprocess = checked
        self.preprocess_toggled.emit(self._ocr_manager.active_engine_type.value, checked)

    def _on_interval_changed(self, value: int) -> None:
        self.interval_changed.emit(value)

    def set_interval(self, value: int) -> None:
        """Set the interval spinbox value (used when loading saved preferences)."""
        self.interval_spinbox.setValue(value)

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

    def set_engine_status(self, status: str) -> None:
        """Update the engine loading status display.

        Args:
            status: One of 'not_loaded', 'loading', or 'loaded'.
        """
        if status == self._current_engine_status:
            return
        self._current_engine_status = status

        if status == "loading":
            self._engine_spinner.start()
            self._engine_status_label.setText("Loading model...")
            self._engine_status_label.setStyleSheet(
                "color: #FFB347; background-color: transparent; font-size: 10px;"
            )
        elif status == "loaded":
            self._engine_spinner.stop()
            self._engine_status_label.setText("Model loaded")
            self._engine_status_label.setStyleSheet(
                "color: #7BC67E; background-color: transparent; font-size: 10px;"
            )
        else:
            self._engine_spinner.stop()
            self._engine_status_label.setText("Not loaded \u2014 will load on first scan")
            self._engine_status_label.setStyleSheet(
                "color: #888888; background-color: transparent; font-size: 10px;"
            )

    def set_overlay_colors(self, bg_color: str, text_color: str) -> None:
        """Set the color swatches to reflect saved preferences."""
        self.bg_color_swatch.set_color(bg_color)
        self.text_color_swatch.set_color(text_color)

    def _pick_bg_color(self) -> None:
        """Open color picker for overlay background color."""
        current = QtGui.QColor(self.bg_color_swatch.color)
        color = QtWidgets.QColorDialog.getColor(
            current, None, "Overlay Background Color",
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
            current, None, "Overlay Text Color",
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
