# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Universal Japanese Game Translator is a Windows desktop application that provides real-time OCR and translation overlays for Japanese games. It captures game window regions, extracts Japanese text using vision AI, translates it to English, and displays the translation in customizable overlay windows.

## Running the Application

```bash
# Install dependencies (requires Python 3.10+)
pip install -r requirements.txt

# Run the application
python main_ui.py
```

**Important**: The Sugoi translation model files must be present in the `sugoi_model/` directory with the following structure:
- `model.bin` - CTranslate2 model
- `spm.ja.nopretok.model` - Japanese tokenizer
- `spm.en.nopretok.model` - English tokenizer

## System Requirements

- Windows OS (uses Windows-specific APIs for window capture)
- NVIDIA GPU with CUDA support (for optimal performance with Qwen2-VL)
- Python 3.10+
- PyTorch with CUDA 12.1 support

## Architecture

### Pipeline Flow

1. **Window Capture** (`capture/window_capture.py`) - Captures game window using Win32 GDI APIs
2. **OCR** (`ocr/qwen_wrapper.py`) - Qwen2-VL-2B vision model extracts Japanese text
3. **Translation** (`translation/sugoi_wrapper.py`) - CTranslate2 translates Japanese to English
4. **Display** (`ui/text_overlay.py`) - Shows translation in floating overlay window

### Package Structure

```
project/
├── main_ui.py                    # Application entry point
├── error_handler.py              # Cross-cutting error handling utilities
├── perf_logger.py                # Performance measurement
│
├── capture/                      # Window capture package
│   ├── __init__.py               # Exports WindowCapture
│   └── window_capture.py         # Win32 GDI screen capture
│
├── ocr/                          # OCR engine package
│   ├── __init__.py               # Exports LocalVisionAI
│   ├── qwen_wrapper.py           # Qwen2-VL-2B primary OCR engine
│   ├── deepseek_wrapper.py       # DeepSeek OCR (unused)
│   ├── rapid_wrapper.py          # RapidOCR (unused)
│   ├── winocr_wrapper.py         # Windows native OCR (unused)
│   └── image_processor.py        # Image preprocessing utilities
│
├── translation/                  # Translation engine package
│   ├── __init__.py               # Exports SugoiTranslator
│   └── sugoi_wrapper.py          # CTranslate2 + SentencePiece
│
└── ui/                           # UI package
    ├── __init__.py
    ├── controller.py             # Main controller window (orchestrator)
    ├── text_overlay.py           # Floating translucent overlay windows
    ├── snipper.py                # Screen region selection tool
    ├── widgets.py                # Custom widgets (ModernComboBox, IconButton, OverlayListItem)
    ├── styles.py                 # Dark theme stylesheet
    └── pipeline.py               # TranslationPipeline class (OCR + translation loop)
```

### Core Components

**Entry Point**
- `main_ui.py` - Application entry point with global exception handling

