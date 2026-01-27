import sys
import uuid

import numpy as np
from PyQt6 import QtWidgets, QtCore

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


class ControllerWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay Manager")
        self.resize(400, 400)

        # Data storage:
        # { 'uuid_string': { 'rect': dict, 'overlay': TextBoxOverlay } }
        self.active_regions: dict[str, dict] = {}
        self.last_images: dict[str, "np.ndarray"] = {}

        # --- UI Layout ---
        layout = QtWidgets.QVBoxLayout()

        slider_layout = QtWidgets.QHBoxLayout()

        self.lbl_opacity = QtWidgets.QLabel("Background Opacity: 80%")
        slider_layout.addWidget(self.lbl_opacity)

        self.slider_opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 255)  # 0 = Invisible, 255 = Solid
        self.slider_opacity.setValue(200)  # Default start value (~80%)
        self.slider_opacity.valueChanged.connect(self.update_opacity)
        slider_layout.addWidget(self.slider_opacity)

        layout.addLayout(slider_layout)

        # List of active regions
        self.region_list = QtWidgets.QListWidget()
        self.region_list.itemChanged.connect(self.on_region_checkbox_changed)
        layout.addWidget(self.region_list)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()

        self.btn_add = QtWidgets.QPushButton("Add New Region")
        self.btn_add.clicked.connect(self.activate_snipper)
        btn_layout.addWidget(self.btn_add)

        self.btn_del = QtWidgets.QPushButton("Delete Selected")
        self.btn_del.clicked.connect(self.delete_region)
        btn_layout.addWidget(self.btn_del)

        layout.addLayout(btn_layout)

        self.btn_start = QtWidgets.QPushButton("Start Translation")
        self.btn_start.setCheckable(True)
        self.btn_start.clicked.connect(self.toggle_translation)
        layout.addWidget(self.btn_start)

        self.win_cap = WindowCapture()

        self.perf = PerformanceLogger()
        self.lbl_perf = QtWidgets.QLabel("Last Cycle: 0ms")
        self.lbl_perf.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.lbl_perf)

        # Game selection
        self.combo_games = QtWidgets.QComboBox()
        self.combo_games.addItems(self.win_cap.list_window_names())
        self.combo_games.currentIndexChanged.connect(self.select_game_window)
        layout.addWidget(QtWidgets.QLabel("Select Game Window:"))
        layout.addWidget(self.combo_games)

        # Refresh button (games might open after this app)
        btn_refresh = QtWidgets.QPushButton("Refresh Window List")
        btn_refresh.clicked.connect(self.refresh_window_list)
        layout.addWidget(btn_refresh)

        self.setLayout(layout)

        # --- Backend ---
        path_to_model = "sugoi_model"
        self.vision_ai = None
        self.translator = None
        self._initialize_backend(path_to_model)
        
        self.timer = QtCore.QTimer()
        self.timer.setInterval(100)  # ms
        self.timer.timeout.connect(self.run_batch_pipeline)
    
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
    def update_opacity(self) -> None:
        try:
            current_val = self.slider_opacity.value()  # 0-255
            self.lbl_opacity.setText(
                f"Background Opacity: {int(current_val / 255 * 100)}%"
            )

            # Only update opacity for enabled overlays
            for rid, data in list(self.active_regions.items()):  # Use list() to avoid modification during iteration
                try:
                    if self.is_region_enabled(rid) and "overlay" in data:
                        overlay = data["overlay"]
                        if overlay:
                            overlay.set_background_opacity(current_val)
                except Exception:
                    continue  # Skip problematic overlays
        except Exception:
            pass  # Already handled by decorator

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to refresh window list")
    def refresh_window_list(self) -> None:
        try:
            current = self.combo_games.currentText()
            self.combo_games.clear()
            window_names = self.win_cap.list_window_names()
            if window_names:
                self.combo_games.addItems(window_names)
                # Try to restore selection, but don't fail if it doesn't exist
                try:
                    self.combo_games.setCurrentText(current)
                except Exception:
                    pass
        except Exception:
            pass  # Already handled by decorator

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to select game window")
    def select_game_window(self) -> None:
        try:
            title = self.combo_games.currentText()
            if title:
                self.win_cap.set_window_by_title(title)
        except Exception:
            pass  # Already handled by decorator

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to activate snipper")
    def activate_snipper(self) -> None:
        try:
            self.hide()  # Hide controller
            self.snipper = Snipper()
            self.snipper.region_selected.connect(self.on_region_added)
            self.snipper.show()
        except Exception:
            self.show()  # Show controller again on error
            raise

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to add region")
    def on_region_added(self, area: dict) -> None:
        try:
            self.show()  # Show controller

            # Validate region data
            if not validate_region_data(area):
                print("Invalid region data provided")
                return

            # Generate a unique ID
            region_id = str(uuid.uuid4())[:8]  # Short UUID

            # Create the overlay window immediately
            try:
                overlay = TextBoxOverlay(
                    area["left"],
                    area["top"],
                    area["width"],
                    area["height"],
                    initial_opacity=self.slider_opacity.value(),
                )
            except Exception as e:
                print(f"Failed to create overlay: {e}")
                return

            # Connect geometry changed signal to update stored data
            try:
                overlay.geometry_changed.connect(
                    lambda x, y, w, h, rid=region_id: self.on_overlay_geometry_changed(rid, x, y, w, h)
                )
            except Exception:
                pass  # Connection might fail if overlay is deleted

            # Store the data
            self.active_regions[region_id] = {
                "rect": area,
                "overlay": overlay,
            }

            # Add to list widget for management
            try:
                item_text = f"Region {region_id} - ({area['width']}x{area['height']})"
                list_item = QtWidgets.QListWidgetItem(item_text)
                list_item.setData(QtCore.Qt.ItemDataRole.UserRole, region_id)
                list_item.setCheckState(QtCore.Qt.CheckState.Checked)  # Enabled by default
                self.region_list.addItem(list_item)
            except Exception as e:
                print(f"Failed to add item to list: {e}")
                # Clean up overlay if list addition fails
                try:
                    overlay.close()
                    del self.active_regions[region_id]
                except Exception:
                    pass
        except Exception:
            self.show()  # Ensure controller is visible
            raise

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to delete region")
    def delete_region(self) -> None:
        try:
            selected_items = self.region_list.selectedItems()
            if not selected_items:
                return

            for item in selected_items:
                if not item:
                    continue
                    
                try:
                    region_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    if not region_id:
                        continue

                    if region_id in self.active_regions:
                        try:
                            overlay = self.active_regions[region_id]["overlay"]
                            if overlay:
                                overlay.close()
                        except Exception:
                            pass  # Overlay might already be closed
                        del self.active_regions[region_id]
                    
                    # Clean up last image cache
                    if region_id in self.last_images:
                        del self.last_images[region_id]

                    # Remove from list
                    try:
                        row = self.region_list.row(item)
                        if row >= 0:
                            self.region_list.takeItem(row)
                    except Exception:
                        pass
                except Exception:
                    continue  # Continue with next item
        except Exception:
            pass  # Already handled by decorator

    def toggle_translation(self) -> None:
        if self.btn_start.isChecked():
            self.btn_start.setText("Stop Translation")
            self.timer.start()
        else:
            self.btn_start.setText("Start Translation")
            self.timer.stop()

    @safe_execute(default_return=False, log_errors=False, error_message="Failed to check region enabled state")
    def is_region_enabled(self, region_id: str) -> bool:
        """Check if a region is enabled (checkbox is checked)."""
        if not region_id or not self.region_list:
            return False
        try:
            for i in range(self.region_list.count()):
                item = self.region_list.item(i)
                if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == region_id:
                    return item.checkState() == QtCore.Qt.CheckState.Checked
        except Exception:
            pass
        return False

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to change checkbox state")
    def on_region_checkbox_changed(self, item: QtWidgets.QListWidgetItem) -> None:
        """Handle checkbox state changes for region items."""
        try:
            if not item:
                return
                
            region_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if not region_id or region_id not in self.active_regions:
                return

            is_enabled = item.checkState() == QtCore.Qt.CheckState.Checked
            overlay = self.active_regions[region_id].get("overlay")
            
            if not overlay:
                return

            if is_enabled:
                try:
                    overlay.show()
                    # Update opacity to match current slider value
                    overlay.set_background_opacity(self.slider_opacity.value())
                except Exception:
                    pass
            else:
                try:
                    overlay.hide()
                except Exception:
                    pass
        except Exception:
            pass  # Already handled by decorator

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to update geometry")
    def on_overlay_geometry_changed(
        self, region_id: str, x: int, y: int, width: int, height: int
    ) -> None:
        """Handle overlay position/size changes from user interaction."""
        try:
            if not region_id or region_id not in self.active_regions:
                return

            # Validate dimensions
            if width <= 0 or height <= 0 or width > 10000 or height > 10000:
                return

            # Update stored region data
            self.active_regions[region_id]["rect"] = {
                "left": x,
                "top": y,
                "width": width,
                "height": height,
            }

            # Update list widget text to reflect new dimensions
            try:
                for i in range(self.region_list.count()):
                    item = self.region_list.item(i)
                    if item and item.data(QtCore.Qt.ItemDataRole.UserRole) == region_id:
                        item.setText(f"Region {region_id} - ({width}x{height})")
                        break
            except Exception:
                pass  # UI update failure is not critical
        except Exception:
            pass  # Already handled by decorator

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
                return 1000.0  # Force update if no history

            if not SafeWindowCapture.validate_image(img1) or not SafeWindowCapture.validate_image(img2):
                return 1000.0

            # Ensure sizes match (handling resize edge cases)
            if img1.size != img2.size:
                return 1000.0

            # Convert to grayscale and then to NumPy array
            arr1 = np.array(img1.convert("L"), dtype=np.int16)
            arr2 = np.array(img2.convert("L"), dtype=np.int16)

            # Calculate absolute difference
            diff = np.abs(arr1 - arr2)

            # Return the mean difference (average change per pixel)
            return float(np.mean(diff))
        except Exception:
            return 1000.0  # Force update on error

    @safe_execute(default_return=None, log_errors=True, error_message="Pipeline error")
    def run_batch_pipeline(self) -> None:
        """Run OCR on all active regions."""
        try:
            # Validate prerequisites
            if not self.active_regions:
                return
            
            if not self.win_cap or not SafeWindowCapture.is_window_valid(self.win_cap.hwnd):
                return

            if not self.vision_ai or not self.translator:
                return

            self.perf.start_cycle()

            # Capture screenshot with error handling
            full_window_img = self.win_cap.screenshot()
            if not SafeWindowCapture.validate_image(full_window_img):
                return

            win_x, win_y, win_w, win_h = self.win_cap.get_window_rect()
            if win_w <= 0 or win_h <= 0:
                return

            # Process each region
            for rid, data in list(self.active_regions.items()):  # Use list() to avoid modification issues
                try:
                    # Skip disabled regions
                    if not self.is_region_enabled(rid):
                        continue

                    if "rect" not in data or "overlay" not in data:
                        continue

                    screen_rect = data["rect"]
                    if not validate_region_data(screen_rect):
                        continue

                    # Convert screen coords to relative window coords
                    rel_x = screen_rect["left"] - win_x
                    rel_y = screen_rect["top"] - win_y
                    rel_w = screen_rect["width"]
                    rel_h = screen_rect["height"]

                    # Safety checks: ensure crop is inside the window
                    if rel_x < 0 or rel_y < 0:
                        continue
                    if rel_x + rel_w > win_w or rel_y + rel_h > win_h:
                        continue
                    if rel_w <= 0 or rel_h <= 0:
                        continue

                    # Crop using Pillow
                    try:
                        current_crop = full_window_img.crop(
                            (rel_x, rel_y, rel_x + rel_w, rel_y + rel_h)
                        )
                        if not SafeWindowCapture.validate_image(current_crop):
                            continue
                    except Exception:
                        continue  # Skip invalid crops

                    # Check if image changed significantly
                    last_img = self.last_images.get(rid)
                    diff_score = self.calculate_image_diff(current_crop, last_img)

                    if diff_score < 2.0:
                        continue

                    self.last_images[rid] = current_crop

                    # OCR with error handling
                    try:
                        self.perf.start_ocr()
                        jap_text = self.vision_ai.analyze(current_crop, mode="ocr")
                        if not jap_text or not isinstance(jap_text, str):
                            continue
                    except Exception as e:
                        print(f"OCR error for region {rid}: {e}")
                        continue

                    # Translate with error handling
                    try:
                        self.perf.start_translation()
                        eng_text = self.translator.translate(jap_text)
                        if not eng_text or not isinstance(eng_text, str):
                            eng_text = "Translation error"
                    except Exception as e:
                        print(f"Translation error for region {rid}: {e}")
                        eng_text = "Translation error"

                    # Update performance stats
                    try:
                        stats = self.perf.end_cycle()
                        print(
                            f"[PERF] OCR: {stats['ocr_ms']}ms | "
                            f"Trans: {stats['trans_ms']}ms | "
                            f"Total: {stats['total_ms']}ms"
                        )
                        self.lbl_perf.setText(
                            f"Speed: {stats['total_ms']}ms "
                            f"(OCR: {stats['ocr_ms']} | Trans: {stats['trans_ms']})"
                        )
                    except Exception:
                        pass  # Performance logging failure is not critical

                    # Update the overlay object's text
                    try:
                        overlay = data.get("overlay")
                        if overlay:
                            overlay.update_text(eng_text)
                    except Exception:
                        pass  # Overlay update failure is not critical

                except Exception:
                    continue  # Continue processing other regions on error

        except Exception:
            pass  # Already handled by decorator


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())


