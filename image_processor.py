import cv2
import numpy as np
from PIL import Image

class ImagePreprocessor:
    @staticmethod
    def process(pil_image, upscale_factor=3.0, apply_filters=False):
        # NOTE: Default upscale increased to 3.0. 
        # Windows OCR needs massive text to see the tiny dots correctly.
        
        img = np.array(pil_image)
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        # 1. UPSCALING (High Quality)
        # We use Lanczos4 to keep the tiny dakuten separated from the characters.
        if upscale_factor > 1:
            h, w = gray.shape
            new_size = (int(w * upscale_factor), int(h * upscale_factor))
            gray = cv2.resize(gray, new_size, interpolation=cv2.INTER_LANCZOS4)

        # 2. NORMALIZATION (Contrast Stretch)
        # Ensures the darkest pixel is 0 and brightest is 255.
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        # 3. AUTO-INVERSION
        # Windows OCR performs significantly better on Black Text / White BG
        # especially for dakuten detection.
        _, thresh_check = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        num_white = cv2.countNonZero(thresh_check)
        if (gray.size - num_white) > num_white:
            gray = cv2.bitwise_not(gray)

        # 4. GAMMA CORRECTION (The "Dakuten Saver")
        # Gamma < 1.0 makes shadows/mid-tones darker.
        # This makes faint dakuten dots turn solid black.
        gamma = 0.5 # Aggressive darkening
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        gray = cv2.LUT(gray, table)

        # 5. SHARPENING (Mild)
        # We want to sharpen, but NOT blur (do not use medianBlur or bilateralFilter here)
        # Blurring eats dakuten.
        sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        gray = cv2.filter2D(gray, -1, sharpen_kernel)

        return Image.fromarray(gray)