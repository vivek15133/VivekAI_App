"""
VivekAI_App - System Tray (Windows + macOS)
Windows: Taskbar tray icon
macOS:   Menu bar icon
"""

from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QBrush
from PyQt5.QtCore import Qt
from ui.platform_utils import is_macos


class SystemTray(QSystemTrayIcon):
    def __init__(self, app, overlay):
        super().__init__(app)
        self.app     = app
        self.overlay = overlay
        self._build_icon()
        self._build_menu()
        self.activated.connect(self._on_tray_click)

    def _build_icon(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        # macOS gets purple icon, Windows gets cyan
        color = "#A855F7" if is_macos() else "#00E5FF"
        p.setBrush(QBrush(QColor(color)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        self.setIcon(QIcon(pixmap))
        plat = "macOS 🍎" if is_macos() else "Windows 🪟"
        self.setToolTip(f"VivekAI v3.0 — {plat}")

    def _build_menu(self):
        menu = QMenu()
        accent = "#A855F7" if is_macos() else "#00E5FF"
        menu.setStyleSheet(f"""
            QMenu {{
                background: #0D1117; color: #E0E0E0;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px; padding: 4px;
                font-family: {'SF Pro Display' if is_macos() else 'Segoe UI'};
                font-size: 13px;
            }}
            QMenu::item {{ padding: 8px 18px; border-radius: 5px; }}
            QMenu::item:selected {{ background: rgba(255,255,255,0.08); }}
            QMenu::separator {{ background: rgba(255,255,255,0.06); height: 1px; margin: 4px 10px; }}
        """)

        icon = "🍎" if is_macos() else "🪟"
        show_act = QAction(f"{icon}  Show VivekAI", self)
        show_act.triggered.connect(self._show_overlay)

        hide_act = QAction("👁  Hide Window", self)
        hide_act.triggered.connect(self.overlay.hide)

        switch_icon = "🪟" if is_macos() else "🍎"
        switch_name = "Windows" if is_macos() else "macOS"
        switch_act = QAction(f"{switch_icon}  Switch to {switch_name}", self)
        switch_act.triggered.connect(self._switch_platform)

        transcript_act = QAction("📁  Open Transcripts", self)
        transcript_act.triggered.connect(self._open_transcripts)

        quit_act = QAction("✕  Quit VivekAI", self)
        quit_act.triggered.connect(self.app.quit)

        menu.addAction(show_act)
        menu.addAction(hide_act)
        menu.addSeparator()
        menu.addAction(switch_act)
        menu.addAction(transcript_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        self.setContextMenu(menu)

    def _show_overlay(self):
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()

    def _switch_platform(self):
        """Reset platform and show selector"""
        from ui.platform_selector import reset_platform, PlatformSelector
        from PyQt5.QtWidgets import QApplication
        reset_platform()
        selector = PlatformSelector()
        selector.platform_selected.connect(self.overlay._on_platform_changed)
        selector.show()
        self._selector = selector

    def _open_transcripts(self):
        from ui.platform_utils import open_folder
        open_folder(self.overlay.transcript_mgr.get_transcript_dir())

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.overlay.isVisible():
                self.overlay.hide()
            else:
                self._show_overlay()
