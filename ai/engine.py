"""
VivekAI_App - AI Engine
Manages Groq, Gemini, and Ollama backends
Auto-fallback if primary engine fails
"""

import time
import config
from ai.groq_client import GroqClient
from ai.gemini_client import GeminiClient
from ai.ollama_client import OllamaClient

class AIEngine:
    def __init__(self):
        self.groq = GroqClient()
        self.gemini = GeminiClient()
        self.ollama = OllamaClient()
        self.current_engine = config.DEFAULT_ENGINE
        self.fallback_order = ["groq", "gemini", "ollama"]

    def set_engine(self, engine_name):
        """Switch AI engine: groq | gemini | ollama"""
        self.current_engine = engine_name

    def get_engine_name(self):
        return self.current_engine.upper()

    def generate(self, prompt, system_prompt, on_token=None):
        """
        Generate AI response with auto-fallback
        Returns: (response_text, engine_used, time_taken)
        """
        engines_to_try = [self.current_engine] + [
            e for e in self.fallback_order if e != self.current_engine
        ]

        for engine_name in engines_to_try:
            try:
                start = time.time()
                response = self._call_engine(engine_name, prompt, system_prompt)
                elapsed = round(time.time() - start, 2)

                if response:
                    return response, engine_name.upper(), elapsed

            except Exception as e:
                print(f"[{engine_name}] failed: {e}, trying next...")
                continue

        return "Sorry, all AI engines are unavailable right now.", "NONE", 0

    def _call_engine(self, engine_name, prompt, system_prompt):
        if engine_name == "groq":
            return self.groq.generate(prompt, system_prompt)
        elif engine_name == "gemini":
            return self.gemini.generate(prompt, system_prompt)
        elif engine_name == "ollama":
            return self.ollama.generate(prompt, system_prompt)
        return None
