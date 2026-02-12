from transformers import AutoModel, AutoTokenizer
import torch
import os
os.environ["CUDA_VISIBLE_DEVICES"] = '0'
model_name = 'deepseek-ai/DeepSeek-OCR'

class DeepSeekLocalVisionAi:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True, use_safetensors=True)
        self.model = self.model.eval().cuda().to(torch.bfloat16)
    def analyze(self, pil_image, mode="ocr"):
        # prompt = "<image>\nFree OCR. "
        prompt = "<image>\n<|grounding|>Convert the document to markdown. "
        
        if mode == "ocr":
            prompt = "Read the Japanese text in this image accurately. Output only the text."
        else:
            prompt = "Translate the text in this image to English. Output only the translation."

        image_file = pil_image

        return self.model.infer(self.tokenizer, prompt=prompt, image_file=image_file, output_path='./', base_size = 1024, image_size = 640, crop_mode=True, save_results = False, test_compress = True)