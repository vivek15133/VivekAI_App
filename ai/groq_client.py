"""
VivekAI_App - Groq Client
Ultra-fast AI responses via Groq LPU
"""

from groq import Groq
import config

class GroqClient:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if config.GROQ_API_KEY:
            self.client = Groq(api_key=config.GROQ_API_KEY)

    def generate(self, prompt, system_prompt):
        if not self.client:
            raise Exception("Groq API key not configured")

        response = self.client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config.MAX_RESPONSE_TOKENS,
            temperature=0.7,
            timeout=config.RESPONSE_TIMEOUT
        )
        return response.choices[0].message.content.strip()
