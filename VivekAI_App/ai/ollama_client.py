"""
VivekAI_App - Ollama Client
100% Local, Offline AI - No internet needed
"""

import requests
import json
import config

class OllamaClient:
    def __init__(self):
        self.host = config.OLLAMA_HOST
        self.model = config.OLLAMA_MODEL

    def generate(self, prompt, system_prompt):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "num_predict": config.MAX_RESPONSE_TOKENS,
                "temperature": 0.7
            }
        }

        response = requests.post(
            f"{self.host}/api/chat",
            json=payload,
            timeout=config.RESPONSE_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()

    def is_available(self):
        """Check if Ollama is running"""
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2)
            return r.status_code == 200
        except:
            return False

    def list_models(self):
        """List downloaded models"""
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2)
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except:
            return []
