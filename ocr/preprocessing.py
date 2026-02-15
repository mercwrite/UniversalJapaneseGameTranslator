"""Image preprocessing pipeline with toggleable steps and dynamic UI parameter specs."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# Check for OpenCV availability
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    try:
        import numpy as np
    except ImportError:
        np = None


class StepType(Enum):
    SCALE = "scale"
    GRAYSCALE = "grayscale"
    AUTO_INVERT = "auto_invert"
    CONTRAST = "contrast"
    CLAHE = "clahe"
    SHARPEN = "sharpen"
    DENOISE = "denoise"
    BINARIZE = "binarize"
    MORPHOLOGY = "morphology"
    PADDING = "padding"


@dataclass
class ParamSpec:
    """Describes one tunable parameter. The UI reads these to generate controls."""

    name: str
    label: str
    type: str  # "int", "float", "bool", "choice"
    default: Any
    min_val: Any = None
    max_val: Any = None
    step: Any = None
    choices: list[str] | None = None
    tooltip: str = ""


@dataclass
class PreprocessingStep:
    """A single preprocessing step with enable toggle and parameters."""

    step_type: StepType
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def get_param_specs(cls, step_type: StepType) -> list[ParamSpec]:
        return _PARAM_SPECS_REGISTRY.get(step_type, [])

    @classmethod
    def register_specs(cls, step_type: StepType, specs: list[ParamSpec]) -> None:
        _PARAM_SPECS_REGISTRY[step_type] = specs


# Class-level registry stored outside the dataclass to avoid mutable default issues
_PARAM_SPECS_REGISTRY: dict[StepType, list[ParamSpec]] = {}


# ─── Register ParamSpec lists for each StepType ─────────────────────────────

PreprocessingStep.register_specs(StepType.SCALE, [
    ParamSpec("factor", "Scale Factor", "float", default=2.0,
              min_val=1.0, max_val=4.0, step=0.25,
              tooltip="Upscale image for better OCR. 2x is usually optimal."),
    ParamSpec("interpolation", "Interpolation", "choice", default="lanczos",
              choices=["nearest", "bilinear", "bicubic", "lanczos"],
              tooltip="Resampling method. Lanczos preserves text edges best."),
])

PreprocessingStep.register_specs(StepType.GRAYSCALE, [
    ParamSpec("enabled_note", "Convert to Grayscale", "bool", default=True,
              tooltip="Convert to grayscale. Required for binarization/CLAHE."),
])

PreprocessingStep.register_specs(StepType.AUTO_INVERT, [
    ParamSpec("threshold", "Brightness Threshold", "int", default=127,
              min_val=0, max_val=255, step=1,
              tooltip="If mean brightness is above this, invert. Normalizes text polarity."),
])

PreprocessingStep.register_specs(StepType.CONTRAST, [
    ParamSpec("factor", "Contrast Factor", "float", default=1.5,
              min_val=0.5, max_val=3.0, step=0.1,
              tooltip="1.0 = no change, 2.0 = double contrast."),
    ParamSpec("brightness", "Brightness Factor", "float", default=1.0,
              min_val=0.5, max_val=2.0, step=0.1,
              tooltip="1.0 = no change."),
])

PreprocessingStep.register_specs(StepType.CLAHE, [
    ParamSpec("clip_limit", "Clip Limit", "float", default=2.0,
              min_val=0.5, max_val=10.0, step=0.5,
              tooltip="Higher = more local contrast."),
    ParamSpec("grid_size", "Grid Size", "int", default=8,
              min_val=2, max_val=32, step=1,
              tooltip="Smaller = more localized contrast adjustment."),
])

PreprocessingStep.register_specs(StepType.SHARPEN, [
    ParamSpec("amount", "Sharpen Amount", "float", default=1.5,
              min_val=0.0, max_val=5.0, step=0.1,
              tooltip="Unsharp mask amount. 0 = none."),
    ParamSpec("radius", "Radius", "float", default=1.0,
              min_val=0.5, max_val=5.0, step=0.5,
              tooltip="Unsharp mask radius in pixels."),
])

PreprocessingStep.register_specs(StepType.DENOISE, [
    ParamSpec("strength", "Denoise Strength", "int", default=10,
              min_val=1, max_val=30, step=1,
              tooltip="Higher = smoother but may lose detail."),
    ParamSpec("method", "Method", "choice", default="nlmeans",
              choices=["nlmeans", "bilateral", "median", "gaussian"],
              tooltip="Denoising algorithm. NL-Means is best quality."),
])

PreprocessingStep.register_specs(StepType.BINARIZE, [
    ParamSpec("method", "Method", "choice", default="adaptive_gaussian",
              choices=["otsu", "adaptive_gaussian", "adaptive_mean", "simple"],
              tooltip="Adaptive works best on uneven backgrounds."),
    ParamSpec("block_size", "Block Size (adaptive)", "int", default=11,
              min_val=3, max_val=99, step=2,
              tooltip="Must be odd. Used by adaptive methods only."),
    ParamSpec("constant", "Constant (adaptive)", "int", default=2,
              min_val=-20, max_val=20, step=1,
              tooltip="Subtracted from adaptive threshold mean."),
    ParamSpec("threshold", "Threshold (simple/otsu)", "int", default=128,
              min_val=0, max_val=255, step=1,
              tooltip="Manual threshold for simple method."),
])

PreprocessingStep.register_specs(StepType.MORPHOLOGY, [
    ParamSpec("operation", "Operation", "choice", default="close",
              choices=["close", "open", "dilate", "erode"],
              tooltip="Close fills gaps in strokes. Open removes noise."),
    ParamSpec("kernel_size", "Kernel Size", "int", default=2,
              min_val=1, max_val=7, step=1),
    ParamSpec("iterations", "Iterations", "int", default=1,
              min_val=1, max_val=5, step=1),
])

PreprocessingStep.register_specs(StepType.PADDING, [
    ParamSpec("pixels", "Padding (px)", "int", default=8,
              min_val=0, max_val=50, step=1,
              tooltip="White border padding. Helps detect edge characters."),
    ParamSpec("color", "Pad Color", "choice", default="white",
              choices=["white", "black"]),
])


# ─── Executor functions ─────────────────────────────────────────────────────

_INTERPOLATION_MAP = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}


def exec_scale(image: Image.Image, params: dict) -> Image.Image:
    factor = params.get("factor", 2.0)
    if factor <= 1.0:
        return image
    interp_name = params.get("interpolation", "lanczos")
    resample = _INTERPOLATION_MAP.get(interp_name, Image.Resampling.LANCZOS)
    new_w = int(image.width * factor)
    new_h = int(image.height * factor)
    return image.resize((new_w, new_h), resample)


def exec_grayscale(image: Image.Image, params: dict) -> Image.Image:
    return image.convert("L")


def exec_auto_invert(image: Image.Image, params: dict) -> Image.Image:
    threshold = params.get("threshold", 127)
    # Compute mean brightness on grayscale version
    gray = image.convert("L") if image.mode != "L" else image
    if np is not None:
        mean_val = float(np.array(gray).mean())
    else:
        # Pure PIL fallback
        pixels = list(gray.getdata())
        mean_val = sum(pixels) / len(pixels) if pixels else 128
    if mean_val > threshold:
        if image.mode == "L":
            return ImageOps.invert(image)
        else:
            return ImageOps.invert(image.convert("RGB"))
    return image


def exec_contrast(image: Image.Image, params: dict) -> Image.Image:
    factor = params.get("factor", 1.5)
    brightness = params.get("brightness", 1.0)
    if image.mode == "L":
        image = image.convert("RGB")
    result = ImageEnhance.Contrast(image).enhance(factor)
    result = ImageEnhance.Brightness(result).enhance(brightness)
    return result


def exec_clahe(image: Image.Image, params: dict) -> Image.Image:
    clip_limit = params.get("clip_limit", 2.0)
    grid_size = params.get("grid_size", 8)

    if HAS_CV2:
        arr = np.array(image)
        clahe = cv2.createCLAHE(clipLimit=clip_limit,
                                tileGridSize=(grid_size, grid_size))
        if len(arr.shape) == 2:
            # Grayscale
            result = clahe.apply(arr)
            return Image.fromarray(result)
        else:
            # Color: apply to L channel in LAB
            lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            return Image.fromarray(rgb)
    else:
        # PIL fallback: autocontrast
        return ImageOps.autocontrast(image, cutoff=int(clip_limit))


def exec_sharpen(image: Image.Image, params: dict) -> Image.Image:
    amount = params.get("amount", 1.5)
    radius = params.get("radius", 1.0)
    if amount <= 0:
        return image
    # Convert to RGB if needed for UnsharpMask
    if image.mode == "L":
        return image.filter(ImageFilter.UnsharpMask(radius=radius, percent=int(amount * 100), threshold=0))
    return image.filter(ImageFilter.UnsharpMask(radius=radius, percent=int(amount * 100), threshold=0))


def exec_denoise(image: Image.Image, params: dict) -> Image.Image:
    strength = params.get("strength", 10)
    method = params.get("method", "nlmeans")

    if HAS_CV2:
        arr = np.array(image)
        if method == "nlmeans":
            if len(arr.shape) == 2:
                result = cv2.fastNlMeansDenoising(arr, None, strength, 7, 21)
            else:
                result = cv2.fastNlMeansDenoisingColored(arr, None, strength, strength, 7, 21)
        elif method == "bilateral":
            result = cv2.bilateralFilter(arr, 9, strength * 7, strength * 7)
        elif method == "median":
            ksize = max(3, strength | 1)  # Must be odd
            result = cv2.medianBlur(arr, ksize)
        elif method == "gaussian":
            ksize = max(3, strength | 1)
            result = cv2.GaussianBlur(arr, (ksize, ksize), 0)
        else:
            return image
        return Image.fromarray(result)
    else:
        # PIL fallback
        ksize = max(3, strength // 3)
        if ksize % 2 == 0:
            ksize += 1
        return image.filter(ImageFilter.MedianFilter(size=ksize))


def exec_binarize(image: Image.Image, params: dict) -> Image.Image:
    method = params.get("method", "adaptive_gaussian")
    block_size = params.get("block_size", 11)
    constant = params.get("constant", 2)
    threshold_val = params.get("threshold", 128)

    # Ensure grayscale
    gray = image.convert("L") if image.mode != "L" else image

    if HAS_CV2:
        arr = np.array(gray)
        if method == "otsu":
            _, result = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif method == "adaptive_gaussian":
            # Ensure block_size is odd and >= 3
            bs = max(3, block_size)
            if bs % 2 == 0:
                bs += 1
            result = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, bs, constant)
        elif method == "adaptive_mean":
            bs = max(3, block_size)
            if bs % 2 == 0:
                bs += 1
            result = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                           cv2.THRESH_BINARY, bs, constant)
        elif method == "simple":
            _, result = cv2.threshold(arr, threshold_val, 255, cv2.THRESH_BINARY)
        else:
            return gray
        return Image.fromarray(result)
    else:
        # PIL fallback: simple threshold
        return gray.point(lambda p: 255 if p > threshold_val else 0)


def exec_morphology(image: Image.Image, params: dict) -> Image.Image:
    if not HAS_CV2:
        return image  # No PIL fallback for morphology

    operation = params.get("operation", "close")
    kernel_size = params.get("kernel_size", 2)
    iterations = params.get("iterations", 1)

    arr = np.array(image)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    op_map = {
        "close": cv2.MORPH_CLOSE,
        "open": cv2.MORPH_OPEN,
        "dilate": cv2.MORPH_DILATE,
        "erode": cv2.MORPH_ERODE,
    }
    morph_op = op_map.get(operation, cv2.MORPH_CLOSE)
    result = cv2.morphologyEx(arr, morph_op, kernel, iterations=iterations)
    return Image.fromarray(result)


def exec_padding(image: Image.Image, params: dict) -> Image.Image:
    pixels = params.get("pixels", 8)
    color = params.get("color", "white")
    if pixels <= 0:
        return image
    fill = 255 if color == "white" else 0
    if image.mode == "L":
        return ImageOps.expand(image, border=pixels, fill=fill)
    else:
        fill_color = (255, 255, 255) if color == "white" else (0, 0, 0)
        return ImageOps.expand(image, border=pixels, fill=fill_color)


# ─── Executor registry ──────────────────────────────────────────────────────

STEP_EXECUTORS: dict[StepType, Callable] = {
    StepType.SCALE: exec_scale,
    StepType.GRAYSCALE: exec_grayscale,
    StepType.AUTO_INVERT: exec_auto_invert,
    StepType.CONTRAST: exec_contrast,
    StepType.CLAHE: exec_clahe,
    StepType.SHARPEN: exec_sharpen,
    StepType.DENOISE: exec_denoise,
    StepType.BINARIZE: exec_binarize,
    StepType.MORPHOLOGY: exec_morphology,
    StepType.PADDING: exec_padding,
}


# ─── PreprocessingPipeline ──────────────────────────────────────────────────

class PreprocessingPipeline:
    """Configurable image preprocessing pipeline."""

    def __init__(self, steps: list[PreprocessingStep] | None = None):
        self.steps = steps if steps is not None else self.default_steps()

    @staticmethod
    def default_steps() -> list[PreprocessingStep]:
        """Sensible defaults for Japanese game text OCR."""
        return [
            PreprocessingStep(StepType.SCALE, enabled=True,
                              params={"factor": 2.0, "interpolation": "lanczos"}),
            PreprocessingStep(StepType.GRAYSCALE, enabled=True,
                              params={"enabled_note": True}),
            PreprocessingStep(StepType.AUTO_INVERT, enabled=True,
                              params={"threshold": 127}),
            PreprocessingStep(StepType.CONTRAST, enabled=False,
                              params={"factor": 1.5, "brightness": 1.0}),
            PreprocessingStep(StepType.CLAHE, enabled=True,
                              params={"clip_limit": 2.0, "grid_size": 8}),
            PreprocessingStep(StepType.SHARPEN, enabled=False,
                              params={"amount": 1.5, "radius": 1.0}),
            PreprocessingStep(StepType.DENOISE, enabled=False,
                              params={"strength": 10, "method": "nlmeans"}),
            PreprocessingStep(StepType.BINARIZE, enabled=False,
                              params={"method": "adaptive_gaussian", "block_size": 11,
                                      "constant": 2, "threshold": 128}),
            PreprocessingStep(StepType.MORPHOLOGY, enabled=False,
                              params={"operation": "close", "kernel_size": 2,
                                      "iterations": 1}),
            PreprocessingStep(StepType.PADDING, enabled=True,
                              params={"pixels": 8, "color": "white"}),
        ]

    def process(self, image: Image.Image) -> Image.Image:
        """Run all enabled steps on the image."""
        result = image.copy()
        for step in self.steps:
            if not step.enabled:
                continue
            executor = STEP_EXECUTORS.get(step.step_type)
            if executor is None:
                continue
            try:
                result = executor(result, step.params)
            except Exception as e:
                warnings.warn(f"Preprocessing step {step.step_type.name} failed: {e}")
                continue
        return result

    def to_dict(self) -> list[dict]:
        """Serialize pipeline configuration."""
        return [
            {
                "type": step.step_type.name,
                "enabled": step.enabled,
                "params": dict(step.params),
            }
            for step in self.steps
        ]

    @classmethod
    def from_dict(cls, data: list[dict]) -> PreprocessingPipeline:
        """Deserialize pipeline configuration."""
        if not data:
            return cls()
        steps = []
        for entry in data:
            try:
                step_type = StepType[entry["type"]]
                steps.append(PreprocessingStep(
                    step_type=step_type,
                    enabled=entry.get("enabled", True),
                    params=entry.get("params", {}),
                ))
            except (KeyError, ValueError) as e:
                warnings.warn(f"Skipping invalid preprocessing step: {e}")
                continue
        if not steps:
            return cls()
        return cls(steps=steps)
