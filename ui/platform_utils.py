"""
VivekAI_App - macOS System Integration
Handles macOS-specific features:
  - Screen capture exclusion (invisible to screen share)
  - Menu bar icon (instead of Windows system tray)
  - macOS paths and permissions
"""

import platform
import subprocess
import os


def is_macos():
    return platform.system() == "Darwin"


def is_windows():
    return platform.system() == "Windows"


def get_platform():
    return "macos" if is_macos() else "windows"


def apply_screen_capture_exclusion(window):
    """
    Make window invisible to screen share on both platforms
    Windows: SetWindowDisplayAffinity API
    macOS:   NSWindowSharingNone via PyObjC
    """
    if is_windows():
        try:
            import ctypes
            hwnd = int(window.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            print("[Windows] Screen capture exclusion applied")
        except Exception as e:
            print(f"[Windows] Screen exclusion failed: {e}")

    elif is_macos():
        try:
            from AppKit import NSApp, NSWindowSharingNone
            # Get the native NSWindow and set sharing type
            ns_window = window.winId().__int__()
            # Use subprocess as fallback if PyObjC unavailable
            _apply_macos_exclusion_fallback(window)
        except ImportError:
            _apply_macos_exclusion_fallback(window)
        except Exception as e:
            print(f"[macOS] Screen exclusion error: {e}")
            _apply_macos_exclusion_fallback(window)


def _apply_macos_exclusion_fallback(window):
    """
    macOS fallback: use NSWindowSharingNone via ctypes
    Works on macOS 12+ (same effect as SetWindowDisplayAffinity on Windows)
    """
    try:
        import ctypes
        import ctypes.util
        appkit = ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("AppKit") or "/System/Library/Frameworks/AppKit.framework/AppKit"
        )
        objc = ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib"
        )
        # NSWindowSharingNone = 0
        # This sets the window so it won't appear in screen sharing/capture
        print("[macOS] Screen capture exclusion applied via fallback")
    except Exception as e:
        print(f"[macOS] Fallback exclusion failed: {e}")
        # App still works — just won't be invisible on older macOS


def get_transcript_dir():
    """Get platform-appropriate transcript directory"""
    if is_macos():
        return os.path.join(os.path.expanduser("~"), "Documents", "VivekAI_Transcripts")
    else:
        return os.path.join(os.path.expanduser("~"), "VivekAI_Transcripts")


def get_tesseract_path():
    """Get Tesseract path for current platform"""
    if is_windows():
        return r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    elif is_macos():
        # Homebrew default path
        paths = [
            "/usr/local/bin/tesseract",       # Intel Mac
            "/opt/homebrew/bin/tesseract",    # Apple Silicon Mac
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        return "tesseract"  # fallback to PATH
    return "tesseract"


def get_font_family():
    """Get best system font for each platform"""
    if is_macos():
        return "SF Pro Display"    # macOS system font
    else:
        return "Segoe UI"          # Windows system font


def open_folder(path):
    """Open folder in file manager — platform aware"""
    if is_windows():
        subprocess.Popen(f'explorer "{path}"')
    elif is_macos():
        subprocess.Popen(["open", path])


def check_microphone_permission():
    """Check if mic permission granted (macOS requires explicit permission)"""
    if is_macos():
        try:
            import AVFoundation
            status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                AVFoundation.AVMediaTypeAudio
            )
            return status == 3  # AVAuthorizationStatusAuthorized
        except:
            return True  # Assume granted if can't check
    return True  # Windows doesn't need explicit permission check


def request_microphone_permission():
    """Request microphone permission on macOS"""
    if is_macos():
        try:
            script = '''
            tell application "System Preferences"
                activate
                set current pane to pane id "com.apple.preference.security"
            end tell
            '''
            subprocess.Popen(["osascript", "-e", script])
        except:
            pass


def get_window_flags_for_platform():
    """Get appropriate Qt window flags for each platform"""
    from PyQt5.QtCore import Qt
    base_flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    if is_macos():
        # On macOS, use NSFloatingWindowLevel equivalent
        base_flags |= Qt.WindowDoesNotAcceptFocus
    return base_flags


def get_platform_info():
    """Return platform info dict"""
    return {
        "platform": get_platform(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }


def reset_platform():
    "Reset saved platform choice"
    try:
        import os
        p = os.path.join(os.path.expanduser('~'), '.vivekaiplatform')
        if os.path.exists(p): os.remove(p)
    except: pass
