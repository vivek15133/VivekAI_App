"""
VivekAI_App - Platform Utilities v3.1
Handles cross-platform screen-capture exclusion, paths, and permissions.

FIXED: Proper NSWindowSharingNone via objc runtime (macOS).
       SetWindowDisplayAffinity with WDA_EXCLUDEFROMCAPTURE flag (Windows).
"""

import platform
import subprocess
import os
import ctypes
import ctypes.util


def is_macos():
    return platform.system() == "Darwin"


def is_windows():
    return platform.system() == "Windows"


def get_platform():
    return "macos" if is_macos() else "windows"


# ── Screen-capture exclusion ──────────────────────────────────────────────────

def apply_screen_capture_exclusion(window):
    """
    Make `window` invisible to screen share / OBS / recording on both platforms.
    Call this AFTER the window is shown (so winId() is valid).
    """
    if is_windows():
        _exclude_windows(window)
    elif is_macos():
        _exclude_macos(window)


def _exclude_windows(window):
    """
    SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    WDA_EXCLUDEFROMCAPTURE = 0x00000011  — requires Windows 10 2004+
    """
    try:
        hwnd = int(window.winId())
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        print("[Windows] Screen capture exclusion applied")
    except Exception as e:
        print(f"[Windows] Screen exclusion failed: {e}")


def _exclude_macos(window):
    """
    Set NSWindowSharingNone (= 0) via the ObjC runtime.
    Works on macOS 12+ without PyObjC installed.
    """
    try:
        objc = ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib"
        )
        objc.objc_getClass.restype    = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype     = ctypes.c_void_p
        objc.objc_msgSend.argtypes    = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_void_p]

        ns_view = ctypes.c_void_p(int(window.winId()))
        ns_win  = objc.objc_msgSend(
            ns_view, objc.sel_registerName(b"window"), None
        )
        # NSWindowSharingNone = 0
        objc.objc_msgSend(
            ns_win,
            objc.sel_registerName(b"setSharingType:"),
            ctypes.c_void_p(0)
        )
        print("[macOS] Screen capture exclusion applied")
    except Exception as e:
        print(f"[macOS] Screen exclusion failed: {e}")


# ── Paths ─────────────────────────────────────────────────────────────────────

def get_transcript_dir():
    if is_macos():
        return os.path.join(os.path.expanduser("~"), "Documents", "VivekAI_Transcripts")
    return os.path.join(os.path.expanduser("~"), "VivekAI_Transcripts")


def get_tesseract_path():
    if is_windows():
        return r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    elif is_macos():
        for p in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.exists(p):
                return p
        return "tesseract"
    return "tesseract"


# ── Fonts ─────────────────────────────────────────────────────────────────────

def get_font_family():
    return "SF Pro Display" if is_macos() else "Segoe UI"


# ── File manager ──────────────────────────────────────────────────────────────

def open_folder(path):
    if is_windows():
        subprocess.Popen(f'explorer "{path}"')
    elif is_macos():
        subprocess.Popen(["open", path])


# ── Permissions (macOS) ───────────────────────────────────────────────────────

def check_microphone_permission():
    if is_macos():
        try:
            import AVFoundation
            status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                AVFoundation.AVMediaTypeAudio
            )
            return status == 3
        except Exception:
            return True
    return True


def request_microphone_permission():
    if is_macos():
        try:
            script = (
                'tell application "System Preferences"\n'
                '    activate\n'
                '    set current pane to pane id "com.apple.preference.security"\n'
                'end tell'
            )
            subprocess.Popen(["osascript", "-e", script])
        except Exception:
            pass


# ── Window flags ──────────────────────────────────────────────────────────────

def get_window_flags_for_platform():
    from PyQt5.QtCore import Qt
    flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    if is_macos():
        flags |= Qt.WindowDoesNotAcceptFocus
    return flags


# ── Platform info ─────────────────────────────────────────────────────────────

def get_platform_info():
    return {
        "platform": get_platform(),
        "system":   platform.system(),
        "release":  platform.release(),
        "version":  platform.version(),
        "machine":  platform.machine(),
    }


# ── Saved-platform reset ──────────────────────────────────────────────────────

def reset_platform():
    """Delete saved platform choice so the selector appears on next launch."""
    try:
        p = os.path.join(os.path.expanduser("~"), ".vivekaiplatform")
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass
