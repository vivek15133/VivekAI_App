"""
VivekAI_App - Overlay UI v3.1
FIXES:
  • RegionSelector & overlay are now INVISIBLE to screen share / OBS
  • Resize-handle cursors hidden from screen capture (only you see them)
  • Window resize arrows suppressed on screen share target
  • Resume upload tab — auto-builds AI context from PDF/DOCX/TXT
Supports: Windows 10/11 + macOS 12+
"""

import sys
import os
import threading
import pyperclip  # type: ignore
from datetime import datetime
from PyQt5.QtWidgets import (  # type: ignore
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QApplication,
    QFrame, QTabWidget, QMenu, QAction, QFileDialog,
    QScrollArea
)
from PyQt5.QtCore import (  # type: ignore
    Qt, QTimer, pyqtSignal, QObject, QThread,
    QPoint, QRect, QSize, QEvent
)
from PyQt5.QtGui import QColor, QFont, QPainter, QBrush, QPen, QCursor  # type: ignore
from typing import Optional, Tuple, Any

# Pixel zone near each edge that acts as a resize handle
RESIZE_MARGIN = 16

import config  # type: ignore
from modes.prompts import get_mode_list, get_mode_icon, get_system_prompt  # type: ignore
from ai.engine import AIEngine  # type: ignore
from ai.vision_client import VisionAIClient  # type: ignore
from audio.capture import AudioCapture  # type: ignore
from audio.transcriber import Transcriber  # type: ignore
from audio.screen_vision import ScreenVision  # type: ignore
from storage.transcript_manager import TranscriptManager  # type: ignore
from ui.region_selector import RegionSelector  # type: ignore
from ui.platform_utils import (  # type: ignore
    apply_screen_capture_exclusion, get_font_family,
    open_folder, get_window_flags_for_platform, is_macos
)

# ── Resume parser (graceful import) ──────────────────────────────────────────
try:
    from ai.resume_parser import (  # type: ignore
        extract_text_from_file, parse_resume,
        build_resume_context, get_resume_enhanced_prompt
    )
    RESUME_AVAILABLE = True
except ImportError:
    RESUME_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Worker signals & threads
# ─────────────────────────────────────────────────────────────────────────────

class WorkerSignals(QObject):
    transcript_ready  = pyqtSignal(str)
    response_ready    = pyqtSignal(str, str, float)
    status_update     = pyqtSignal(str)
    model_loaded      = pyqtSignal()
    screen_text_ready = pyqtSignal(str)
    vision_ready      = pyqtSignal(str, str, float)


class AIWorker(QThread):
    def __init__(self, text, system_prompt, engine, signals):
        super().__init__()
        self.text          = text
        self.system_prompt = system_prompt
        self.engine        = engine
        self.signals       = signals

    def run(self):
        import time
        try:
            response, eng, elapsed = self.engine.generate(
                self.text, self.system_prompt
            )
            self.signals.response_ready.emit(response, eng, elapsed)
        except Exception as e:
            self.signals.response_ready.emit(f"Error: {e}", "ERROR", 0.0)


class VisionWorker(QThread):
    def __init__(self, screenshot, mode, vision_client, signals):
        super().__init__()
        self.screenshot    = screenshot
        self.mode          = mode
        self.vision_client = vision_client
        self.signals       = signals

    def run(self):
        import time
        try:
            start    = time.time()
            response = self.vision_client.analyze_screenshot(
                self.screenshot, self.mode
            )
            elapsed = round(time.time() - start, 2)  # type: ignore
            self.signals.vision_ready.emit(response, "GEMINI VISION", elapsed)
        except Exception as e:
            self.signals.vision_ready.emit(f"Vision error: {e}", "ERROR", 0.0)


class ResumeParseWorker(QThread):
    """Parse a resume file in a background thread."""
    parse_done = pyqtSignal(str, str)   # (status_msg, context_text)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            raw     = extract_text_from_file(self.filepath)
            parsed  = parse_resume(raw)
            context = build_resume_context(parsed)
            name    = parsed.get("name", "Candidate")
            skills  = parsed.get("skills", [])
            msg     = (
                f"✅ Resume loaded — {name} | "
                f"{len(skills)} skills detected"
            )
            self.parse_done.emit(msg, context)
        except Exception as e:
            self.parse_done.emit(f"❌ Resume parse error: {e}", "")


# ─────────────────────────────────────────────────────────────────────────────
# Main overlay widget
# ─────────────────────────────────────────────────────────────────────────────

