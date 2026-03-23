#!/bin/bash
# ═══════════════════════════════════════════════════════════
#   VivekAI v3.0 — macOS Complete Installer
#   Supports: macOS 12 Monterey+ | Intel + Apple Silicon
# ═══════════════════════════════════════════════════════════

clear
echo ""
echo "  ██╗   ██╗██╗██╗   ██╗███████╗██╗  ██╗ █████╗ ██╗"
echo "  ██║   ██║██║██║   ██║██╔════╝██║ ██╔╝██╔══██╗██║"
echo "  ╚██╗ ██╔╝██║╚██╗ ██╔╝███████╗██║  ██╗██║  ██║██║"
echo ""
echo "   v3.0  |  macOS Edition  🍎"
echo "   Mic + Screenshot + Auto Watch"
echo ""
echo "  ═══════════════════════════════════════════════════"
echo ""

# ── STEP 1: Check macOS version ─────────────────────────
echo "  [STEP 1/9]  Checking macOS version..."
OS_VERSION=$(sw_vers -productVersion)
echo "  [✓] macOS $OS_VERSION detected"
echo ""

# ── STEP 2: Check/Install Homebrew ──────────────────────
echo "  [STEP 2/9]  Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "  [!] Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add to PATH for Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    echo "  [✓] Homebrew installed"
else
    echo "  [✓] Homebrew found"
fi
echo ""

# ── STEP 3: Check/Install Python ────────────────────────
echo "  [STEP 3/9]  Checking Python 3.11..."
if ! command -v python3 &>/dev/null; then
    echo "  [!] Python not found. Installing via Homebrew..."
    brew install python@3.11
    echo "  [✓] Python 3.11 installed"
else
    PYVER=$(python3 --version 2>&1)
    echo "  [✓] $PYVER found"
fi
echo ""

# ── STEP 4: Install FFmpeg ───────────────────────────────
echo "  [STEP 4/9]  Checking FFmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "  [!] FFmpeg not found. Installing..."
    brew install ffmpeg
    echo "  [✓] FFmpeg installed"
else
    echo "  [✓] FFmpeg found"
fi
echo ""

# ── STEP 5: Install Tesseract OCR ───────────────────────
echo "  [STEP 5/9]  Checking Tesseract OCR..."
if ! command -v tesseract &>/dev/null; then
    echo "  [!] Tesseract not found. Installing..."
    brew install tesseract
    echo "  [✓] Tesseract installed"
else
    echo "  [✓] Tesseract found"
fi
echo ""

# ── STEP 6: Install Python packages ────────────────────
echo "  [STEP 6/9]  Installing Python packages (5-10 mins)..."
echo ""

pip3 install \
    openai-whisper \
    pyaudio \
    noisereduce \
    soundfile \
    numpy \
    PyQt5 \
    pyperclip \
    groq \
    google-generativeai \
    requests \
    python-dotenv \
    pillow \
    pytesseract \
    opencv-python \
    pyinstaller \
    -q --no-warn-script-location

echo "  [✓] All packages installed"
echo ""

# ── STEP 7: Create folder structure ────────────────────
echo "  [STEP 7/9]  Creating project structure..."
mkdir -p audio ai modes storage ui assets
touch audio/__init__.py ai/__init__.py modes/__init__.py storage/__init__.py ui/__init__.py
echo "  [✓] Structure ready"

# Create transcript folder
TRANSCRIPT_DIR="$HOME/Documents/VivekAI_Transcripts"
mkdir -p "$TRANSCRIPT_DIR"
echo "  [✓] Transcripts: $TRANSCRIPT_DIR"
echo ""

# ── STEP 8: API Keys setup ──────────────────────────────
echo "  [STEP 8/9]  API Key Configuration"
echo "  ═══════════════════════════════════════════════════"
echo ""

if [ -f ".env" ]; then
    echo "  [✓] .env file exists — skipping"
else
    echo "  ┌─ GROQ API KEY (Free — Fastest) ─────────────────┐"
    echo "  │  Get FREE at: https://console.groq.com         │"
    echo "  └──────────────────────────────────────────────────┘"
    echo ""
    read -p "  Paste your GROQ API Key (or Enter to skip): " GROQ_KEY
    echo ""

    echo "  ┌─ GEMINI API KEY (Required for Screenshot) ───────┐"
    echo "  │  Get FREE at: https://aistudio.google.com       │"
    echo "  └──────────────────────────────────────────────────┘"
    echo ""
    read -p "  Paste your GEMINI API Key (or Enter to skip): " GEMINI_KEY

    echo "# VivekAI API Keys" > .env
    echo "GROQ_API_KEY=$GROQ_KEY" >> .env
    echo "GEMINI_API_KEY=$GEMINI_KEY" >> .env
    echo ""
    echo "  [✓] Keys saved to .env"
fi
echo ""

# ── STEP 9: Build macOS app bundle ─────────────────────
echo "  [STEP 9/9]  Building VivekAI.app for macOS..."

pyinstaller \
    --onefile \
    --windowed \
    --name "VivekAI" \
    --osx-bundle-identifier "com.vivek.vivekaiapp" \
    --add-data ".env:." \
    --add-data "config.py:." \
    --add-data "modes:modes" \
    --add-data "audio:audio" \
    --add-data "ai:ai" \
    --add-data "storage:storage" \
    --add-data "ui:ui" \
    --hidden-import "whisper" \
    --hidden-import "pyaudio" \
    --hidden-import "groq" \
    --hidden-import "pytesseract" \
    --hidden-import "cv2" \
    --hidden-import "PIL" \
    --hidden-import "google.generativeai" \
    --hidden-import "PyQt5.QtWidgets" \
    --hidden-import "PyQt5.QtCore" \
    --hidden-import "PyQt5.QtGui" \
    --clean --noconfirm \
    main.py 2>/dev/null

if [ -f "dist/VivekAI" ]; then
    echo ""
    echo "  ═══════════════════════════════════════════════════"
    echo "   ✅  VIVEKIA v3.0 macOS BUILD SUCCESSFUL!"
    echo ""
    echo "   App ready at: dist/VivekAI"
    echo ""
    echo "   To install to Applications:"
    echo "   cp -r dist/VivekAI /Applications/"
    echo "  ═══════════════════════════════════════════════════"
    echo ""

    read -p "  Launch VivekAI now? (y/n): " LAUNCH
    if [[ "$LAUNCH" == "y" || "$LAUNCH" == "Y" ]]; then
        open dist/VivekAI &
    fi
else
    echo ""
    echo "  [!] Build had issues. Running with Python directly..."
    read -p "  Run VivekAI now? (y/n): " LAUNCH
    if [[ "$LAUNCH" == "y" || "$LAUNCH" == "Y" ]]; then
        python3 main.py &
    fi
fi

echo ""
echo "  ══════════════════════════════════════════"
echo "   macOS NOTES:"
echo ""
echo "   Microphone permission:"
echo "   System Preferences > Privacy > Microphone"
echo "   Enable for VivekAI"
echo ""
echo "   For Accessibility (screen reading):"
echo "   System Preferences > Privacy > Accessibility"
echo "   Enable for VivekAI"
echo ""
echo "   For system audio capture:"
echo "   Install BlackHole (free): github.com/ExistentialAudio/BlackHole"
echo "   brew install blackhole-2ch"
echo "  ══════════════════════════════════════════"
echo ""
read -p "  Press Enter to exit..."
