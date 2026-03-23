"""
VivekAI_App - Gemini Client
Google Gemini 2.0 Flash - Fast & Smart
"""

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google")
import google.generativeai as genai  # type: ignore
import config  # type: ignore

class GeminiClient:
    def __init__(self):
        self.model = None
        self._init_client()

    def _init_client(self):
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=config.MAX_RESPONSE_TOKENS,
                    temperature=0.7,
                )
            )

    def generate(self, prompt, system_prompt):
        if not self.model:
            raise Exception("Gemini API key not configured")

        full_prompt = f"{system_prompt}\n\nUser: {prompt}"
        response = self.model.generate_content(full_prompt)
        return response.text.strip()
