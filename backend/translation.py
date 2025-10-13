from typing import Optional
from googletrans import Translator as GoogleTranslator

class Translator:
    def __init__(self):
        self.translator = GoogleTranslator()

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> Optional[str]:
        try:
            if not text or src_lang == tgt_lang:
                return text
            result = self.translator.translate(text, src=src_lang, dest=tgt_lang)
            return result.text
        except Exception as e:
            print(f"Translation error: {e}")
            return text
