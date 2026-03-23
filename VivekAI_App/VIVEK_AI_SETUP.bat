@echo off
setlocal enabledelayedexpansion
title VivekAI v3.0 - Complete Setup Wizard
color 0A
cls

echo.
echo  ██╗   ██╗██╗██╗   ██╗███████╗██╗  ██╗ █████╗ ██╗
echo  ██║   ██║██║██║   ██║██╔════╝██║ ██╔╝██╔══██╗██║
echo  ██║   ██║██║██║   ██║█████╗  █████╔╝ ███████║██║
echo  ╚██╗ ██╔╝██║╚██╗ ██╔╝██╔══╝  ██╔═██╗ ██╔══██║██║
echo   ╚████╔╝ ██║ ╚████╔╝ ███████╗██║  ██╗██║  ██║██║
echo    ╚═══╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝
echo.
echo   v3.0  |  Windows Edition  |  Mic + Screenshot + Auto Watch
echo   Built for: Vivek  ^|  Windows 10/11
echo.
echo  ═══════════════════════════════════════════════════
echo.

:: ── Admin check ──────────────────────────────────────────
net session >nul 2>&1
if errorlevel 1 (
    echo  [!] Please right-click and "Run as Administrator"
    echo  Continuing in 3 seconds...
    timeout /t 3 /nobreak >nul
)

:: ── STEP 1: Python check ─────────────────────────────────
echo  [STEP 1/9]  Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [X] Python NOT found!
    echo  Install from: https://www.python.org/downloads/
    echo  CHECK: Add Python to PATH during install!
    pause & exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [✓] Python %PYVER% found
echo.

:: ── STEP 2: pip upgrade ──────────────────────────────────
echo  [STEP 2/9]  Upgrading pip...
python -m pip install --upgrade pip -q
echo  [✓] pip upgraded
echo.

:: ── STEP 3: FFmpeg ───────────────────────────────────────
echo  [STEP 3/9]  Checking FFmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    pip install imageio-ffmpeg -q
    echo  [✓] FFmpeg installed via pip
) else (
    echo  [✓] FFmpeg found
)
echo.

:: ── STEP 4: Tesseract OCR (NEW - for screen reading) ─────
echo  [STEP 4/9]  Checking Tesseract OCR (screen reader)...
tesseract --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Tesseract not found. Installing...
    echo.
    echo  ┌─────────────────────────────────────────────────┐
    echo  │  TESSERACT OCR - Required for Screen Reading    │
    echo  │                                                 │
    echo  │  Please install manually (takes 2 minutes):    │
    echo  │                                                 │
    echo  │  1. Open this link in your browser:            │
    echo  │     https://github.com/UB-Mannheim/tesseract   │
    echo  │     /wiki/Downloading-Tesseract-at-UB-Mannheim │
    echo  │                                                 │
    echo  │  2. Download: tesseract-ocr-w64-setup-5.x.exe  │
    echo  │                                                 │
    echo  │  3. Install to DEFAULT path:                   │
    echo  │     C:\Program Files\Tesseract-OCR\            │
    echo  │                                                 │
    echo  │  4. Come back here and press any key           │
    echo  └─────────────────────────────────────────────────┘
    echo.
    pause
    tesseract --version >nul 2>&1
    if errorlevel 1 (
        echo  [!] Tesseract still not found.
        echo  Screenshot OCR will use Gemini Vision instead.
        echo  Screen reading will still work via AI vision!
    ) else (
        echo  [✓] Tesseract installed successfully!
    )
) else (
    echo  [✓] Tesseract OCR found
)
echo.

:: ── STEP 5: Python packages ──────────────────────────────
echo  [STEP 5/9]  Installing Python packages (5-10 mins)...
echo.
pip install ^
    openai-whisper ^
    pyaudio ^
    noisereduce ^
    soundfile ^
    numpy ^
    PyQt5 ^
    pyperclip ^
    groq ^
    google-generativeai ^
    requests ^
    python-dotenv ^
    pillow ^
    pytesseract ^
    opencv-python ^
    pyinstaller ^
    -q --no-warn-script-location

echo  [✓] All packages installed
echo.

