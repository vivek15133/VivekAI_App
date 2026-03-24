import os
import platform as _platform
from dotenv import load_dotenv  # type: ignore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

# â”€â”€ API KEYS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "") or os.getenv("\ufeffGROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("\ufeffGEMINI_API_KEY", "")

# â”€â”€ WHISPER SETTINGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
WHISPER_MODEL       = "small"
WHISPER_LANGUAGE    = "en"
WHISPER_BEAM_SIZE   = 5
WHISPER_BEST_OF     = 5
WHISPER_TEMPERATURE = 0.0
WHISPER_WORD_TIMESTAMPS = True

# â”€â”€ AUDIO SETTINGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
AUDIO_SAMPLE_RATE   = 16000
AUDIO_CHUNK_SECONDS = 1
AUDIO_CHANNELS      = 1
SILENCE_THRESHOLD   = 0.0001
AUDIO_MAX_SILENCE   = 0.1  # Seconds of silence to trigger EOF
AUDIO_MAX_LENGTH    = 10.0 # Maximum seconds before forcing a chunk

# â”€â”€ AI ENGINE SETTINGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DEFAULT_ENGINE       = "groq"
MAX_RESPONSE_TOKENS  = 300
RESPONSE_TIMEOUT     = 5

# â”€â”€ GROQ MODELS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GROQ_MODEL      = "llama-3.1-8b-instant"
GROQ_FAST_MODEL = "llama-3.1-8b-instant"

# â”€â”€ GEMINI MODELS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GEMINI_MODEL = "gemini-2.0-flash"

# â”€â”€ OLLAMA SETTINGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_HOST  = "http://localhost:11434"

# â”€â”€ TRANSCRIPT DIR â€” Platform aware â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _get_transcript_dir():
    if _platform.system() == "Darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Documents", "VivekAI_Transcripts")
    else:  # Windows
        return os.path.join(os.path.expanduser("~"), "VivekAI_Transcripts")

TRANSCRIPT_DIR     = _get_transcript_dir()
AUTO_SAVE_INTERVAL = 30

# â”€â”€ TESSERACT PATH â€” Platform aware â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _get_tesseract_path():
    if _platform.system() == "Darwin":
        for p in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.exists(p):
                return p
        return "tesseract"
    return r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TESSERACT_PATH = _get_tesseract_path()

# â”€â”€ UI SETTINGS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
WINDOW_OPACITY = 0.93
WINDOW_WIDTH = 360
WINDOW_HEIGHT  = 400
