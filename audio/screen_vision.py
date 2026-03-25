"""
VivekAI_App - Screen Vision Module
Feature 1: Screenshot button → AI answers what's on screen
Feature 2: Auto screen reader → watches region, auto-answers new questions
"""

import numpy as np  # type: ignore
import threading
import time
import queue
from PIL import Image, ImageGrab, ImageFilter  # type: ignore
import pytesseract  # type: ignore
import cv2  # type: ignore
import config  # type: ignore
from typing import Optional, Tuple

# ── Tesseract path for Windows ────────────────────────────
# Tesseract must be installed: https://github.com/UB-Mannheim/tesseract/wiki
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
except:
    pass


class ScreenVision:
    def __init__(self, on_text_detected=None):
        """
        on_text_detected: callback(text) called when new text is detected on screen
        """
        self.on_text_detected = on_text_detected
        self.auto_watching = False
        self.watch_region: Optional[Tuple[int, int, int, int]] = None        # (x1, y1, x2, y2) or None for full screen
        self.last_text = ""
        self.watch_thread: Optional[threading.Thread] = None
        self.text_queue = queue.Queue()
        self.min_text_change = 20       # Minimum chars changed to trigger
        self.watch_interval = 2.0       # Check every 2 seconds

    # ── FEATURE 1: Single Screenshot ─────────────────────
    def capture_and_read(self, region=None):
        """Capture screen/region and return (Image, Text)"""
        try:
            # 1. Capture
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                screenshot = ImageGrab.grab()
                # NEW: Automatic Header Cropping for Full Screen
                # Ignores top ~120px (Address bar, Tab bar) to avoid URL noise
                w, h = screenshot.size
                if h > 500: # Only crop if it's a real screen, not a tiny window
                    screenshot = screenshot.crop((0, 120, w, h))

            # 2. Enhance for OCR
            enhanced = self._enhance_for_ocr(screenshot)

            # Extract text using Tesseract OCR
            text = self._extract_text(enhanced)

            return screenshot, text

        except Exception as e:
            print(f"Screenshot error: {e}")
            return None, ""

    def capture_screen_as_base64(self, region=None):
        """
        Capture screen and return as base64 for Gemini Vision API
        """
        import base64
        import io
        try:
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                screenshot = ImageGrab.grab()

            # Convert to base64
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            buffer.seek(0)
            b64 = base64.b64encode(buffer.read()).decode("utf-8")
            return b64, screenshot

        except Exception as e:
            print(f"Screen capture error: {e}")
            return None, None

    # ── FEATURE 2: Auto Screen Watcher ───────────────────
    def start_watching(self, region=None):
        """
        Start watching screen region for new text/questions
        region: (x1, y1, x2, y2) tuple or None for full screen
        """
        self.watch_region = region
        self.auto_watching = True
        self.last_text = ""
        t = threading.Thread(
            target=self._watch_loop, daemon=True
        )
        self.watch_thread = t
        t.start()

    def stop_watching(self):
        self.auto_watching = False

    def set_region(self, x1, y1, x2, y2):
        """Set the screen region to watch"""
        self.watch_region = (x1, y1, x2, y2)

    def _watch_loop(self):
        """Continuously watch screen for new text"""
        while self.auto_watching:
            try:
                _, text = self.capture_and_read(self.watch_region)

                if text and self._is_significant_change(text):
                    self.last_text = text
                    if self.on_text_detected:
                        self.on_text_detected(text)

            except Exception as e:
                print(f"Watch loop error: {e}")

            time.sleep(self.watch_interval)

    def _is_significant_change(self, new_text):
        """Check if screen text changed significantly"""
        if not self.last_text:
            return len(new_text.strip()) > 10

        # Calculate how much text changed
        old_words = set(self.last_text.lower().split())
        new_words = set(new_text.lower().split())
        new_unique = new_words - old_words

        # Trigger if more than 2 new unique words appeared
        return len(new_unique) > 2

    # ── OCR Processing ────────────────────────────────────
    def _enhance_for_ocr(self, image):
        """Enhance image for better text extraction accuracy"""
        try:
            # Convert to numpy for OpenCV processing
            img_array = np.array(image)

            # Convert to grayscale
            if len(img_array.shape) == 3:
                if img_array.shape[2] == 4:
                    gray = cv2.cvtColor(img_array, cv2.COLOR_RGBA2GRAY)
                else:
                    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Increase contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

            # Scale up for better OCR (2x)
            h, w = denoised.shape
            scaled = cv2.resize(denoised, (w*2, h*2), interpolation=cv2.INTER_CUBIC)

            return Image.fromarray(scaled)

        except Exception as e:
            print(f"Enhancement error: {e}")
            return image

    def _extract_text(self, image):
        """Extract text from image using Tesseract"""
        try:
            # OCR config for best accuracy
            custom_config = r'--oem 3 --psm 6 -l eng'
            text = pytesseract.image_to_string(image, config=custom_config)

            # Clean up text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned = '\n'.join(lines)
            
            # Application of Intelligence Filter
            final_text = self._process_intelligence(cleaned)
            return final_text

        except Exception as e:
            print(f"OCR error: {e}")
            return ""

    def _process_intelligence(self, text):
        """
        Premium cleanup: Removes browser noise, URLs, and isolates the 'Ask'.
        """
        import re
        if not text: return ""

        # 1. Strip URLs and browser artifacts
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        
        # 2. Block common junk keywords (Aggressive URL and UI filtering)
        junk_patterns = [
            r'LinkedIn', r'Messaging', r'Gmail', r'CodeSignal', r'Test Instructions',
            r'app\.', r'\.com', r'\(23\)', r'Your CodeSignal', r'practice-question',
            r'context=', r'invitations', r'questiondatabase', r'status=', r'person_id=',
            r'request_id=', r'seat_no=', r'#', r'\/practice', r'\?context'
        ]
        for p in junk_patterns:
            text = re.sub(p, '', text, flags=re.IGNORECASE)

        # 3. Filter out lines that look like a URL segment (long alphanumeric, no spaces)
        lines = []
        for line in text.split('\n'):
            if not line.strip(): continue
            if ' ' not in line.strip() and len(line.strip()) > 15: # likely a URL fragment
                continue
            lines.append(line)  # type: ignore
        text = '\n'.join(lines)

        # 4. Remove non-standard special characters (leaving common punct)
        text = re.sub(r'[^\w\s\?\.\!\,\-\:\(\)]', '', text) # type: ignore[reportGeneralTypeIssues]

        # 4. Deduplicate lines and normalize whitespace
        lines = []
        seen = set()
        for line in text.split('\n'):
            clean_line = line.strip()
            if not clean_line or len(clean_line) < 3: continue
            
            # Simple fuzzy deduplication
            normalized = re.sub(r'\s+', '', clean_line.lower())
            if normalized not in seen:
                lines.append(clean_line)  # type: ignore
                seen.add(normalized)
        
        cleaned_text = '\n'.join(lines)

        # 5. Find the "Ask" (Intelligent Isolate)
        return self._find_the_ask(cleaned_text)

    def _find_the_ask(self, text):
        """
        Heuristic to find the actual question block.
        """
        if not text: return ""
        lines = text.split('\n')
        
        # Priority: Lines ending in '?'
        questions = [l for l in lines if '?' in l]
        if questions:
            # Join all questions if they are short, or return the most substantial one
            return ' '.join(questions)

        # Fallback 1: Look for question/instruction keywords at start of lines
        kw = [
            "what", "how", "why", "which", "can", "is", "explain", "write", "solve",
            "you", "given", "find", "identify", "create", "implement", "calculate"
        ]
        maybe_ask = []
        for l in lines:
            words = l.split()
            if not words: continue
            first_word = words[0].lower().replace(':', '')
            if first_word in kw:
                maybe_ask.append(l)
        
        if maybe_ask:
            # Return up to 8 lines to catch the full instruction block
            return '\n'.join(maybe_ask[:8])  # type: ignore

        # Fallback 2: Look for technical context
        tech_kw = ["table", "column", "function", "array", "string", "integers", "return"]
        for l in lines:
            if any(tk in l.lower() for tk in tech_kw):
                maybe_ask.append(l)
        
        if maybe_ask:
            return '\n'.join(maybe_ask[:8])  # type: ignore

        # Ultimate Fallback: Return the first 8 lines of cleaned text
        return '\n'.join(lines[:8])  # type: ignore

    def get_screen_size(self):
        """Get current screen dimensions"""
        screen = ImageGrab.grab()
        return screen.size  # (width, height)
