import ctranslate2
import sentencepiece as spm
import os
from error_handler import safe_execute

class SugoiTranslator:
    def __init__(self, model_folder_path, device="auto"):
        print("Loading Sugoi Translator (Split Tokenizer Mode)...")
        
        self.translator = None
        self.sp_source = None
        self.sp_target = None
        
        try:
            # 1. Hardware Detection
            if device == "auto":
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            print(f"Running Inference on: {device}")

            # 2. Load the CTranslate2 Engine
            # It will automatically find 'model.bin' and the vocab txt files
            if not os.path.exists(model_folder_path):
                raise FileNotFoundError(f"Model folder not found: {model_folder_path}")
            
            self.translator = ctranslate2.Translator(model_folder_path, device=device)
            
            # 3. Load the Japanese (Source) Tokenizer
            # This is used to turn your Japanese text into numbers/tokens
            ja_sp_path = os.path.join(model_folder_path, "spm.ja.nopretok.model")
            if not os.path.exists(ja_sp_path):
                raise FileNotFoundError(f"Missing Japanese tokenizer: {ja_sp_path}")
                
            self.sp_source = spm.SentencePieceProcessor()
            self.sp_source.load(ja_sp_path)

            # 4. Load the English (Target) Tokenizer
            # This is used to turn the result tokens back into English text
            en_sp_path = os.path.join(model_folder_path, "spm.en.nopretok.model")
            if not os.path.exists(en_sp_path):
                raise FileNotFoundError(f"Missing English tokenizer: {en_sp_path}")

            self.sp_target = spm.SentencePieceProcessor()
            self.sp_target.load(en_sp_path)
        except Exception as e:
            print(f"Failed to load Sugoi Translator: {e}")
            raise

    @safe_execute(default_return="", log_errors=True, error_message="Translation error")
    def translate(self, text):
        if not self.translator or not self.sp_source or not self.sp_target:
            return ""
        
        if not text or not isinstance(text, str) or text.strip() == "":
            return ""

        try:
            # Step 1: Encode using the JAPANESE model
            input_tokens = self.sp_source.encode(text, out_type=str)
            if not input_tokens:
                return ""

            # Step 2: Run Inference
            results = self.translator.translate_batch([input_tokens])
            if not results or len(results) == 0:
                return ""

            # Step 3: Decode using the ENGLISH model
            if not results[0].hypotheses or len(results[0].hypotheses) == 0:
                return ""
            
            output_tokens = results[0].hypotheses[0]
            translated_text = self.sp_target.decode(output_tokens)

            return translated_text if translated_text else ""
        except Exception:
            return ""  # Return empty string on error