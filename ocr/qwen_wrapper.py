from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import torch
from PIL import Image
from error_handler import safe_execute, SafeWindowCapture

class LocalVisionAI:
    def __init__(self):
        print("Loading Qwen2-VL-2B (Vision AI)...")
        self.model = None
        self.processor = None

        try:
            # Load Model in 4-bit mode (Fast, Low VRAM)
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                "Qwen/Qwen2-VL-2B-Instruct",
                torch_dtype="auto",
                device_map="auto",
                # quantization_config is optional but recommended for gaming while translating
                # quantization_config=BitsAndBytesConfig(load_in_4bit=True)
            )

            self.processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct")
            print("Vision AI Loaded.")
        except Exception as e:
            print(f"Failed to load Vision AI: {e}")
            raise

    @safe_execute(default_return="", log_errors=True, error_message="OCR/Analysis error")
    def analyze(self, pil_image, mode="ocr"):
        """
        mode: 'ocr' returns Japanese text. 'translate' returns English translation.
        """
        if not self.model or not self.processor:
            return ""

        if not SafeWindowCapture.validate_image(pil_image):
            return ""

        try:
            # Define the prompt based on what you want
            if mode == "ocr":
                text_prompt = "Read the Japanese text in this image accurately. Output only the text."
            else:
                text_prompt = "Translate the text in this image to English. Output only the translation."

            # Prepare messages
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": pil_image},
                        {"type": "text", "text": text_prompt},
                    ],
                }
            ]

            # Prepare inputs
            text_input = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)

            inputs = self.processor(
                text=[text_input],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            inputs = inputs.to("cuda")

            # Generate output
            # max_new_tokens=128 is usually enough for a dialogue box
            generated_ids = self.model.generate(**inputs, max_new_tokens=128)

            # Decode
            output_text = self.processor.batch_decode(
                generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )

            if not output_text or len(output_text) == 0:
                return ""

            # The output includes the prompt, so we strip it to get just the AI response
            # (This parsing depends slightly on the model version, but usually:)
            response = output_text[0].split("assistant\n")[-1].strip()
            return response if response else ""
        except Exception:
            return ""  # Return empty string on error
