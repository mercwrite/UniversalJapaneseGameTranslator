"""Translation pipeline: image diff detection, OCR, and translation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from PyQt6 import QtWidgets
from error_handler import safe_execute, SafeWindowCapture, validate_region_data

if TYPE_CHECKING:
    from capture.window_capture import WindowCapture
    from ocr.manager import OCRManager
    from translation.sugoi_wrapper import SugoiTranslator
    from perf_logger import PerformanceLogger


class TranslationPipeline:
    """Runs the OCR + translation pipeline over active overlay regions."""

    def __init__(
        self,
        win_cap: WindowCapture,
        ocr_manager: OCRManager | None,
        translator: SugoiTranslator | None,
        perf: PerformanceLogger,
    ):
        self.win_cap = win_cap
        self.ocr_manager = ocr_manager
        self.translator = translator
        self.perf = perf

    @staticmethod
    @safe_execute(default_return=1000.0, log_errors=False, error_message="Failed to calculate image diff")
    def calculate_image_diff(img1, img2) -> float:
        """
        Returns a 'difference score' between two images.
        0 = Identical. Higher numbers = more different.
        """
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

    @safe_execute(default_return=None, log_errors=True, error_message="Pipeline error")
    def run(
        self,
        active_regions: dict[str, dict],
        last_images: dict[str, np.ndarray],
        is_region_enabled_fn,
    ) -> None:
        """Run OCR on all active regions.

        Args:
            active_regions: dict mapping region_id to region data dicts.
            last_images: dict mapping region_id to last-seen PIL images
                         (mutated in-place when a new image is processed).
            is_region_enabled_fn: callable(region_id) -> bool.
        """
        if not active_regions:
            return

        if not self.win_cap or not SafeWindowCapture.is_window_valid(self.win_cap.hwnd):
            return

        if not self.ocr_manager or not self.translator:
            return

        self.perf.start_cycle()

        full_window_img = self.win_cap.screenshot()
        if not SafeWindowCapture.validate_image(full_window_img):
            return

        win_x, win_y, win_w, win_h = self.win_cap.get_window_rect()
        if win_w <= 0 or win_h <= 0:
            return

        for rid, data in list(active_regions.items()):
            overlay = data.get("overlay")
            translating = False
            try:
                if not is_region_enabled_fn(rid):
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

                last_img = last_images.get(rid)
                diff_score = self.calculate_image_diff(current_crop, last_img)

                if diff_score < 2.0:
                    continue

                last_images[rid] = current_crop

                # Show spinner on overlay before OCR/translation
                if overlay:
                    overlay.set_translating(True)
                    translating = True
                    QtWidgets.QApplication.processEvents()

                try:
                    self.perf.start_ocr()
                    ocr_result = self.ocr_manager.process(current_crop)
                    if ocr_result.is_empty:
                        continue
                    jap_text = ocr_result.text
                    print(f"[OCR] {ocr_result.engine_name}: {ocr_result.processing_time_ms:.0f}ms")
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
                    if overlay:
                        overlay.update_text(eng_text)
                except Exception:
                    pass

            except Exception:
                continue
            finally:
                if translating and overlay:
                    overlay.set_translating(False)
