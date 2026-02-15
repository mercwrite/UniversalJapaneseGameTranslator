# Universal Japanese Game Translator

Real-time OCR and translation overlay for Japanese games on Windows. Captures any game window, extracts Japanese text using AI vision models, translates it to English, and displays the result in draggable, resizable overlay windows — all without interrupting gameplay.

---

## Features

### Multi-Region Overlay System
- Create **unlimited translation overlay regions** by drawing rectangles on your screen
- Each overlay is independently **draggable and resizable** with edge/corner handles
- **Toggle overlays on/off** individually with eye icons
- **Adjustable opacity** slider controls overlay transparency across all regions
- Close button appears on hover for quick removal

### Dual OCR Engine Support
- **manga-ocr (Lightweight)** — ~400MB model, runs on CPU or GPU, fast and efficient for clean text
- **Qwen2-VL-2B (High Accuracy)** — Vision-language model for complex scenes, requires NVIDIA GPU with CUDA
- Hot-swap between engines at any time from the settings page
- Per-engine preprocessing toggle — lightweight engines benefit from preprocessing, VLMs typically don't

### Image Preprocessing Pipeline
- **10-step configurable pipeline** with live preview editor:
  - **Scale** — Upscale images (1x–4x) with selectable interpolation (nearest, bilinear, bicubic, lanczos)
  - **Grayscale** — Convert to grayscale for downstream steps
  - **Auto Invert** — Automatically invert dark-on-light or light-on-dark text based on brightness threshold
  - **Contrast / Brightness** — Fine-tune contrast and brightness
  - **CLAHE** — Adaptive histogram equalization for uneven lighting (OpenCV)
  - **Sharpen** — Unsharp mask with adjustable amount and radius
  - **Denoise** — NL-Means, bilateral, median, or Gaussian denoising (OpenCV)
  - **Binarize** — Otsu, adaptive Gaussian/mean, or simple thresholding (OpenCV)
  - **Morphology** — Close, open, dilate, or erode operations to clean up strokes (OpenCV)
  - **Padding** — Add white or black border padding to help detect edge characters
- Each step has **collapsible parameter controls** with sliders, dropdowns, and checkboxes
- **Live preview** — capture any overlay region and see preprocessing results in real-time
- **Reset to defaults** with one click
- Pipeline configuration is saved and restored across sessions

### Translation Engine
- **Sugoi Translator** — Offline Japanese-to-English translation powered by CTranslate2 and SentencePiece
- Runs entirely locally with no API keys or internet connection required
- Supports both CPU and CUDA GPU acceleration

### Smart Pipeline Execution
- **Image diff detection** — Only runs OCR when the screen content actually changes (numpy-based comparison)
- **Configurable pipeline interval** — Adjustable from 50ms to 2000ms via settings slider
- **Background window capture** — Uses Win32 PrintWindow API to capture games without requiring focus, with BitBlt fallback for hardware-accelerated windows
- Performance logging tracks OCR and translation latency per cycle

### Modern Docked UI
- **Auto-hiding side panel** — Collapses to a small tab on the right edge of the screen, expands on hover with smooth animation
- **Three-page navigation** — Home (overlay management), Preprocessing (pipeline editor), Settings (engine config)
- **Dark theme** throughout with rounded corners, translucent backgrounds, and custom-drawn vector icons
- **Custom widgets** — ModernComboBox with animated arrows, IconButton with hand-drawn SVG-style icons, OverlayListItem with toggle/delete controls
- **Always-on-top** — Controller and overlays stay above game windows

### Settings & Preferences
- OCR engine selection with GPU requirement indicators
- Translation engine status display
- Pipeline interval tuning
- Per-engine preprocessing toggles
- All settings **persist across sessions** via JSON preferences file
- Exit button for clean shutdown (unloads all models and releases GPU memory)

---

## Quick Start

### Prerequisites

- **Windows 10/11**
- **Python 3.10+**
- **NVIDIA GPU with CUDA** (recommended for Qwen VLM and faster translation)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/UniversalJapaneseGameTranslator.git
cd UniversalJapaneseGameTranslator

# Install dependencies
pip install -r requirements.txt

# Install PyTorch with CUDA support (if not already installed)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Sugoi Translation Model Setup

Download the Sugoi translation model files and place them in `sugoi_model/`:

```
sugoi_model/
  model.bin                 # CTranslate2 model
  spm.ja.nopretok.model     # Japanese SentencePiece tokenizer
  spm.en.nopretok.model     # English SentencePiece tokenizer
```

### Run

```bash
python main_ui.py
```

---

## How to Use

1. **Launch the app** — A small tab appears on the right edge of your screen
2. **Hover over the tab** — The control panel slides out
3. **Select your game window** from the dropdown (click refresh to update the list)
4. **Click the + button** — Draw a rectangle over the area of the game with Japanese text
5. **Click the play button** — Translation starts automatically
6. **Drag and resize** overlays to fine-tune positioning
7. **Adjust opacity** with the slider to blend overlays with the game

---

## Architecture

```
project/
├── main_ui.py                    # Application entry point
├── error_handler.py              # @safe_execute decorator, validation utilities
├── perf_logger.py                # OCR/translation latency measurement
├── preferences.py                # JSON-based settings persistence
│
├── capture/                      # Window capture
│   └── window_capture.py         # Win32 GDI/PrintWindow/BitBlt capture
│
├── ocr/                          # OCR engines
│   ├── base.py                   # Abstract OCREngine + OCRResult
│   ├── manager.py                # Engine selection + preprocessing coordinator
│   ├── preprocessing.py          # 10-step configurable image pipeline
│   ├── manga_ocr_engine.py       # manga-ocr (lightweight, CPU-friendly)
│   ├── vlm_engine.py             # Qwen2-VL-2B (GPU, high accuracy)
│   └── qwen_wrapper.py           # Qwen2-VL-2B model wrapper
│
├── translation/                  # Translation
│   └── sugoi_wrapper.py          # CTranslate2 + SentencePiece translator
│
└── ui/                           # PyQt6 interface
    ├── controller.py             # Main orchestrator window
    ├── text_overlay.py           # Floating translucent overlays
    ├── snipper.py                # Screen region selection tool
    ├── pipeline.py               # OCR + translation loop with image diff
    ├── preprocessing_editor.py   # Visual pipeline editor with live preview
    ├── settings_page.py          # Engine and performance configuration
    ├── widgets.py                # Custom widgets (ComboBox, IconButton, ListItem)
    └── styles.py                 # Dark theme stylesheet
```

---

## Tech Stack

| Component | Technology |
|---|---|
| UI Framework | PyQt6 |
| OCR (Lightweight) | manga-ocr |
| OCR (High Accuracy) | Qwen2-VL-2B-Instruct (Hugging Face Transformers) |
| Translation | CTranslate2 + SentencePiece (Sugoi model) |
| Image Processing | Pillow, OpenCV, NumPy |
| Window Capture | Win32 API (PrintWindow, BitBlt, GDI) |
| GPU Acceleration | PyTorch + CUDA 12.1 |

---

## License

See [LICENSE](LICENSE) for details.
