"""Lightweight manga-ocr engine for Japanese text recognition."""

from __future__ import annotations

from PIL import Image

from ocr.base import OCREngine, OCRResult


class MangaOCREngine(OCREngine):
    """Lightweight OCR engine using manga-ocr (~400MB model)."""

    def __init__(self, device: str = "cpu", force_cpu: bool = False):
        super().__init__()
        self._device = device
        self._force_cpu = force_cpu
        self._mocr = None

    @property
    def name(self) -> str:
        return "manga-ocr (Lightweight)"

    @property
    def requires_gpu(self) -> bool:
        return False

    def load(self) -> None:
        try:
            from manga_ocr import MangaOcr
        except ImportError:
            raise ImportError(
                "manga-ocr is not installed. Run: pip install manga-ocr"
            )

        device = self._device
        if device == "auto":
            if self._force_cpu:
                device = "cpu"
            else:
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"

        self._mocr = MangaOcr(force_cpu=(device == "cpu"))
        self._is_loaded = True
        print(f"[OCR] manga-ocr loaded on {device}")

    def _recognize(self, image: Image.Image) -> OCRResult:
        if self._mocr is None:
            return OCRResult()
        text = self._mocr(image)
        return OCRResult(text=text.strip() if text else "", confidence=1.0)

    def unload(self) -> None:
        self._mocr = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        super().unload()