**Capture Package** (`capture/`)
- `window_capture.py` - WindowCapture class for Windows-specific screen capture
  - Uses ctypes to interface with Win32 APIs (PrintWindow, BitBlt, GDI)
  - Captures windows in background (doesn't require focus)

**OCR Package** (`ocr/`)
- `qwen_wrapper.py` - LocalVisionAI class wraps Qwen2-VL-2B-Instruct model
  - Primary OCR engine
  - Uses Hugging Face transformers
  - Supports both OCR-only and direct translation modes
- `deepseek_wrapper.py`, `rapid_wrapper.py`, `winocr_wrapper.py` - Alternative OCR engines (currently unused)
- `image_processor.py` - Image preprocessing utilities

**Translation Package** (`translation/`)
- `sugoi_wrapper.py` - SugoiTranslator class wraps CTranslate2 model
  - Primary translation engine
  - Separate Japanese/English SentencePiece tokenizers

**UI Package** (`ui/`)
- `controller.py` - Main controller window (ControllerWindow class)
  - Manages multiple overlay regions
  - Handles window selection and translation start/stop
  - Delegates pipeline execution to TranslationPipeline
- `text_overlay.py` - Floating translucent overlay windows (TextBoxOverlay class)
- `snipper.py` - Screen region selection tool (Snipper class)
- `widgets.py` - Custom Qt widgets (ModernComboBox, IconButton, OverlayListItem)
- `styles.py` - Dark theme stylesheet constant and `apply_dark_styles()` function
- `pipeline.py` - TranslationPipeline class with image diff and OCR/translation loop

**Cross-cutting Utilities**
- `error_handler.py` - Error handling infrastructure
  - `@safe_execute` decorator for graceful error handling
  - SafeWindowCapture utility class for validation
  - Centralized logging configuration
- `perf_logger.py` - PerformanceLogger for measuring OCR/translation latency

### Key Design Patterns

**Error Handling**
All critical functions use the `@safe_execute` decorator:
```python
@safe_execute(default_return=None, log_errors=True, error_message="Custom message")
def risky_function():
    # ...
```

**Region Management**
The controller maintains active regions in a dictionary:
```python
self.active_regions[region_id] = {
    "rect": {"left": x, "top": y, "width": w, "height": h},
    "overlay": TextBoxOverlay(...),
    "item": OverlayListItem(...)
}
```

**Translation Pipeline**
The `TranslationPipeline.run()` method in `ui/pipeline.py`:
1. Captures full window screenshot
2. For each enabled region:
   - Crops the region from full window
   - Compares with last image (skip if diff < 2.0)
   - Runs OCR via `vision_ai.analyze()`
   - Translates via `translator.translate()`
   - Updates overlay with `overlay.update_text()`

**PyQt6 Signals**
- `region_selected` signal (Snipper -> Controller)
- `geometry_changed` signal (TextBoxOverlay -> Controller)

## Model Initialization

Both AI models are initialized in `ControllerWindow._initialize_backend()`:
- Qwen2-VL loads with `device_map="auto"` for automatic GPU placement
- Sugoi Translator detects CUDA availability and selects device accordingly
- Failures are caught and logged, allowing the app to start without models (for debugging UI)

## Development Notes

### Adding New OCR Engines
Create a wrapper class in the `ocr/` package following the pattern in `ocr/qwen_wrapper.py`:
- Implement `analyze(pil_image, mode="ocr")` method
- Decorate with `@safe_execute` for error handling
- Validate images with `SafeWindowCapture.validate_image()`
- Return empty string on errors

### Adding New Translation Engines
Create a wrapper class in the `translation/` package following the pattern in `translation/sugoi_wrapper.py`:
- Implement `translate(text)` method
- Decorate with `@safe_execute`
- Validate input text (non-empty strings)
- Return empty string on errors

### Windows API Usage
The application uses Windows-specific APIs extensively:
- `windll.user32.FindWindowW()` - Find window by title
- `windll.user32.PrintWindow()` - Capture window content
- `windll.gdi32.*` - GDI bitmap operations
- Always validate window handles with `SafeWindowCapture.is_window_valid(hwnd)`

### Performance Optimization
- Images are compared using numpy array diff to avoid redundant OCR
- Only enabled regions are processed
- Timer interval is 100ms (10 FPS) - balance between responsiveness and CPU usage

## Common Tasks

**Testing OCR/Translation Pipeline**
Temporarily modify `ui/controller.py` to:
1. Load a test image instead of screen capture
2. Call `vision_ai.analyze()` directly
3. Print results to console

**Debugging Window Capture Issues**
Enable debug logging in `capture/window_capture.py`:
- Check `SafeWindowCapture.is_window_valid()` results
- Verify window rect coordinates
- Ensure PrintWindow fallback to BitBlt is working

**Modifying UI Styling**
All styles are defined in `ui/styles.py` as `DARK_THEME_STYLESHEET`. The UI uses a black background with white borders and rounded corners throughout.

## PyQt6 Specifics

**Window Flags for Overlays**
TextBoxOverlay uses specific flags to stay on top and be translucent:
- Check `ui/text_overlay.py` for frameless, always-on-top configuration
- Opacity is controlled via `setWindowOpacity()` and background alpha

**Qt Event Loop**
The translation timer (`QtCore.QTimer`) runs on the main event loop. Long-running operations should be avoided in timer callbacks to prevent UI freezing.
