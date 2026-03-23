"""
VivekAI_App - Platform Selector
First launch screen — user chooses Windows or macOS
Saves choice to config, never asks again
"""

import sys
import os
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QApplication, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QBrush, QLinearGradient, QPen, QFont

PLATFORM_FILE = os.path.join(os.path.expanduser("~"), ".vivekaiplatform")


def get_saved_platform():
    """Return saved platform or None if first launch"""
    try:
        if os.path.exists(PLATFORM_FILE):
            with open(PLATFORM_FILE, "r") as f:
                data = json.load(f)
                return data.get("platform")
    except:
        pass
    return None


def save_platform(platform):
    """Save chosen platform for future launches"""
    try:
        with open(PLATFORM_FILE, "w") as f:
            json.dump({"platform": platform}, f)
    except:
        pass


def reset_platform():
    """Reset saved platform — forces selector to show again"""
    try:
        if os.path.exists(PLATFORM_FILE):
            os.remove(PLATFORM_FILE)
    except:
        pass


class PlatformCard(QFrame):
    """Clickable platform card"""
    clicked = pyqtSignal(str)

    def __init__(self, platform, icon, title, subtitle, features, color, parent=None):
        super().__init__(parent)
        self.platform = platform
        self.color = color
        self.selected = False
        self._build(icon, title, subtitle, features, color)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(280, 380)

    def _build(self, icon, title, subtitle, features, color):
        self.setObjectName("platformCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 24)
        layout.setSpacing(0)

        # Icon
        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"font-size: 52px; margin-bottom: 12px;")

        # Title
        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color: {color}; font-size: 22px; font-weight: 700; "
            f"font-family: 'Segoe UI'; letter-spacing: 1px; margin-bottom: 4px;"
        )

        # Subtitle
        sub_lbl = QLabel(subtitle)
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setStyleSheet(
            "color: #6B7280; font-size: 11px; font-family: 'Segoe UI'; "
            "margin-bottom: 20px;"
        )
        sub_lbl.setWordWrap(True)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: rgba(255,255,255,0.06); margin-bottom: 16px;")

        # Features
        feat_layout = QVBoxLayout()
        feat_layout.setSpacing(8)
        for feat in features:
            row = QHBoxLayout()
            row.setSpacing(8)
            check = QLabel("✓")
            check.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700;")
            check.setFixedWidth(16)
            text = QLabel(feat)
            text.setStyleSheet("color: #9CA3AF; font-size: 11px; font-family: 'Segoe UI';")
            row.addWidget(check)
            row.addWidget(text)
            row.addStretch()
            feat_layout.addLayout(row)

        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(sub_lbl)
        layout.addWidget(div)
        layout.addLayout(feat_layout)
        layout.addStretch()

        self._update_style()

    def _update_style(self):
        col = self.color
        if self.selected:
            self.setStyleSheet(f"""
                QFrame#platformCard {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(20,30,50,0.98), stop:1 rgba(12,18,36,0.98));
                    border: 2px solid {col};
                    border-radius: 16px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#platformCard {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(16,22,40,0.95), stop:1 rgba(10,14,26,0.95));
                    border: 1px solid rgba(255,255,255,0.08);
                    border-radius: 16px;
                }}
                QFrame#platformCard:hover {{
                    border: 1px solid {col};
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(20,28,48,0.98), stop:1 rgba(14,20,40,0.98));
                }}
            """)

    def set_selected(self, selected):
        self.selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.platform)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selected:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            # Glow effect at top
            grad = QLinearGradient(0, 0, 0, 60)
            col = QColor(self.color)
            col.setAlpha(40)
            grad.setColorAt(0, col)
            col.setAlpha(0)
            grad.setColorAt(1, col)
            p.fillRect(0, 0, self.width(), 60, grad)