:: ── STEP 6: Folder structure ─────────────────────────────
echo  [STEP 6/9]  Creating project files...
if not exist "audio" mkdir audio
if not exist "ai" mkdir ai
if not exist "modes" mkdir modes
if not exist "storage" mkdir storage
if not exist "ui" mkdir ui
if not exist "assets" mkdir assets
echo. > audio\__init__.py
echo. > ai\__init__.py
echo. > modes\__init__.py
echo. > storage\__init__.py
echo. > ui\__init__.py
echo  [✓] Structure ready
echo.

:: ── STEP 7: API Keys ─────────────────────────────────────
echo  [STEP 7/9]  API Key Configuration
echo  ═══════════════════════════════════════════════════
echo.

if exist ".env" (
    echo  [✓] .env file exists - skipping
    goto :skip_keys
)

echo  ┌─ GROQ API KEY (Free - Fastest AI) ────────────────┐
echo  │  Get FREE at: https://console.groq.com           │
echo  └────────────────────────────────────────────────────┘
set /p GROQ_KEY="  Paste GROQ Key (or Enter to skip): "

echo.
echo  ┌─ GEMINI API KEY (Vision + AI) ────────────────────┐
echo  │  REQUIRED for Screenshot feature                  │
echo  │  Get FREE at: https://aistudio.google.com        │
echo  └────────────────────────────────────────────────────┘
set /p GEMINI_KEY="  Paste GEMINI Key (or Enter to skip): "

echo # VivekAI API Keys > .env
echo GROQ_API_KEY=!GROQ_KEY! >> .env
echo GEMINI_API_KEY=!GEMINI_KEY! >> .env
echo  [✓] Keys saved to .env
echo.
:skip_keys

:: ── STEP 8: Transcripts folder ───────────────────────────
echo  [STEP 8/9]  Setting up storage...
if not exist "%USERPROFILE%\VivekAI_Transcripts" (
    mkdir "%USERPROFILE%\VivekAI_Transcripts"
)
echo  [✓] Transcripts: %USERPROFILE%\VivekAI_Transcripts
echo.

:: ── STEP 9: Build EXE ────────────────────────────────────
echo  [STEP 9/9]  Building VivekAI v2.0 EXE...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "VivekAI" ^
    --add-data ".env;." ^
    --add-data "config.py;." ^
    --add-data "modes;modes" ^
    --add-data "audio;audio" ^
    --add-data "ai;ai" ^
    --add-data "storage;storage" ^
    --add-data "ui;ui" ^
    --hidden-import "whisper" ^
    --hidden-import "pyaudio" ^
    --hidden-import "groq" ^
    --hidden-import "pytesseract" ^
    --hidden-import "cv2" ^
    --hidden-import "PIL" ^
    --hidden-import "google.generativeai" ^
    --hidden-import "PyQt5.QtWidgets" ^
    --hidden-import "PyQt5.QtCore" ^
    --hidden-import "PyQt5.QtGui" ^
    --clean --noconfirm ^
    main.py >nul 2>&1

if exist "dist\VivekAI.exe" (
    echo.
    echo  ═══════════════════════════════════════════════════
    echo   ✅  VIVEKIA v3.0 BUILD SUCCESSFUL!
    echo.
    echo   App ready at: dist\VivekAI.exe
    echo.
    echo   NEW FEATURES:
    echo   📸  Screenshot Tab - Capture screen, AI answers
    echo   👁  Auto Watch Tab - Watches region, auto-answers
    echo   🎙  Mic Tab - Original voice listening
    echo  ═══════════════════════════════════════════════════
    echo.
    set /p LAUNCH="  Launch VivekAI v2.0 now? (Y/N): "
    if /i "!LAUNCH!"=="Y" start "" "dist\VivekAI.exe"
) else (
    echo  [!] EXE build had issues. Running with Python...
    set /p LAUNCH="  Run VivekAI now with Python? (Y/N): "
    if /i "!LAUNCH!"=="Y" python main.py
)

echo.
echo  ══════════════════════════════════════════
echo   IMPORTANT NOTES:
echo.
echo   For Screenshot feature:
echo   - Gemini API key REQUIRED (for vision AI)
echo   - Tesseract OCR helps extract text too
echo.  
echo   For Auto Watch:
echo   - Select a region OR use full screen
echo   - Set check interval (1-5 seconds)
echo   - AI auto-answers when new text appears
echo.
echo   For system audio capture:
echo   Install VB-Audio: https://vb-audio.com/Cable/
echo  ══════════════════════════════════════════
echo.
pause
