"""Preprocessing pipeline editor with live preview and dynamic step controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6 import QtWidgets, QtCore, QtGui
from PIL import Image

from ocr.preprocessing import PreprocessingStep, PreprocessingPipeline, StepType, ParamSpec
from ui.widgets import ModernComboBox, IconButton

if TYPE_CHECKING:
    from ocr.manager import OCRManager


class StepEditorWidget(QtWidgets.QWidget):
    """Editable UI for a single preprocessing step with collapsible parameters."""

    def __init__(self, step: PreprocessingStep, on_change_callback: Callable, parent=None):
        super().__init__(parent)
        self._step = step
        self._on_change = on_change_callback
        self._is_expanded = False
        self._param_controls: dict[str, QtWidgets.QWidget] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header row ──
        header = QtWidgets.QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 6px;
            }
        """)
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(8)

        # Enable checkbox
        self.enable_check = QtWidgets.QCheckBox()
        self.enable_check.setChecked(self._step.enabled)
        self.enable_check.setFixedWidth(20)
        self.enable_check.setStyleSheet(
            "QCheckBox { background-color: transparent; border: none; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self.enable_check.toggled.connect(self._on_enable_toggled)
        header_layout.addWidget(self.enable_check)

        # Step name
        name = self._step.step_type.name.replace("_", " ").title()
        name_label = QtWidgets.QLabel(name)
        name_label.setStyleSheet(
            "color: #EEEEEE; background-color: transparent; "
            "font-weight: 500; font-size: 12px; border: none;"
        )
        header_layout.addWidget(name_label, 1)

        # Expand/collapse button
        self.expand_btn = IconButton("chevron-right", size=24)
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
        """)
        self.expand_btn.clicked.connect(self.toggle_expand)
        header_layout.addWidget(self.expand_btn)

        header.setLayout(header_layout)
        layout.addWidget(header)

        # ── Params area (collapsible) ──
        self.params_widget = QtWidgets.QWidget()
        self.params_widget.setStyleSheet("""
            QWidget {
                background-color: #151515;
                border: 1px solid #2A2A2A;
                border-top: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)
        params_layout = QtWidgets.QVBoxLayout()
        params_layout.setContentsMargins(24, 10, 16, 14)
        params_layout.setSpacing(10)

        specs = PreprocessingStep.get_param_specs(self._step.step_type)
        for spec in specs:
            control_row = self._create_param_control(spec)
            if control_row is not None:
                params_layout.addLayout(control_row) if isinstance(
                    control_row, QtWidgets.QLayout
                ) else params_layout.addWidget(control_row)

        self.params_widget.setLayout(params_layout)
        self.params_widget.hide()
        layout.addWidget(self.params_widget)

        self.setLayout(layout)

    def _create_param_control(self, spec: ParamSpec):
        """Create the appropriate control widget for a parameter spec."""
        current_val = self._step.params.get(spec.name, spec.default)

        if spec.type == "bool":
            check = QtWidgets.QCheckBox(spec.label)
            check.setChecked(bool(current_val))
            check.setStyleSheet(
                "color: #CCCCCC; background-color: transparent; "
                "font-size: 11px; border: none;"
            )
            if spec.tooltip:
                check.setToolTip(spec.tooltip)
            check.toggled.connect(
                lambda val, n=spec.name: self._update_param(n, val)
            )
            self._param_controls[spec.name] = check
            return check

        elif spec.type == "choice":
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(12)

            label = QtWidgets.QLabel(spec.label)
            label.setMinimumWidth(90)
            label.setStyleSheet(
                "color: #AAAAAA; background-color: transparent; "
                "font-size: 11px; border: none;"
            )
            row.addWidget(label)

            combo = ModernComboBox()
            combo.setFixedHeight(24)
            if spec.choices:
                combo.addItems(spec.choices)
                idx = spec.choices.index(current_val) if current_val in spec.choices else 0
                combo.setCurrentIndex(idx)
            if spec.tooltip:
                combo.setToolTip(spec.tooltip)
            combo.currentTextChanged.connect(
                lambda val, n=spec.name: self._update_param(n, val)
            )
            self._param_controls[spec.name] = combo
            row.addWidget(combo, 1)
            return row

        elif spec.type in ("int", "float"):
            row = QtWidgets.QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(12)

            label = QtWidgets.QLabel(spec.label)
            label.setMinimumWidth(90)
            label.setStyleSheet(
                "color: #AAAAAA; background-color: transparent; "
                "font-size: 11px; border: none;"
            )
            row.addWidget(label)

            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setFixedHeight(22)
            slider.setStyleSheet("background-color: transparent; border: none;")

            # For float, multiply by precision factor
            if spec.type == "float":
                step_val = spec.step if spec.step else 0.1
                precision = max(1, round(1.0 / step_val))
                s_min = int((spec.min_val or 0) * precision)
                s_max = int((spec.max_val or 1) * precision)
                s_val = int(float(current_val) * precision)
                slider.setRange(s_min, s_max)
                slider.setValue(s_val)

                val_label = QtWidgets.QLabel(f"{float(current_val):.1f}")
                val_label.setStyleSheet(
                    "color: #AAAAAA; background-color: transparent; "
                    "min-width: 35px; font-size: 11px; border: none;"
                )
                val_label.setAlignment(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )

                def on_float_change(v, n=spec.name, p=precision, lbl=val_label):
                    real_val = v / p
                    lbl.setText(f"{real_val:.1f}")
                    self._update_param(n, real_val)

                slider.valueChanged.connect(on_float_change)
            else:
                s_min = int(spec.min_val) if spec.min_val is not None else 0
                s_max = int(spec.max_val) if spec.max_val is not None else 100
                s_step = int(spec.step) if spec.step else 1
                slider.setRange(s_min, s_max)
                slider.setSingleStep(s_step)
                slider.setValue(int(current_val))

                val_label = QtWidgets.QLabel(str(int(current_val)))
                val_label.setStyleSheet(
                    "color: #AAAAAA; background-color: transparent; "
                    "min-width: 35px; font-size: 11px; border: none;"
                )
                val_label.setAlignment(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )

                def on_int_change(v, n=spec.name, lbl=val_label):
                    lbl.setText(str(v))
                    self._update_param(n, v)

                slider.valueChanged.connect(on_int_change)

            if spec.tooltip:
                slider.setToolTip(spec.tooltip)

            self._param_controls[spec.name] = slider
            row.addWidget(slider, 1)
            row.addWidget(val_label)
            return row

        return None

    def _update_param(self, name: str, value) -> None:
        self._step.params[name] = value
        self._on_change()

    def _on_enable_toggled(self, checked: bool) -> None:
        self._step.enabled = checked
        self._on_change()

    def toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded
        self.params_widget.setVisible(self._is_expanded)
        self.expand_btn.icon_type = "chevron-right" if not self._is_expanded else "chevron-left"
        self.expand_btn.update()

    def update_from_step(self) -> None:
        """Re-read step state and update all controls."""
        self.enable_check.blockSignals(True)
        self.enable_check.setChecked(self._step.enabled)
        self.enable_check.blockSignals(False)

        specs = PreprocessingStep.get_param_specs(self._step.step_type)
        for spec in specs:
            control = self._param_controls.get(spec.name)
            if control is None:
                continue
            val = self._step.params.get(spec.name, spec.default)
            control.blockSignals(True)
            if isinstance(control, QtWidgets.QCheckBox):
                control.setChecked(bool(val))
            elif isinstance(control, ModernComboBox):
                idx = control.findText(str(val))
                if idx >= 0:
                    control.setCurrentIndex(idx)
            elif isinstance(control, QtWidgets.QSlider):
                if spec.type == "float":
                    step_v = spec.step if spec.step else 0.1
                    precision = max(1, round(1.0 / step_v))
                    control.setValue(int(float(val) * precision))
                else:
                    control.setValue(int(val))
            control.blockSignals(False)


class PreprocessingEditorWidget(QtWidgets.QWidget):
    """Full preprocessing pipeline editor with live preview."""

    def __init__(
        self,
        ocr_manager: OCRManager,
        capture_callback: Callable | None = None,
        get_regions_callback: Callable | None = None,
        on_pipeline_changed: Callable | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._ocr_manager = ocr_manager
        self._capture_callback = capture_callback  # Callable[[str], Image | None]
        self._get_regions = get_regions_callback    # Callable[[], list[tuple[str, str]]]
        self._on_pipeline_changed = on_pipeline_changed  # Callable[[], None]
        self._preview_image: Image.Image | None = None
        self._step_editors: list[StepEditorWidget] = []

        # Debounce timer for preview refresh
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(12)

        # ── Preview area ──
        preview_container = QtWidgets.QWidget()
        preview_container.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
                border: 1px solid #404040;
                border-radius: 8px;
            }
        """)
        preview_layout = QtWidgets.QVBoxLayout()
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(10)

        # Processed preview image
        self.preview_processed = QtWidgets.QLabel("No preview")
        self.preview_processed.setMinimumHeight(160)
        self.preview_processed.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_processed.setStyleSheet(
            "background-color: #0D0D0D; color: #666666; "
            "border-radius: 6px; border: 1px solid #333333; font-size: 11px;"
        )
        self.preview_processed.setScaledContents(False)
        preview_layout.addWidget(self.preview_processed)

        # Overlay selector row
        overlay_select_row = QtWidgets.QHBoxLayout()
        overlay_select_row.setSpacing(8)

        overlay_label = QtWidgets.QLabel("Region:")
        overlay_label.setStyleSheet(
            "color: #AAAAAA; background-color: transparent; "
            "font-size: 11px; border: none;"
        )
        overlay_select_row.addWidget(overlay_label)

        self.overlay_combo = ModernComboBox()
        self.overlay_combo.setFixedHeight(28)
        self.overlay_combo.setStyleSheet("""
            QComboBox {
                background-color: #1A1A1A;
                color: #CCCCCC;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        self.overlay_combo.addItem("No overlays", "")
        overlay_select_row.addWidget(self.overlay_combo, 1)

        preview_layout.addLayout(overlay_select_row)

        # Capture button
        btn_capture = QtWidgets.QPushButton("Capture")
        btn_capture.setFixedHeight(26)
        btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                color: #CCCCCC;
                border: 1px solid #505050;
                border-radius: 6px;
                padding: 2px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #606060;
            }
        """)
        btn_capture.setToolTip("Capture the selected overlay region")
        btn_capture.clicked.connect(self._capture_preview_image)
        preview_layout.addWidget(btn_capture)

        preview_container.setLayout(preview_layout)
        layout.addWidget(preview_container)

        # ── Steps list ──
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        self.steps_container = QtWidgets.QWidget()
        self.steps_layout = QtWidgets.QVBoxLayout()
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(4)
        self.steps_container.setLayout(self.steps_layout)
        scroll.setWidget(self.steps_container)

        layout.addWidget(scroll, 1)

        # Reset button
        btn_reset = QtWidgets.QPushButton("Reset to Defaults")
        btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                color: #CCCCCC;
                border: 1px solid #505050;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #353535;
                border-color: #606060;
            }
        """)
        btn_reset.clicked.connect(self._reset_to_defaults)
        layout.addWidget(btn_reset)

        self.setLayout(layout)

        # Build initial step editors
        self._build_step_editors()

    def _build_step_editors(self) -> None:
        """Create step editor widgets from the current pipeline."""
        # Clear existing
        for editor in self._step_editors:
            self.steps_layout.removeWidget(editor)
            editor.deleteLater()
        self._step_editors.clear()

        for step in self._ocr_manager.pipeline.steps:
            editor = StepEditorWidget(step, on_change_callback=self._on_param_changed)
            self.steps_layout.addWidget(editor)
            self._step_editors.append(editor)

        self.steps_layout.addStretch()

    def _on_param_changed(self) -> None:
        """Debounced callback when any step parameter changes."""
        self._preview_timer.start()
        if self._on_pipeline_changed:
            self._on_pipeline_changed()

    def _refresh_preview(self) -> None:
        """Run preprocessing on the preview image and update display."""
        if self._preview_image is None:
            return
        try:
            processed = self._ocr_manager.pipeline.process(self._preview_image)
            self._set_preview_pixmap(self.preview_processed, processed)
        except Exception as e:
            self.preview_processed.setText(f"Error: {e}")

    def _capture_preview_image(self) -> None:
        """Capture the overlay region selected in the combo box."""
        if self._capture_callback is None:
            self.preview_processed.setText("No capture callback")
            return
        region_id = self.overlay_combo.currentData()
        if not region_id:
            self.preview_processed.setText("No overlay selected")
            return
        try:
            img = self._capture_callback(region_id)
            if img is None:
                self.preview_processed.setText("Capture failed")
                return
            self._preview_image = img.convert("RGB")
            self._refresh_preview()
        except Exception as e:
            self.preview_processed.setText(f"Capture error: {e}")

    def refresh_overlay_list(self) -> None:
        """Refresh the overlay selector combo from the current active regions."""
        if self._get_regions is None:
            return
        try:
            regions = self._get_regions()
        except Exception:
            return

        self.overlay_combo.blockSignals(True)
        prev_id = self.overlay_combo.currentData()
        self.overlay_combo.clear()
        if not regions:
            self.overlay_combo.addItem("No overlays", "")
        else:
            restore_idx = 0
            for i, (rid, name) in enumerate(regions):
                self.overlay_combo.addItem(name, rid)
                if rid == prev_id:
                    restore_idx = i
            self.overlay_combo.setCurrentIndex(restore_idx)
        self.overlay_combo.blockSignals(False)

    def _reset_to_defaults(self) -> None:
        """Reset pipeline to default steps."""
        self._ocr_manager.pipeline = PreprocessingPipeline()
        self._build_step_editors()
        self._refresh_preview()
        if self._on_pipeline_changed:
            self._on_pipeline_changed()

    @staticmethod
    def _pil_to_qpixmap(image: Image.Image, max_size: int = 360) -> QtGui.QPixmap:
        """Convert PIL image to QPixmap, scaling down if needed."""
        # Handle grayscale
        if image.mode == "L":
            arr_bytes = image.tobytes()
            qimg = QtGui.QImage(
                arr_bytes, image.width, image.height,
                image.width,
                QtGui.QImage.Format.Format_Grayscale8,
            )
        elif image.mode in ("RGB", "RGBA"):
            if image.mode == "RGBA":
                fmt = QtGui.QImage.Format.Format_RGBA8888
                bpl = image.width * 4
            else:
                fmt = QtGui.QImage.Format.Format_RGB888
                bpl = image.width * 3
            arr_bytes = image.tobytes()
            qimg = QtGui.QImage(arr_bytes, image.width, image.height, bpl, fmt)
        else:
            image = image.convert("RGB")
            arr_bytes = image.tobytes()
            qimg = QtGui.QImage(
                arr_bytes, image.width, image.height,
                image.width * 3,
                QtGui.QImage.Format.Format_RGB888,
            )

        pixmap = QtGui.QPixmap.fromImage(qimg)
        if pixmap.width() > max_size or pixmap.height() > max_size:
            pixmap = pixmap.scaled(
                max_size, max_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        return pixmap

    def _set_preview_pixmap(self, label: QtWidgets.QLabel, image: Image.Image) -> None:
        """Set a PIL image onto a QLabel as a pixmap."""
        try:
            pixmap = self._pil_to_qpixmap(image, max_size=360)
            label.setPixmap(pixmap)
        except Exception as e:
            label.setText(f"Display error: {e}")
