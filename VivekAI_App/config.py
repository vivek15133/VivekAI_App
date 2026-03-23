import os
import platform as _platform
from dotenv import load_dotenv

load_dotenv()

# ── API KEYS ──────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── WHISPER SETTINGS ─────────────────────────────────────
WHISPER_MODEL       = "small"
WHISPER_LANGUAGE    = "en"
WHISPER_BEAM_SIZE   = 5
WHISPER_BEST_OF     = 5
WHISPER_TEMPERATURE = 0.0
WHISPER_WORD_TIMESTAMPS = True

# ── AUDIO SETTINGS ────────────────────────────────────────
AUDIO_SAMPLE_RATE   = 16000
AUDIO_CHUNK_SECONDS = 5
AUDIO_CHANNELS      = 1
SILENCE_THRESHOLD   = 0.01

# ── AI ENGINE SETTINGS ────────────────────────────────────
DEFAULT_ENGINE       = "groq"
MAX_RESPONSE_TOKENS  = 300
RESPONSE_TIMEOUT     = 5

# ── GROQ MODELS ───────────────────────────────────────────
GROQ_MODEL      = "llama-3.1-8b-instant"
GROQ_FAST_MODEL = "llama-3.1-8b-instant"

# ── GEMINI MODELS ─────────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"

# ── OLLAMA SETTINGS ───────────────────────────────────────
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_HOST  = "http://localhost:11434"

# ── TRANSCRIPT DIR — Platform aware ───────────────────────
def _get_transcript_dir():
    if _platform.system() == "Darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Documents", "VivekAI_Transcripts")
    else:  # Windows
        return os.path.join(os.path.expanduser("~"), "VivekAI_Transcripts")

TRANSCRIPT_DIR     = _get_transcript_dir()
AUTO_SAVE_INTERVAL = 30

# ── TESSERACT PATH — Platform aware ───────────────────────
def _get_tesseract_path():
    if _platform.system() == "Darwin":
        for p in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.exists(p):
                return p
        return "tesseract"
    return r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TESSERACT_PATH = _get_tesseract_path()

# ── UI SETTINGS ───────────────────────────────────────────
WINDOW_OPACITY = 0.93
WINDOW_WIDTH   = 480
WINDOW_HEIGHT  = 600
