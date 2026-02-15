"""Adapter for existing Qwen VLM OCR engine."""

from __future__ import annotations

from PIL import Image

from ocr.base import OCREngine, OCRResult


class QwenVLMEngine(OCREngine):
    """Thin adapter around the existing qwen_wrapper.LocalVisionAI."""

    def __init__(self):
        super().__init__()
        self._vlm = None

    @property
    def name(self) -> str:
        return "Qwen VLM (High Accuracy)"

    @property
    def requires_gpu(self) -> bool:
        return True

    def load(self) -> None:
        from ocr.qwen_wrapper import LocalVisionAI
        self._vlm = LocalVisionAI()
        self._is_loaded = True

    def _recognize(self, image: Image.Image) -> OCRResult:
        if self._vlm is None:
            return OCRResult()
        text = self._vlm.analyze(image, mode="ocr")
        return OCRResult(text=text.strip() if text else "", confidence=1.0)

    def unload(self) -> None:
        self._vlm = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        super().unload()
