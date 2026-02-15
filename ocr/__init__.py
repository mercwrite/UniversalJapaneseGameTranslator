"""OCR engine package."""

from ocr.qwen_wrapper import LocalVisionAI
from ocr.base import OCREngine, OCRResult
from ocr.manager import OCRManager, EngineType
from ocr.preprocessing import (
    PreprocessingPipeline,
    PreprocessingStep,
    StepType,
    ParamSpec,
)

__all__ = [
    "LocalVisionAI",
    "OCREngine",
    "OCRResult",
    "OCRManager",
    "EngineType",
    "PreprocessingPipeline",
    "PreprocessingStep",
    "StepType",
    "ParamSpec",
]
