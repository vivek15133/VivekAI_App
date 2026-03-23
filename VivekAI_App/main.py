"""
VivekAI_App v3.0 - Main Entry Point
Supports: Windows 10/11 + macOS 12+
Shows platform selector on first launch
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer

from ui.platform_selector import PlatformSelector, get_saved_platform
from ui.platform_utils import get_platform, apply_screen_capture_exclusion
from ui.tray import SystemTray


def launch_app(platform_choice):
    """Launch main overlay after platform is chosen"""
    from ui.overlay import VivekAIOverlay

    overlay = VivekAIOverlay(platform=platform_choice)
    tray = SystemTray(app, overlay)
    tray.show()
    overlay.show()

    # Store references to prevent garbage collection
    app._overlay = overlay
    app._tray = tray


def main():
    global app
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("VivekAI")
    app.setApplicationVersion("3.0")

    # Check if platform already saved from previous launch
    saved_platform = get_saved_platform()

    if saved_platform:
        # Platform already chosen — launch directly
        print(f"[VivekAI] Launching for saved platform: {saved_platform}")
        QTimer.singleShot(100, lambda: launch_app(saved_platform))
    else:
        # First launch — show platform selector
        print("[VivekAI] First launch — showing platform selector")
        selector = PlatformSelector()
        selector.platform_selected.connect(launch_app)
        selector.show()
        app._selector = selector

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
