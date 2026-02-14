import asyncio
import winsdk.windows.media.ocr as ocr
import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.storage.streams as streams
import winsdk
from PIL import Image
import io

class WindowsOCR:
    def __init__(self):
        print("Loading Windows Native OCR...")

        # 1. Find the Japanese Language Pack
        try:
            lang = ocr.OcrEngine.try_create_from_language(winsdk.windows.globalization.Language("ja"))
        except Exception:
            lang = None

        if not lang:
            raise Exception("Japanese Language Pack not found! Go to Windows Settings -> Time & Language -> Add Japanese.")

        self.engine = lang

    def scan(self, pil_image):
        """
        Synchronous wrapper to run the async OCR engine.
        """
        try:
            return asyncio.run(self._scan_async(pil_image))
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    async def _scan_async(self, pil_image):
        # 1. Convert PIL Image to Bytes (PNG format)
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        img_byte_arr = io.BytesIO()
        # Save as PNG to preserve quality (Lossless)
        pil_image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        # 2. Memory Stream Setup
        # Create a Windows Runtime RandomAccessStream
        stream = streams.InMemoryRandomAccessStream()
        writer = streams.DataWriter(stream)

        # --- THE FIX IS HERE ---
        # Pass the raw bytes directly. Do not cast to list().
        writer.write_bytes(img_bytes)

        await writer.store_async()

        # Rewind stream to beginning so Decoder can read it
        stream.seek(0)

        # 3. Create Bitmap Decoder
        # This parses the PNG data inside the stream
        decoder = await imaging.BitmapDecoder.create_async(stream)

        # 4. Get SoftwareBitmap
        # OCR engine needs a SoftwareBitmap, not a stream
        software_bitmap = await decoder.get_software_bitmap_async()

        # 5. Run OCR
        result = await self.engine.recognize_async(software_bitmap)

        # 6. Extract Text
        lines = []
        for line in result.lines:
            lines.append(line.text)

        # Join lines with no spaces (standard for Japanese)
        return "".join(lines)