class VivekAIOverlay(QWidget):
    trigger_auto_watch = pyqtSignal(str)

    def __init__(self, platform="windows"):
        super().__init__()
        self.platform       = platform
        self.signals        = WorkerSignals()
        self.ai_engine      = AIEngine()
        self.vision_client  = VisionAIClient()
        self.transcriber    = Transcriber()
        self.transcript_mgr = TranscriptManager()
        self.screen_vision  = ScreenVision(
            on_text_detected=self._on_screen_text_detected
        )
        self.audio_capture: Any = None
        self.is_listening   = False
        self.is_watching    = False
        self.watch_region: Optional[Tuple[int, int, int, int]] = None
        self.workers        = []

        # Resume context
        self.resume_context: str = ""
        self._resume_worker: Optional[ResumeParseWorker] = None

        # Drag / resize state
        self._drag_pos: Optional[QPoint]  = None
        self._resize_dir: Optional[str]   = None
        self._resize_start_geom: Optional[QRect]  = None
        self._resize_start_pos:  Optional[QPoint] = None
        self._is_minimized   = False
        self._normal_height  = 600

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._load_whisper_async()
        
        # Open to Resume tab by default
        if hasattr(self, 'tabs'):
            self.tabs.setCurrentIndex(3)

    # ── Window setup ─────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(get_window_flags_for_platform())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setWindowOpacity(config.WINDOW_OPACITY)
        self.setMinimumSize(600, 450)
        self.resize(700, 500)
        self.setMouseTracking(True)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 720, 100)
        # Apply screen-capture exclusion AFTER window is created
        QTimer.singleShot(600, lambda: apply_screen_capture_exclusion(self))

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(self._stylesheet())
        self.container.setMouseTracking(True)
        self.container.installEventFilter(self)

        main_vbox = QVBoxLayout(self.container)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)
        
        # 1. Top bar (Fixed Height)
        self.title_bar_widget = self._build_titlebar()
        main_vbox.addWidget(self.title_bar_widget)
        
        self.controls_widget = self._build_controls()
        main_vbox.addWidget(self.controls_widget)

        # 2. Split Body (Horizontal)
        body_frame = QFrame()
        body_hbox = QHBoxLayout(body_frame)
        body_hbox.setContentsMargins(10, 0, 10, 10)
        body_hbox.setSpacing(12)

        # -- Left Column: Inputs (Scrollable)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.tabs = self._build_tabs()
        self.tabs.tabBar().setExpanding(True)
        self.tabs.setDocumentMode(True)
        left_scroll.setWidget(self.tabs)
        body_hbox.addWidget(left_scroll, 4) # Stretch 4

        # -- Right Column: Persistent AI Response (Scrollable)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.right_panel = self._build_right_panel()
        right_scroll.setWidget(self.right_panel)
        body_hbox.addWidget(right_scroll, 5) # Stretch 5

        main_vbox.addWidget(body_frame, 1)

        # 3. Bottom bar (Fixed Height)
        main_vbox.addWidget(self._build_statusbar())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.container.setGeometry(0, 0, self.width(), self.height())
        self._update_dynamic_fonts()

    def _update_dynamic_fonts(self):
        # Scale base font from window size
        # 700 width is our "baseline" for 100% font size
        scale = max(0.9, min(1.6, self.width() / 750.0))
        base_size = int(13 * scale)
        small_size = int(11 * scale)
        large_size = int(16 * scale)
        
        # We can update the stylesheet dynamically or update specific labels
        # For simplicity and performance, we'll update the container's stylesheet
        # and re-apply it.
        self.container.setStyleSheet(self._stylesheet(base_size, small_size, large_size))

    def _build_titlebar(self):
        self.titleBar = QFrame()
        bar = self.titleBar
        bar.setFixedHeight(46)
        bar.setObjectName("titleBar")
        bar.installEventFilter(self)
        h = QHBoxLayout(bar)
        h.setContentsMargins(14, 0, 10, 0)
        h.setSpacing(8)

        dot   = QLabel("●")
        dot.setStyleSheet("color:#00E5FF;font-size:10px;")
        title = QLabel("VivekAI")
        title.setStyleSheet(
            "color:#FFF;font-size:15px;font-weight:700;"
            "font-family:'Segoe UI';letter-spacing:1px;"
        )
        plat_icon = "🪟" if self.platform == "windows" else "🍎"
        plat_col  = "#00E5FF" if self.platform == "windows" else "#A855F7"
        ver = QLabel(f"{plat_icon} v3.1")
        ver.setStyleSheet(
            f"color:{plat_col};font-size:9px;font-weight:600;"
            f"background:rgba(0,0,0,0.2);border:1px solid {plat_col}44;"
            "border-radius:4px;padding:1px 6px;"
        )
        h.addWidget(dot); h.addWidget(title); h.addWidget(ver)
        h.addStretch()
        h.addWidget(self._icon_btn("⚙", "#555", self._show_settings_menu))
        h.addWidget(self._icon_btn("—", "#888", self._toggle_minimize))
        h.addWidget(self._icon_btn("🗖", "#888", self._toggle_maximize))
        h.addWidget(self._icon_btn("✕", "#FF5252", self.close))

        bar.mousePressEvent = self._drag_start
        bar.mouseMoveEvent  = self._drag_move
        return bar

    def _show_settings_menu(self):
        from ui.platform_selector import reset_platform  # type: ignore
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:#0D1117;color:#E0E0E0;
                border:1px solid rgba(0,229,255,0.2);
                border-radius:8px;padding:4px;
                font-family:'Segoe UI';font-size:12px;
            }
            QMenu::item{padding:8px 16px;border-radius:4px;}
            QMenu::item:selected{background:rgba(0,229,255,0.12);}
            QMenu::separator{background:rgba(255,255,255,0.08);height:1px;margin:4px 8px;}
        """)
        plat_icon = "🍎" if self.platform == "windows" else "🪟"
        plat_name = "macOS" if self.platform == "windows" else "Windows"
        change_act     = QAction(f"{plat_icon}  Switch to {plat_name}", self)
        transcript_act = QAction("📁  Open Transcripts", self)
        about_act      = QAction("ℹ️  About VivekAI v3.1", self)
        change_act.triggered.connect(self._change_platform)
        transcript_act.triggered.connect(self._open_transcripts)
        about_act.triggered.connect(self._show_about)
        menu.addAction(change_act)
        menu.addSeparator()
        menu.addAction(transcript_act)
        menu.addAction(about_act)
        menu.exec_(self.mapToGlobal(self.rect().topRight()))

    def _change_platform(self):
        from ui.platform_selector import reset_platform, PlatformSelector  # type: ignore
        if self.is_listening: self._stop_listening()
        if self.is_watching:  self._stop_watching()
        reset_platform()
        selector = PlatformSelector()
        selector.platform_selected.connect(self._on_platform_changed)
        selector.show()
        self._selector = selector

    def _on_platform_changed(self, new_platform):
        self.platform = new_platform
        self._build_ui()
        self.status_label.setText(
            f"✅ Switched to "
            f"{'Windows 🪟' if new_platform == 'windows' else 'macOS 🍎'}"
        )

    def _show_about(self):
        plat = "Windows 🪟" if self.platform == "windows" else "macOS 🍎"
        self.status_label.setText(
            f"VivekAI v3.1 — {plat} — Mic + Screenshot + Auto Watch + Resume"
        )

    def _build_controls(self):
        frame = QFrame()
        frame.setObjectName("controls")
        frame.setFixedHeight(54)
        h = QHBoxLayout(frame)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(8)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("combo")
        self.mode_combo.setFixedWidth(148)
        for m in get_mode_list():
            self.mode_combo.addItem(f"{get_mode_icon(m)} {m}", m)

        self.engine_combo = QComboBox()
        self.engine_combo.setObjectName("combo")
        self.engine_combo.setFixedWidth(110)
        for label, val in [("⚡ Groq","groq"),
                            ("🌟 Gemini","gemini"),
                            ("🏠 Ollama","ollama")]:
            self.engine_combo.addItem(label, val)

        self.listen_btn = QPushButton("▶  Start Mic")
        self.listen_btn.setFixedWidth(100)
        self.listen_btn.setObjectName("listenBtn")
        self.listen_btn.setCursor(Qt.PointingHandCursor)
        self.listen_btn.clicked.connect(self._toggle_listen)

        h.addWidget(self.mode_combo)
        h.addWidget(self.engine_combo)
        h.addStretch()
        h.addWidget(self.listen_btn)
        return frame

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setObjectName("tabs")
        self.tabs.addTab(self._build_mic_tab(),        "🎙 Mic")
        self.tabs.addTab(self._build_screenshot_tab(), "📸 Screen")
        self.tabs.addTab(self._build_watch_tab(),      "👁 Watch")
        self.tabs.addTab(self._build_resume_tab(),     "📄 Resume")
        return self.tabs

    # ── Mic tab ───────────────────────────────────────────────────────────────

    def _build_mic_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 8); v.setSpacing(8)
        header_row = QHBoxLayout()
        header_row.addWidget(self._slabel("🎙  HEARD", "#00E5FF"))
        header_row.addStretch()
        clear_heard = QPushButton("🗑")
        clear_heard.setObjectName("clearBtn")
        clear_heard.setFixedSize(30, 20)
        clear_heard.clicked.connect(lambda: self.heard_text.clear())
        header_row.addWidget(clear_heard)
        v.addLayout(header_row)

        self.heard_text = QTextEdit()
        self.heard_text.setReadOnly(True)
        self.heard_text.setFixedHeight(120)
        self.heard_text.setObjectName("heardBox")
        self.heard_text.setPlaceholderText("Listening for audio...")
        self.heard_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.addWidget(self.heard_text)
        
        v.addStretch()
        return w

    # ── Screenshot tab ────────────────────────────────────────────────────────

    def _build_screenshot_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 8); v.setSpacing(8)
        info = QLabel("Captures your entire screen → AI reads it → Answers automatically")
        info.setStyleSheet("color:#6B7280;font-size:10px;font-style:italic;font-family:'Segoe UI';")
        info.setWordWrap(True)
        v.addWidget(info)
        self.screenshot_btn = QPushButton("📸  Capture Screen & Get Answer")
        self.screenshot_btn.setObjectName("screenshotBtn")
        self.screenshot_btn.setFixedHeight(46)
        self.screenshot_btn.setCursor(Qt.PointingHandCursor)
        self.screenshot_btn.clicked.connect(self._do_screenshot)
        delay_row = QHBoxLayout()
        delay_lbl = QLabel("Capture delay:")
        delay_lbl.setStyleSheet("color:#888;font-size:11px;font-family:'Segoe UI';")
        self.delay_combo = QComboBox()
        self.delay_combo.setObjectName("combo")
        self.delay_combo.setFixedWidth(100)
        for d in ["Instant", "2 seconds", "3 seconds", "5 seconds"]:
            self.delay_combo.addItem(d)
        delay_row.addWidget(delay_lbl); delay_row.addWidget(self.delay_combo)
        delay_row.addStretch()
        v.addWidget(self.screenshot_btn); v.addLayout(delay_row)
        # Screen text header + Clear button
        header_row = QHBoxLayout()
        header_row.addWidget(self._slabel("👁  SCREEN TEXT", "#FFD700"))
        header_row.addStretch()
        clear_ocr = QPushButton("🗑")
        clear_ocr.setObjectName("clearBtn")
        clear_ocr.setFixedSize(30, 20)
        clear_ocr.clicked.connect(lambda: self.ocr_text.clear())
        header_row.addWidget(clear_ocr)
        v.addLayout(header_row)

        self.ocr_text = QTextEdit()
        self.ocr_text.setReadOnly(True)
        self.ocr_text.setFixedHeight(120)
        self.ocr_text.setObjectName("heardBox")
        self.ocr_text.setPlaceholderText("Extracted text...")
        self.ocr_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.addWidget(self.ocr_text)

        v.addStretch()
        return w

    # ── Auto-watch tab ────────────────────────────────────────────────────────

    def _build_watch_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 8); v.setSpacing(8)
        info = QLabel(
            "Watches a screen region continuously. "
            "When new question appears → AI answers automatically!"
        )
        info.setStyleSheet("color:#6B7280;font-size:10px;font-style:italic;font-family:'Segoe UI';")
        info.setWordWrap(True); v.addWidget(info)

        self.region_label = QLabel(
            "📍  No region selected — click Select Region or Full Screen"
        )
        self.region_label.setStyleSheet(
            "color:#FFD700;font-size:10px;font-weight:600;"
            "background:rgba(255,215,0,0.08);border:1px solid rgba(255,215,0,0.2);"
            "border-radius:6px;padding:6px 10px;font-family:'Segoe UI';"
        )
        self.region_label.setWordWrap(True); v.addWidget(self.region_label)

        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        self.select_region_btn = QPushButton("🖱  Region")
        self.select_region_btn.setObjectName("regionBtn")
        self.select_region_btn.setCursor(Qt.PointingHandCursor)
        self.select_region_btn.clicked.connect(self._select_region)
        self.fullscreen_btn = QPushButton("🖥  Full")
        self.fullscreen_btn.setObjectName("regionBtn")
        self.fullscreen_btn.setCursor(Qt.PointingHandCursor)
        self.fullscreen_btn.clicked.connect(self._use_fullscreen)
        self.watch_btn = QPushButton("👁  Watch")
        self.watch_btn.setObjectName("watchBtn")
        self.watch_btn.setCursor(Qt.PointingHandCursor)
        self.watch_btn.clicked.connect(self._toggle_watch)
        btn_row.addWidget(self.select_region_btn, 1)
        btn_row.addWidget(self.fullscreen_btn, 1)
        btn_row.addWidget(self.watch_btn, 1)
        v.addLayout(btn_row)

        int_row = QHBoxLayout()
        int_lbl = QLabel("Check every:")
        int_lbl.setStyleSheet("color:#888;font-size:11px;font-family:'Segoe UI';")
        self.interval_combo = QComboBox()
        self.interval_combo.setObjectName("combo")
        self.interval_combo.setFixedWidth(110)
        for intv in ["1 second", "2 seconds", "3 seconds", "5 seconds"]:
            self.interval_combo.addItem(intv)
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.currentIndexChanged.connect(self._update_interval)
        int_row.addWidget(int_lbl); int_row.addWidget(self.interval_combo)
        int_row.addStretch()
        v.addLayout(int_row)

        # Detected content (reduced height in input side)
        # Detected content header + Clear button
        det_row = QHBoxLayout()
        det_row.addWidget(self._slabel("👁  DETECTED ON SCREEN", "#FFD700"))
        det_row.addStretch()
        clear_det = QPushButton("🗑")
        clear_det.setObjectName("clearBtn")
        clear_det.setFixedSize(30, 20)
        clear_det.clicked.connect(lambda: self.watch_detected.clear())
        det_row.addWidget(clear_det)
        v.addLayout(det_row)

        self.watch_detected = QTextEdit()
        self.watch_detected.setReadOnly(True)
        self.watch_detected.setFixedHeight(120)
        self.watch_detected.setObjectName("heardBox")
        self.watch_detected.setPlaceholderText("Screen text appears here...")
        self.watch_detected.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.addWidget(self.watch_detected)

        v.addStretch()
        return w

    # ── Resume tab ────────────────────────────────────────────────────────────

    def _build_resume_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 8); v.setSpacing(8)

        title_lbl = QLabel("📄  RESUME CONTEXT")
        title_lbl.setStyleSheet(
            "color:#A78BFA;font-size:9px;font-weight:700;"
            "letter-spacing:1.5px;font-family:'Segoe UI';"
        )
        v.addWidget(title_lbl)

        info = QLabel(
            "Upload your resume (PDF, DOCX, or TXT). "
            "VivekAI will automatically tailor all AI answers "
            "to your background, skills, and experience."
        )
        info.setStyleSheet(
            "color:#6B7280;font-size:10px;font-style:italic;"
            "font-family:'Segoe UI';"
        )
        info.setWordWrap(True)
        v.addWidget(info)

        # Upload button row
        upload_row = QHBoxLayout(); upload_row.setSpacing(8)
        self.upload_btn = QPushButton("📂  Upload Resume")
        self.upload_btn.setObjectName("uploadBtn")
        self.upload_btn.setFixedHeight(40)
        self.upload_btn.setCursor(Qt.PointingHandCursor)
        self.upload_btn.clicked.connect(self._upload_resume)
        self.clear_resume_btn = QPushButton("🗑  Clear")
        self.clear_resume_btn.setObjectName("clearBtn")
        self.clear_resume_btn.setCursor(Qt.PointingHandCursor)
        self.clear_resume_btn.clicked.connect(self._clear_resume)
        upload_row.addWidget(self.upload_btn, 3)
        upload_row.addWidget(self.clear_resume_btn, 1)
        v.addLayout(upload_row)

        # File label
        self.resume_file_label = QLabel("No resume loaded")
        self.resume_file_label.setStyleSheet(
            "color:#4B5563;font-size:10px;font-family:'Segoe UI';"
            "background:rgba(167,139,250,0.06);"
            "border:1px solid rgba(167,139,250,0.15);"
            "border-radius:6px;padding:6px 10px;"
        )
        self.resume_file_label.setWordWrap(True)
        v.addWidget(self.resume_file_label)

        # Detected skills
        v.addWidget(self._slabel("🧠  DETECTED CONTEXT (AUTO-PREVIEW)", "#A78BFA"))
        self.resume_preview = QTextEdit()
        self.resume_preview.setReadOnly(True)
        self.resume_preview.setObjectName("resumeBox")
        self.resume_preview.setPlaceholderText(
            "Upload a resume above — detected skills, experience and "
            "education will appear here and automatically enhance all AI answers."
        )
        v.addWidget(self.resume_preview, 1)

        # Quick-ask row
        v.addWidget(self._slabel("💬  QUICK ASK (TEST YOUR CONTEXT)", "#69FF47"))
        # Quick-ask inputs
        quick_row = QHBoxLayout(); quick_row.setSpacing(6)
        self.quick_question = QTextEdit()
        self.quick_question.setObjectName("heardBox")
        self.quick_question.setFixedHeight(60)
        self.quick_question.setPlaceholderText("Ask about your resume...")
        self.quick_question.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.quick_ask_btn = QPushButton("Ask")
        self.quick_ask_btn.setObjectName("copyBtn")
        self.quick_ask_btn.setFixedSize(50, 28)
        self.quick_ask_btn.clicked.connect(self._quick_ask)

        self.clear_quick_btn = QPushButton("🗑")
        self.clear_quick_btn.setObjectName("clearBtn")
        self.clear_quick_btn.setFixedSize(50, 28)
        self.clear_quick_btn.clicked.connect(self.quick_question.clear)

        btns = QVBoxLayout(); btns.setSpacing(4)
        btns.addWidget(self.quick_ask_btn)
        btns.addWidget(self.clear_quick_btn)

        quick_row.addWidget(self.quick_question, 1)
        quick_row.addLayout(btns)
        v.addLayout(quick_row)
        
        v.addStretch()
        return w

    def _build_right_panel(self):
        w = QFrame()
        w.setObjectName("rightPanel")
        v = QVBoxLayout(w); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)

        v.addWidget(self._slabel("🤖  AI RESPONSE", "#00E5FF"))
        
        # Shared Response Box
        self.global_response = QTextEdit()
        self.global_response.setReadOnly(True)
        self.global_response.setObjectName("responseBox")
        self.global_response.setPlaceholderText("Everything the AI says will appear here permanently...")
        self.global_response.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        v.addWidget(self.global_response, 1)

        # Action Buttons
        row = QHBoxLayout(); row.setSpacing(8)
        
        copy_btn = QPushButton("📋  Copy")
        copy_btn.setObjectName("copyBtn")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self._copy(self.global_response))
        
        clear_btn = QPushButton("🗑  Clear All")
        clear_btn.setObjectName("clearBtn")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_everything)
        
        export_btn = QPushButton("📁  History")
        export_btn.setObjectName("clearBtn")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._open_transcripts)
        
        row.addWidget(copy_btn); row.addWidget(clear_btn); row.addWidget(export_btn)
        v.addLayout(row)

        return w

    def _clear_everything(self):
        self.global_response.clear()
        if hasattr(self, 'heard_text'): self.heard_text.clear()
        if hasattr(self, 'ocr_text'): self.ocr_text.clear()
        if hasattr(self, 'watch_detected'): self.watch_detected.clear()
        if hasattr(self, 'quick_question'): self.quick_question.clear()
        self.transcript_mgr.clear_session()
        self.status_label.setText("✨ Ready")
        self.count_label.setText("0 answers")

    # ── Status bar ────────────────────────────────────────────────────────────

    # ── Stylesheet ──────────────────────────────────────────────────────────

    def _stylesheet(self, base=12, small=10, large=15):
        # We now accept sizes for dynamic scaling
        accent = "#00E5FF" if self.platform == "windows" else "#A855F7"
        return f"""
            #container {{
                background: #111827; 
                border: 1px solid #374151;
                border-radius: 12px;
            }}
            #titleBar {{
                background: #1F2937;
                border-bottom: 1px solid #374151;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
            #controls {{
                background: #111827;
                border-bottom: 1px solid #1F2937;
            }}
            #statusBar {{
                background: #1F2937;
                border-top: 1px solid #374151;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
            QTabWidget::pane {{ border: none; background: transparent; }}
            QTabBar::tab {{
                background: #1F2937; color: #9CA3AF; padding: 12px 5px;
                font-family: 'Segoe UI'; font-size: {small}px; font-weight: 700;
                border-right: 1px solid #374151;
                min-width: 60px;
            }}
            QTabBar::tab:selected {{ background: #111827; color: {accent}; border-bottom: 3px solid {accent}; }}
            QTabBar::tab:hover {{ background: #374151; color: #FFFFFF; }}
            
            QTextEdit {{
                background: #000000; color: #F9FAFB;
                border: 1px solid #4B5563;
                border-radius: 8px; padding: 12px;
                font-family: 'Consolas', 'Monaco', monospace; font-size: {base}px;
                line-height: 1.6;
            }}
            #heardBox, #resumeBox {{
                background: #0F172A;
                color: #FFFFFF;
                border: 1px solid #1E293B;
            }}
            #responseBox {{
                background: #000000;
                color: #FFFFFF;
                border: 2px solid {accent};
                font-size: {large}px;
            }}
            
            QLabel {{ color: #E5E7EB; font-family: 'Segoe UI'; font-weight: 600; }}
            
            QPushButton {{
                background: #1F2937; color: #FFFFFF;
                border: 1px solid #374151;
                border-radius: 6px; font-family: 'Segoe UI'; font-size: {small}px; font-weight: 700;
            }}
            QPushButton:hover {{ 
                background: #374151; color: {accent}; 
                border: 1px solid {accent};
            }}
            #listenBtn[active="true"] {{ background: #DC2626; color: white; border: 1px solid #EF4444; }}
            
            #copyBtn {{ background: #064E3B; color: #34D399; border: 1px solid #059669; }}
            #copyBtn:hover {{ background: #059669; color: white; }}
            
            #clearBtn {{ background: #7F1D1D; color: #F87171; border: 1px solid #B91C1C; }}
            #clearBtn:hover {{ background: #B91C1C; color: white; }}
            
            QComboBox {{
                background: #1F2937; color: #F3F4F6;
                border: 1px solid #374151;
                border-radius: 6px; padding: 4px 10px; font-size: {small}px;
            }}
            QComboBox:hover {{ border: 1px solid {accent}; }}
            
            QScrollBar:vertical {{
                background: #111827; width: 10px; margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #374151; border-radius: 5px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {accent};
            }}
        """

    def _build_statusbar(self):
        bar = QFrame(); bar.setFixedHeight(28); bar.setObjectName("statusBar")
        h = QHBoxLayout(bar); h.setContentsMargins(12, 0, 12, 0)
        self.status_label = QLabel("⏳ Loading Whisper...")
        self.status_label.setStyleSheet("color:#888;font-size:10px;")
        self.count_label = QLabel("0 answers")
        self.count_label.setStyleSheet("color:#555;font-size:10px;")
        h.addWidget(self.status_label); h.addStretch(); h.addWidget(self.count_label)
        return bar

    # ── Small helpers ─────────────────────────────────────────────────────────

    def _slabel(self, text, color):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{color};font-size:10px;font-weight:800;"
            "letter-spacing:1.8px;font-family:'Segoe UI';"
            "background: transparent;"
        )
        return lbl

    def _action_btns(self, textbox, second_textbox=None):
        row = QHBoxLayout(); row.setSpacing(6)
        c = QPushButton("📋  Copy Answer")
        c.setObjectName("copyBtn")
        c.setCursor(Qt.PointingHandCursor)
        c.clicked.connect(lambda: self._copy(textbox))
        d = QPushButton("🗑  Clear")
        d.setObjectName("clearBtn")
        d.setCursor(Qt.PointingHandCursor)
        d.clicked.connect(lambda: self._clear_boxes(textbox, second_textbox))
        f = QPushButton("📁  Transcripts")
        f.setObjectName("clearBtn")
        f.setCursor(Qt.PointingHandCursor)
        f.clicked.connect(self._open_transcripts)
        row.addWidget(c); row.addWidget(d); row.addWidget(f)
        return row

    def _clear_boxes(self, box1, box2=None):
        box1.clear()
        if box2: box2.clear()
        # Also reset manager and counter if it's the main mic tab
        self.transcript_mgr.clear_session()
        self.count_label.setText("0 answers")

    def _icon_btn(self, text, color, callback):
        btn = QPushButton(text)
        btn.setFixedSize(26, 26)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{color};"
            "border:none;font-size:13px;border-radius:5px;}}"
            "QPushButton:hover{background:rgba(255,255,255,0.08);}"
        )
        btn.clicked.connect(callback)
        return btn

    # ── Signal connections ────────────────────────────────────────────────────

    def _connect_signals(self):
        self.signals.transcript_ready.connect(self._on_transcript)
        self.signals.response_ready.connect(self._on_mic_response)
        self.signals.status_update.connect(self.status_label.setText)
        self.signals.model_loaded.connect(
            lambda: self.status_label.setText(
                "✅ Ready — Mic, Screenshot, Auto-Watch & Resume available"
            )
        )
        self.signals.screen_text_ready.connect(self._on_screen_text)
        self.signals.vision_ready.connect(self._on_vision_response)
        self.engine_combo.currentIndexChanged.connect(
            lambda: self.ai_engine.set_engine(self.engine_combo.currentData())
        )
        self.trigger_auto_watch.connect(self._do_auto_watch_ai)

    def _load_whisper_async(self):
        def load():
            self.transcriber.load_model(
                lambda m: self.signals.status_update.emit(m)
            )
            self.signals.model_loaded.emit()
        threading.Thread(target=load, daemon=True).start()

    # ── System prompt with optional resume context ────────────────────────────

    def _get_system_prompt(self, mode: str) -> str:
        base = get_system_prompt(mode)
        if self.resume_context and RESUME_AVAILABLE:
            return get_resume_enhanced_prompt(base, self.resume_context)
        return base

    # ── Mic ───────────────────────────────────────────────────────────────────

    def _toggle_listen(self):
        if not self.transcriber.is_loaded:
            self.status_label.setText("⏳ Whisper still loading...")
            return
        if self.is_listening:
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self):
        self.is_listening = True
        self.listen_btn.setText("■  Stop Mic")
        self.listen_btn.setProperty("active", "true")
        self.listen_btn.setStyle(self.listen_btn.style())
        mode   = self.mode_combo.currentData()
        engine = self.engine_combo.currentData()
        self.ai_engine.set_engine(engine)
        self.transcript_mgr.start_session(mode, engine.upper())
        self.audio_capture = AudioCapture(self._on_audio_chunk)
        self.audio_capture.start()
        self.status_label.setText(f"🔴 Listening | {mode} | {engine.upper()}")

    def _stop_listening(self):
        self.is_listening = False
        self.listen_btn.setText("▶  Start Mic")
        self.listen_btn.setProperty("active", "false")
        self.listen_btn.setStyle(self.listen_btn.style())
        if self.audio_capture:
            self.audio_capture.stop()
            self.audio_capture = None
        self.transcript_mgr.stop_session()
        self.status_label.setText(
            f"⏹ Stopped | {self.transcript_mgr.get_entry_count()} saved"
        )

    def _on_audio_chunk(self, audio_chunk, sample_rate):
        def process():
            text = self.transcriber.transcribe(audio_chunk, sample_rate)
            if text:
                self.signals.transcript_ready.emit(text)
                worker = AIWorker(
                    text,
                    self._get_system_prompt(self.mode_combo.currentData()),
                    self.ai_engine,
                    self.signals
                )
                self.workers.append(worker)
                worker.finished.connect(
                    lambda: self.workers.remove(worker) if worker in self.workers else None
                )
                worker.start()
        threading.Thread(target=process, daemon=True).start()

    def _on_transcript(self, text):
        self.heard_text.setPlainText(text)
        # Propagate to Resume tab Quick Ask
        if hasattr(self, 'quick_question'):
            self.quick_question.setPlainText(text)
        self.status_label.setText("⚡ Generating response...")

    def _on_mic_response(self, response, engine, elapsed):
        self.global_response.setPlainText(response)
        self.transcript_mgr.add_entry(
            self.heard_text.toPlainText(), response
        )
        self.count_label.setText(
            f"{self.transcript_mgr.get_entry_count()} answers"
        )
        icon = "❌" if engine == "ERROR" else "✅"
        self.status_label.setText(
            f"{icon} {engine} | {elapsed}s | "
            f"{'🔴 Listening' if self.is_listening else 'Ready'}"
        )

    # ── Screenshot ────────────────────────────────────────────────────────────

    def _do_screenshot(self):
        delays = {"Instant": 0, "2 seconds": 2,
                  "3 seconds": 3, "5 seconds": 5}
        delay = delays.get(self.delay_combo.currentText(), 0)
        self.screenshot_btn.setText("⏳  Capturing...")
        self.screenshot_btn.setEnabled(False)
        self.status_label.setText(
            f"📸 Capturing in {self.delay_combo.currentText()}..."
        )

        def _prepare_capture():
            self.hide()
            QTimer.singleShot(180, _execute_capture)

        def _execute_capture():
            QApplication.processEvents()
            screenshot, ocr_text = self.screen_vision.capture_and_read()
            self.show()
            if screenshot:
                if ocr_text:
                    self.signals.screen_text_ready.emit(ocr_text)
                self.status_label.setText("🤖 Vision AI analyzing screen...")
                worker = VisionWorker(
                    screenshot,
                    self.mode_combo.currentData(),
                    self.vision_client,
                    self.signals
                )
                self.workers.append(worker)
                worker.finished.connect(
                    lambda: self.workers.remove(worker) if worker in self.workers else None
                )
                worker.start()
            else:
                self.status_label.setText(
                    "❌ Screenshot failed — check Tesseract install"
                )
            self.screenshot_btn.setText("📸  Capture Screen & Get Answer")
            self.screenshot_btn.setEnabled(True)

        QTimer.singleShot(max(10, delay * 1000), _prepare_capture)

    def _on_screen_text(self, text):
        short = text[:500] + "..." if len(text) > 500 else text
        self.ocr_text.setPlainText(short)
        self.watch_detected.setPlainText(short)

    def _on_vision_response(self, response, engine, elapsed):
        self.global_response.setPlainText(response)
        self.transcript_mgr.add_entry("[Screen]", response)
        self.count_label.setText(
            f"{self.transcript_mgr.get_entry_count()} answers"
        )
        icon = "❌" if engine == "ERROR" else "✅"
        self.status_label.setText(f"{icon} {engine} | {elapsed}s")

    # ── Auto-watch ────────────────────────────────────────────────────────────

    def _select_region(self):
        self.hide()
        QTimer.singleShot(300, self._open_selector)

    def _open_selector(self):
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self._on_region_selected)
        self.selector.cancelled.connect(lambda: self.show())
        self.selector.show()

    def _on_region_selected(self, x1, y1, x2, y2):
        self.watch_region = (x1, y1, x2, y2)
        self.screen_vision.set_region(x1, y1, x2, y2)
        self.region_label.setText(
            f"📍  Region: ({x1},{y1}) → ({x2},{y2})  "
            f"[{x2-x1}×{y2-y1}px]"
        )
        self.show()
        self.status_label.setText("✅ Region selected — click 'Start Watching'")

    def _use_fullscreen(self):
        self.watch_region = None
        self.screen_vision.watch_region = None
        self.region_label.setText(
            "📍  Full screen selected — click 'Start Watching'"
        )

    def _toggle_watch(self):
        if self.is_watching:
            self._stop_watching()
        else:
            self._start_watching()

    def _start_watching(self):
        self.is_watching = True
        self.watch_btn.setText("⏹  Stop Watching")
        self.watch_btn.setProperty("active", "true")
        self.watch_btn.setStyle(self.watch_btn.style())
        self.screen_vision.start_watching(self.watch_region)
        self.status_label.setText(
            f"👁 Watching "
            f"{'full screen' if not self.watch_region else 'region'} "
            "for new content..."
        )

    def _stop_watching(self):
        self.is_watching = False
        self.watch_btn.setText("👁  Start Watching")
        self.watch_btn.setProperty("active", "false")
        self.watch_btn.setStyle(self.watch_btn.style())
        self.screen_vision.stop_watching()
        self.status_label.setText("⏹ Auto-watch stopped")

    def _on_screen_text_detected(self, text):
        self.trigger_auto_watch.emit(text)

    def _do_auto_watch_ai(self, text):
        self.signals.screen_text_ready.emit(text)
        watch_signals = WorkerSignals()
        watch_signals.response_ready.connect(
            lambda r, e, t: self.signals.vision_ready.emit(r, e, t)
        )
        worker = AIWorker(
            f"Answer this from screen:\n{text[:800]}",
            self._get_system_prompt(self.mode_combo.currentData()),
            self.ai_engine,
            watch_signals
        )
        self.workers.append(worker)
        worker.finished.connect(
            lambda: self.workers.remove(worker) if worker in self.workers else None
        )
        worker.start()

    def _update_interval(self):
        intervals = {
            "1 second": 1.0, "2 seconds": 2.0,
            "3 seconds": 3.0, "5 seconds": 5.0,
        }
        self.screen_vision.watch_interval = intervals.get(
            self.interval_combo.currentText(), 2.0
        )

    # ── Resume feature ────────────────────────────────────────────────────────

    def _upload_resume(self):
        if not RESUME_AVAILABLE:
            self.status_label.setText(
                "❌ Resume parsing needs: pip install pdfminer.six python-docx"
            )
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume File",
            os.path.expanduser("~"),
            "Documents (*.pdf *.docx *.doc *.txt);;All Files (*)"
        )
        if not filepath:
            return

        filename = os.path.basename(filepath)
        self.resume_file_label.setText(f"📄 {filename}  — parsing…")
        self.status_label.setText("⏳ Parsing resume…")
        self.upload_btn.setEnabled(False)

        worker = ResumeParseWorker(filepath)
        self._resume_worker = worker
        worker.parse_done.connect(self._on_resume_parsed)
        worker.start()

    def _on_resume_parsed(self, status_msg: str, context_text: str):
        self.upload_btn.setEnabled(True)
        self.status_label.setText(status_msg)
        if context_text:
            self.resume_context = context_text
            self.resume_preview.setPlainText(context_text)
            # Update file label with success style
            self.resume_file_label.setStyleSheet(
                "color:#A78BFA;font-size:10px;font-family:'Segoe UI';"
                "background:rgba(167,139,250,0.08);"
                "border:1px solid rgba(167,139,250,0.3);"
                "border-radius:6px;padding:6px 10px;"
            )
            self.resume_file_label.setText(status_msg)
        else:
            self.resume_context = ""
            self.resume_preview.setPlainText(status_msg)

    def _clear_resume(self):
        self.resume_context = ""
        self.resume_preview.clear()
        self.resume_file_label.setText("No resume loaded")
        self.resume_file_label.setStyleSheet(
            "color:#4B5563;font-size:10px;font-family:'Segoe UI';"
            "background:rgba(167,139,250,0.06);"
            "border:1px solid rgba(167,139,250,0.15);"
            "border-radius:6px;padding:6px 10px;"
        )
        self.status_label.setText("🗑 Resume context cleared")

    def _quick_ask(self):
        q = self.quick_question.toPlainText().strip()
        if not q:
            return
        self.status_label.setText("⚡ Generating quick answer…")
        prompt = self._get_system_prompt(self.mode_combo.currentData())

        quick_signals = WorkerSignals()
        quick_signals.response_ready.connect(
            lambda r, e, t: (
                self.global_response.setPlainText(r),
                self.status_label.setText(f"{'❌' if e == 'ERROR' else '✅'} {e} | {t}s"),
            )
        )
        worker = AIWorker(q, prompt, self.ai_engine, quick_signals)
        self.workers.append(worker)
        worker.finished.connect(
            lambda: self.workers.remove(worker) if worker in self.workers else None
        )
        worker.start()

    # ── Utility ───────────────────────────────────────────────────────────────

    def _copy(self, textbox):
        text = textbox.toPlainText()
        if text:
            pyperclip.copy(text)
            self.status_label.setText("📋 Copied!")
            QTimer.singleShot(2000, lambda: self.status_label.setText("✅ Ready"))

    def _open_transcripts(self):
        open_folder(self.transcript_mgr.get_transcript_dir())

    def _toggle_minimize(self):
        if not self._is_minimized:
            self._normal_height = self.height()
            self._is_minimized  = True
            self.setMinimumHeight(46)
            self.setMaximumHeight(46)
            self.resize(self.width(), 46)
        else:
            self._is_minimized = False
            self.setMinimumSize(320, 420)
            self.setMaximumSize(16777215, 16777215)
            self.resize(self.width(), self._normal_height)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


    # ── Drag (title bar) ──────────────────────────────────────────────────────

    def _drag_start(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def _drag_move(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos and not self._resize_dir:
            self.move(e.globalPos() - self._drag_pos)

    # ── Resize logic (INVISIBLE to screen share) ──────────────────────────────

    def _get_resize_dir(self, pos):
        """
        Return (direction_str, Qt_cursor) for a window-local mouse position,
        or None if not near an edge.
        The cursors are only painted on the local display — SetWindowDisplayAffinity
        means the entire window (including cursor overlays) is excluded from capture.
        """
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        m = RESIZE_MARGIN
        left   = x < m
        right  = x > w - m
        top    = y < m
        bottom = y > h - m
        if top    and left:  return ("tl", Qt.SizeFDiagCursor)
        if top    and right: return ("tr", Qt.SizeBDiagCursor)
        if bottom and left:  return ("bl", Qt.SizeBDiagCursor)
        if bottom and right: return ("br", Qt.SizeFDiagCursor)
        if left:             return ("l",  Qt.SizeHorCursor)
        if right:            return ("r",  Qt.SizeHorCursor)
        if top:              return ("t",  Qt.SizeVerCursor)
        if bottom:           return ("b",  Qt.SizeVerCursor)
        return None

    def _apply_resize(self, global_pos):
        d = self._resize_dir
        g = self._resize_start_geom
        p = self._resize_start_pos
        if not d or not g or not p:
            return
            
        assert p is not None
        assert g is not None
        
        dx = global_pos.x() - p.x()
        dy = global_pos.y() - p.y()
        x, y, w, h = g.x(), g.y(), g.width(), g.height()
        min_w, min_h = self.minimumWidth(), self.minimumHeight()

        new_x, new_y, new_w, new_h = x, y, w, h
        if d in ("r", "tr", "br"): new_w = max(min_w, w + dx)
        if d in ("b", "bl", "br"): new_h = max(min_h, h + dy)
        if d in ("l", "tl", "bl"):
            cand_x, cand_w = x + dx, w - dx
            if cand_w >= min_w:
                new_x, new_w = cand_x, cand_w
        if d in ("t", "tl", "tr"):
            cand_y, cand_h = y + dy, h - dy
            if cand_h >= min_h:
                new_y, new_h = cand_y, cand_h
        self.setGeometry(new_x, new_y, new_w, new_h)

    # ── Event filter (container mouse events → resize / cursor) ───────────────

    def eventFilter(self, obj, event):
        if obj not in (self.container, getattr(self, "titleBar", None)):
            return super().eventFilter(obj, event)

        etype = event.type()

        if etype == QEvent.MouseMove:
            win_pos = obj.mapTo(self, event.pos())
            if event.buttons() == Qt.LeftButton and self._resize_dir:
                self._apply_resize(event.globalPos())
                return True
            elif not (event.buttons() & Qt.LeftButton):
                result = self._get_resize_dir(win_pos)
                if result:
                    obj.setCursor(QCursor(result[1]))
                else:
                    obj.unsetCursor()

        elif etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            win_pos = obj.mapTo(self, event.pos())
            result  = self._get_resize_dir(win_pos)
            if result:
                self._resize_dir        = result[0]
                self._resize_start_geom = self.geometry()
                self._resize_start_pos  = event.globalPos()
                return True

        elif etype == QEvent.MouseButtonRelease:
            self._drag_pos = None
            if self._resize_dir:
                self._resize_dir        = None
                self._resize_start_geom = None
                self._resize_start_pos  = None
                return True

        return super().eventFilter(obj, event)

    def mouseReleaseEvent(self, e):
        self._resize_dir        = None
        self._resize_start_geom = None
        self._resize_start_pos  = None
        self._drag_pos          = None

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(0, 0, 0, 0)))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 14, 14)

    def closeEvent(self, e):
        if self.is_listening: self._stop_listening()
        if self.is_watching:  self._stop_watching()
        e.accept()
