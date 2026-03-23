"""
VivekAI_App - Vision AI Client
Uses Gemini Vision to understand screen contents and answer questions
Falls back to OCR text if vision API unavailable
"""

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google")
import google.generativeai as genai  # type: ignore
import base64
import io
from PIL import Image  # type: ignore
import config  # type: ignore


class VisionAIClient:
    def __init__(self):
        self.model = None
        self._init_client()

    def _init_client(self):
        if config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)
            # Use vision-capable model
            self.model = genai.GenerativeModel("gemini-2.0-flash")

    def analyze_screenshot(self, screenshot_image, mode="Interview"):
        """
        Send screenshot to Gemini Vision for analysis
        Returns AI-generated answer based on what's visible on screen
        """
        if not self.model:
            return "Gemini API key not configured. Please add GEMINI_API_KEY to .env file."

        try:
            # Convert PIL image to bytes
            buffer = io.BytesIO()
            screenshot_image.save(buffer, format="PNG")
            buffer.seek(0)
            image_bytes = buffer.read()

            # Build prompt based on mode
            prompt = self._build_vision_prompt(mode)

            # Send to Gemini Vision
            response = self.model.generate_content([
                prompt,
                {
                    "mime_type": "image/png",
                    "data": base64.b64encode(image_bytes).decode()
                }
            ])

            return response.text.strip()

        except Exception as e:
            return f"Vision AI error: {str(e)}"

    def analyze_ocr_text(self, text, mode="Interview"):
        """
        Send OCR-extracted text to AI for answering
        Used as fallback when vision API has issues
        """
        if not self.model:
            return "Gemini API key not configured."

        try:
            prompt = f"""You are VivekAI assistant in {mode} mode.
The following text was extracted from the user's screen:

---
{text}
---

Identify if there is a question or problem here and provide a clear, concise answer.
If it's a coding problem, provide the solution with explanation.
If it's an interview question, give a strong answer.
Keep response under 200 words unless code is needed.
"""
            response = self.model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            return f"AI error: {str(e)}"

    def _build_vision_prompt(self, mode):
        prompts = {
            "Interview": """You are VivekAI, an expert interview assistant.
Look at this screenshot carefully. 
If you see an interview question, coding problem, or any question being asked:
1. Identify the question clearly
2. Provide a concise, accurate, ready-to-speak answer
3. For coding: show the optimal solution with time/space complexity
4. Keep answer under 200 words unless code is needed
If no question is visible, describe what you see briefly.""",

            "Coding": """You are VivekAI, a senior software engineer.
Look at this screenshot carefully.
If you see a coding problem or technical question:
1. State the optimal approach and complexity
2. Write clean, working code
3. Explain key logic briefly
If no coding problem is visible, describe what you see.""",

            "Meeting": """You are VivekAI, a meeting assistant.
Look at this screenshot and summarize:
1. Key information visible
2. Any action items or decisions
3. Important names, numbers, or dates
Keep summary under 100 words.""",

            "General": """You are VivekAI, a helpful AI assistant.
Look at this screenshot and:
1. Identify any question or problem visible
2. Provide a helpful, accurate answer
3. Keep response concise and clear"""
        }
        return prompts.get(mode, prompts["General"])