class PlatformSelector(QWidget):
    """
    Full-screen platform selection dialog
    Shown only on first launch
    """
    platform_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.chosen = None
        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def _build_ui(self):
        # Full screen semi-transparent overlay
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(0)

        # Center dialog
        dialog = QFrame()
        dialog.setFixedSize(720, 580)
        dialog.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(10,13,22,0.99), stop:1 rgba(6,9,18,0.99));
                border: 1px solid rgba(0,229,255,0.2);
                border-radius: 20px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 20)
        dialog.setGraphicsEffect(shadow)

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(40, 36, 40, 36)
        dlg_layout.setSpacing(0)

        # Header
        logo = QLabel("●")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("color: #00E5FF; font-size: 18px; margin-bottom: 4px;")

        title = QLabel("Welcome to VivekAI")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color: #FFFFFF; font-size: 26px; font-weight: 700; "
            "font-family: 'Segoe UI'; letter-spacing: -0.5px; margin-bottom: 6px;"
        )

        subtitle = QLabel("Please select your operating system to continue")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            "color: #6B7280; font-size: 13px; font-family: 'Segoe UI'; "
            "margin-bottom: 28px;"
        )

        dlg_layout.addWidget(logo)
        dlg_layout.addWidget(title)
        dlg_layout.addWidget(subtitle)

        # Cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        cards_row.setAlignment(Qt.AlignCenter)

        self.win_card = PlatformCard(
            platform="windows",
            icon="🪟",
            title="Windows",
            subtitle="Windows 10 / 11\n64-bit",
            features=[
                "Invisible to screen share",
                "Groq + Gemini + Ollama",
                "Screenshot feature",
                "Auto Watch feature",
                "One-click .exe installer",
                "System tray support",
            ],
            color="#00E5FF"
        )

        self.mac_card = PlatformCard(
            platform="macos",
            icon="🍎",
            title="macOS",
            subtitle="macOS 12 Monterey or later\nApple Silicon + Intel",
            features=[
                "Invisible to screen share",
                "Groq + Gemini + Ollama",
                "Screenshot feature",
                "Auto Watch feature",
                "One-click .sh installer",
                "Menu bar support",
            ],
            color="#A855F7"
        )

        self.win_card.clicked.connect(self._on_card_click)
        self.mac_card.clicked.connect(self._on_card_click)

        cards_row.addWidget(self.win_card)
        cards_row.addWidget(self.mac_card)
        dlg_layout.addLayout(cards_row)
        dlg_layout.addSpacing(24)

        # Continue button
        self.continue_btn = QPushButton("Select a platform above to continue →")
        self.continue_btn.setFixedHeight(48)
        self.continue_btn.setEnabled(False)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                color: #4B5563;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI';
            }
        """)
        self.continue_btn.clicked.connect(self._on_continue)
        dlg_layout.addWidget(self.continue_btn)

        dlg_layout.addSpacing(12)

        # Remember note
        note = QLabel("Your choice will be remembered — you won't be asked again")
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet(
            "color: #374151; font-size: 10px; font-family: 'Segoe UI';"
        )
        dlg_layout.addWidget(note)

        layout.addWidget(dialog)

    def _on_card_click(self, platform):
        self.chosen = platform
        self.win_card.set_selected(platform == "windows")
        self.mac_card.set_selected(platform == "macos")

        # Update button
        label = "🪟  Continue with Windows →" if platform == "windows" else "🍎  Continue with macOS →"
        color = "#00E5FF" if platform == "windows" else "#A855F7"
        self.continue_btn.setEnabled(True)
        self.continue_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {color}, stop:1 {'#0099BB' if platform == 'windows' else '#7C3AED'});
                color: {'#000000' if platform == 'windows' else '#FFFFFF'};
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        self.continue_btn.setText(label)

    def _on_continue(self):
        if self.chosen:
            save_platform(self.chosen)
            self.platform_selected.emit(self.chosen)
            self.close()

    def paintEvent(self, event):
        """Dark overlay behind dialog"""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 160))
