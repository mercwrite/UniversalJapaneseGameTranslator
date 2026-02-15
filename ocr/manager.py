"""Central OCR manager for engine selection and preprocessing."""

from __future__ import annotations

import time
from enum import IntEnum

from PIL import Image

from ocr.base import OCREngine, OCRResult
from ocr.preprocessing import PreprocessingPipeline


class EngineType(IntEnum):
    LIGHTWEIGHT = 0
    VLM = 1


class OCRManager:
    """Coordinates OCR engine selection and preprocessing pipeline."""

    def __init__(self):
        self._engines: dict[EngineType, OCREngine] = {}
        self._active_engine_type: EngineType = EngineType.LIGHTWEIGHT
        self._pipeline = PreprocessingPipeline()
        self._preprocess_by_engine: dict[EngineType, bool] = {
            EngineType.LIGHTWEIGHT: True,
            EngineType.VLM: False,
        }

    def register_engine(self, engine_type: EngineType, engine: OCREngine) -> None:
        self._engines[engine_type] = engine

    def set_engine(self, engine_type: EngineType) -> None:
        if engine_type not in self._engines:
            raise ValueError(f"Engine type {engine_type.name} is not registered")
        self._active_engine_type = engine_type

    @property
    def active_engine(self) -> OCREngine:
        return self._engines[self._active_engine_type]

    @property
    def active_engine_type(self) -> EngineType:
        return self._active_engine_type

    @property
    def pipeline(self) -> PreprocessingPipeline:
        return self._pipeline

    @pipeline.setter
    def pipeline(self, value: PreprocessingPipeline) -> None:
        self._pipeline = value

    @property
    def should_preprocess(self) -> bool:
        return self._preprocess_by_engine.get(self._active_engine_type, True)

    @should_preprocess.setter
    def should_preprocess(self, value: bool) -> None:
        self._preprocess_by_engine[self._active_engine_type] = value

    def available_engines(self) -> list[tuple[EngineType, str, bool]]:
        """Returns (type, name, requires_gpu) for all registered engines."""
        result = []
        for etype, engine in self._engines.items():
            result.append((etype, engine.name, engine.requires_gpu))
        return result

    def process(self, image: Image.Image) -> OCRResult:
        """Run preprocessing (if applicable) then OCR."""
        processed = image
        if self.should_preprocess:
            t0 = time.perf_counter()
            processed = self._pipeline.process(image)
            preprocess_ms = (time.perf_counter() - t0) * 1000
            print(f"[Preprocess] {preprocess_ms:.0f}ms")

        result = self.active_engine.recognize(processed)
        result.preprocessed = self.should_preprocess
        return result

    def process_with_preview(self, image: Image.Image) -> tuple[OCRResult, Image.Image]:
        """Run preprocessing + OCR, returning both the result and preprocessed image."""
        processed = self._pipeline.process(image)
        result = self.active_engine.recognize(processed)
        result.preprocessed = True
        return result, processed

    def unload_all(self) -> None:
        """Unload all registered engines."""
        for etype, engine in self._engines.items():
            try:
                engine.unload()
            except Exception as e:
                print(f"Warning: Failed to unload {engine.name}: {e}")
