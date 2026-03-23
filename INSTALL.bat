@echo off
title VivekAI App - Installer
color 0B
cls

echo.
echo  ============================================
echo    VIVEK AI - Installation Setup
echo  ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo  Please install Python 3.11 from https://python.org
    echo  Make sure to check "Add Python to PATH" during install
    pause
    exit
)

echo  [1/6] Python found ✓
echo.

:: Upgrade pip
echo  [2/6] Upgrading pip...
python -m pip install --upgrade pip --quiet

:: Install requirements
echo  [3/6] Installing dependencies (this takes 3-5 minutes)...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to install dependencies
    echo  Try running as Administrator
    pause
    exit
)
echo  Dependencies installed ✓

:: Install PyInstaller for .exe build
echo  [4/6] Installing PyInstaller...
pip install pyinstaller --quiet
echo  PyInstaller installed ✓

:: Copy .env template
echo  [5/6] Setting up config...
if not exist .env (
    copy .env.template .env >nul
    echo  [ACTION NEEDED] Open .env file and add your API keys!
) else (
    echo  Config file exists ✓
)

:: Create transcripts folder
if not exist "%USERPROFILE%\VivekAI_Transcripts" (
    mkdir "%USERPROFILE%\VivekAI_Transcripts"
    echo  Transcripts folder created ✓
)

echo  [6/6] Building VivekAI.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "VivekAI" ^
    --icon=assets\icon.ico ^
    --add-data "config.py;." ^
    --add-data "modes;modes" ^
    --hidden-import "whisper" ^
    --hidden-import "pyaudio" ^
    --hidden-import "groq" ^
    --hidden-import "google.generativeai" ^
    main.py

if errorlevel 1 (
    echo.
    echo  [WARNING] .exe build had issues.
    echo  You can still run the app with: python main.py
) else (
    echo.
    echo  ============================================
    echo    BUILD SUCCESSFUL!
    echo    VivekAI.exe is in the 'dist' folder
    echo  ============================================
)

echo.
echo  ============================================
echo    SETUP COMPLETE!
echo  ============================================
echo.
echo  NEXT STEPS:
echo  1. Open '.env' file and add your API keys:
echo     - GROQ_API_KEY    (from console.groq.com)
echo     - GEMINI_API_KEY  (from aistudio.google.com)
echo.
echo  2. Install Ollama for offline use (optional):
echo     Download from: https://ollama.com
echo     Then run: ollama pull llama3.2:3b
echo.
echo  3. For system audio capture (Teams/Zoom audio):
echo     Install VB-Audio Cable from:
echo     https://vb-audio.com/Cable/
echo.
echo  4. Run the app:
echo     Option A: Double-click 'dist\VivekAI.exe'
echo     Option B: Run 'python main.py'
echo.
echo  IMPORTANT: The app is INVISIBLE to screen share!
echo  Only YOU can see it on your screen.
echo.
pause
