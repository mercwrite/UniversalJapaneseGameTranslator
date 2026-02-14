from rapidocr_onnxruntime import RapidOCR

class RapidOCRWrapper:
    def __init__(self):
        print("Loading RapidOCR (Horizontal Optimized)...")
        # Use_det=True enables the 'Detection' phase (finding the text line).
        # Use_cls=False disables 'Classification' (checking if text is upside down), speeds it up.
        # Use_rec=True enables 'Recognition' (reading the text).
        self.engine = RapidOCR(det_use_cuda=False, rec_use_cuda=False)

    def scan(self, img):
        """
        img: Can be a file path, numpy array (OpenCV), or raw bytes.
        """
        # RapidOCR prefers numpy arrays (OpenCV format)
        # If passed a PIL image, convert it first
        import numpy as np
        from PIL import Image

        if isinstance(img, Image.Image):
            img = np.array(img)

        # Run OCR
        # result structure: [ [ [coords], text, confidence ], ... ]
        result, _ = self.engine(img)

        if not result:
            return ""

        # RapidOCR might detect multiple lines.
        # For a translation overlay, we usually want to join them together.
        detected_text = []
        for line in result:
            text = line[1]
            detected_text.append(text)

        # Join with a space (or empty string for Japanese, usually)
        return "".join(detected_text)
