"""Abstract OCR engine interface and result dataclass."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class OCRResult:
    """Result from an OCR engine."""

    text: str = ""
    confidence: float = 0.0
    engine_name: str = ""
    processing_time_ms: float = 0.0
    preprocessed: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.text or not self.text.strip()


class OCREngine(ABC):
    """Abstract base class for OCR engines."""

    def __init__(self):
        self._is_loaded = False
        self._load_time_ms: float = 0.0

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name for UI display."""
        ...

    @property
    @abstractmethod
    def requires_gpu(self) -> bool:
        """Whether this engine needs a CUDA GPU."""
        ...

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @abstractmethod
    def load(self) -> None:
        """Load model weights / initialize engine. Must set self._is_loaded = True."""
        ...

    @abstractmethod
    def _recognize(self, image: Image.Image) -> OCRResult:
        """Internal OCR on a single PIL image."""
        ...

    def recognize(self, image: Image.Image) -> OCRResult:
        """Run OCR, auto-loading the engine if needed."""
        if not self._is_loaded:
            t0 = time.perf_counter()
            self.load()
            self._load_time_ms = (time.perf_counter() - t0) * 1000
            print(f"[OCR] {self.name} loaded in {self._load_time_ms:.0f}ms")

        t0 = time.perf_counter()
        result = self._recognize(image)
        result.processing_time_ms = (time.perf_counter() - t0) * 1000
        result.engine_name = self.name
        return result

    def unload(self) -> None:
        """Release resources. Subclasses override for cleanup."""
        self._is_loaded = False
