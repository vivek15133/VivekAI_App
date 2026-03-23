"""
VivekAI_App - Overlay UI v3.0
Supports: Windows 10/11 + macOS 12+
"""

import sys
import threading
import pyperclip  # type: ignore
from datetime import datetime
from PyQt5.QtWidgets import (  # type: ignore
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QApplication,
    QFrame, QTabWidget, QMenu, QAction, QSizeGrip
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QPoint, QRect, QSize, QEvent  # type: ignore
from PyQt5.QtGui import QColor, QFont, QPainter, QBrush, QPen, QCursor  # type: ignore
from typing import Optional, Tuple, Any

# Pixel zone near each edge that acts as a resize handle
RESIZE_MARGIN = 8

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
        self.text = text
        self.system_prompt = system_prompt
        self.engine = engine
        self.signals = signals

    def run(self):
        import time
        try:
            response, eng, elapsed = self.engine.generate(self.text, self.system_prompt)
            self.signals.response_ready.emit(response, eng, elapsed)
        except Exception as e:
            self.signals.response_ready.emit(f"Error: {e}", "ERROR", 0)


class VisionWorker(QThread):
    def __init__(self, screenshot, mode, vision_client, signals):
        super().__init__()
        self.screenshot = screenshot
        self.mode = mode
        self.vision_client = vision_client
        self.signals = signals

    def run(self):
        import time
        try:
            start = time.time()
            response = self.vision_client.analyze_screenshot(self.screenshot, self.mode)
            elapsed = round(time.time() - start, 2)  # type: ignore
            self.signals.vision_ready.emit(response, "GEMINI VISION", elapsed)
        except Exception as e:
            self.signals.vision_ready.emit(f"Vision error: {e}", "ERROR", 0)


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
        self.screen_vision  = ScreenVision(on_text_detected=self._on_screen_text_detected)
        self.audio_capture: Any = None
        self.is_listening   = False
        self.is_watching    = False
        self.watch_region: Optional[Tuple[int, int, int, int]] = None
        self.workers        = []
        # --- drag/resize state ---
        self._drag_pos: Optional[QPoint] = None          # for title-bar drag
        self._resize_dir: Optional[str] = None          # active resize direction
        self._resize_start_geom: Optional[QRect] = None      # window geom at resize start
        self._resize_start_pos: Optional[QPoint]  = None      # global mouse pos at resize start
        self._is_minimized  = False
        self._normal_height = 560
        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._load_whisper_async()

    def _setup_window(self):
        self.setWindowFlags(get_window_flags_for_platform())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setWindowOpacity(config.WINDOW_OPACITY)
        # Allow free resize — set only a minimum so UI stays usable
        self.setMinimumSize(300, 380)
        self.resize(380, 560)
        # Mouse tracking required so cursor updates fire even without button held
        self.setMouseTracking(True)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 400, 40)
        # Platform-aware screen capture exclusion
        QTimer.singleShot(500, lambda: apply_screen_capture_exclusion(self))

    def _build_ui(self):
        self.container = QFrame(self)
        # Container will always be resized to fill window via resizeEvent
        self.container.setGeometry(0, 0, self.width(), self.height())
        self.container.setObjectName("container")
        self.container.setStyleSheet(self._stylesheet())
        # Mouse tracking + event filter so container-level mouse events
        # are forwarded to our resize/cursor logic (container sits on top
        # of the window and would otherwise swallow every mouse event)
        self.container.setMouseTracking(True)
        self.container.installEventFilter(self)
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_titlebar())
        layout.addWidget(self._build_controls())
        layout.addWidget(self._build_tabs(), 1)  # stretch=1 → fills all spare height
        layout.addWidget(self._build_statusbar())

    def _build_titlebar(self):
        bar = QFrame(); bar.setFixedHeight(46); bar.setObjectName("titleBar")
        h = QHBoxLayout(bar); h.setContentsMargins(14,0,10,0); h.setSpacing(8)
        dot = QLabel("●"); dot.setStyleSheet("color:#00E5FF;font-size:10px;")
        title = QLabel("VivekAI"); title.setStyleSheet(
            "color:#FFF;font-size:15px;font-weight:700;font-family:'Segoe UI';letter-spacing:1px;")
        # Platform badge
        plat_icon = "🪟" if self.platform == "windows" else "🍎"
        plat_col = "#00E5FF" if self.platform == "windows" else "#A855F7"
        ver = QLabel(f"{plat_icon} v3.0")
        ver.setStyleSheet(
            f"color:{plat_col};font-size:9px;font-weight:600;"
            f"background:rgba(0,0,0,0.2);border:1px solid {plat_col}44;"
            "border-radius:4px;padding:1px 6px;")
        h.addWidget(dot); h.addWidget(title); h.addWidget(ver); h.addStretch()
        # Settings button (for change platform)
        settings_btn = self._icon_btn("⚙", "#555", self._show_settings_menu)
        h.addWidget(settings_btn)
        h.addWidget(self._icon_btn("—","#888",self._toggle_minimize))
        h.addWidget(self._icon_btn("✕","#FF5252",self.hide))
        bar.mousePressEvent = self._drag_start
        bar.mouseMoveEvent  = self._drag_move
        return bar

    def _show_settings_menu(self):
        """Show settings dropdown with Change Platform option"""
        from ui.platform_selector import reset_platform  # type: ignore
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #0D1117; color: #E0E0E0;
                border: 1px solid rgba(0,229,255,0.2);
                border-radius: 8px; padding: 4px;
                font-family: 'Segoe UI'; font-size: 12px;
            }
            QMenu::item { padding: 8px 16px; border-radius: 4px; }
            QMenu::item:selected { background: rgba(0,229,255,0.12); }
            QMenu::separator { background: rgba(255,255,255,0.08); height: 1px; margin: 4px 8px; }
        """)
        plat_icon = "🍎" if self.platform == "windows" else "🪟"
        plat_name = "macOS" if self.platform == "windows" else "Windows"
        change_act = QAction(f"{plat_icon}  Switch to {plat_name}", self)
        change_act.triggered.connect(self._change_platform)
        transcript_act = QAction("📁  Open Transcripts", self)
        transcript_act.triggered.connect(self._open_transcripts)
        about_act = QAction("ℹ️  About VivekAI v3.0", self)
        about_act.triggered.connect(self._show_about)
        menu.addAction(change_act)
        menu.addSeparator()
        menu.addAction(transcript_act)
        menu.addAction(about_act)
        menu.exec_(self.mapToGlobal(self.rect().topRight()))

    def _change_platform(self):
        """Reset platform choice and show selector again"""
        from ui.platform_selector import reset_platform, PlatformSelector  # type: ignore
        if self.is_listening: self._stop_listening()
        if self.is_watching: self._stop_watching()
        reset_platform()
        selector = PlatformSelector()
        selector.platform_selected.connect(self._on_platform_changed)
        selector.show()
        self._selector = selector

    def _on_platform_changed(self, new_platform):
        """Handle platform change"""
        self.platform = new_platform
        self._build_ui()  # Rebuild UI with new platform
        self.status_label.setText(
            f"✅ Switched to {'Windows 🪟' if new_platform == 'windows' else 'macOS 🍎'}"
        )

    def _show_about(self):
        """Show about info in status"""
        plat = "Windows 🪟" if self.platform == "windows" else "macOS 🍎"
        self.status_label.setText(f"VivekAI v3.0 — {plat} — Mic + Screenshot + Auto Watch")

    def _build_controls(self):
        frame = QFrame(); frame.setObjectName("controls"); frame.setFixedHeight(54)
        h = QHBoxLayout(frame); h.setContentsMargins(12,6,12,6); h.setSpacing(8)
        self.mode_combo = QComboBox(); self.mode_combo.setObjectName("combo")
        self.mode_combo.setFixedWidth(148)
        for m in get_mode_list():
            self.mode_combo.addItem(f"{get_mode_icon(m)} {m}", m)
        self.engine_combo = QComboBox(); self.engine_combo.setObjectName("combo")
        self.engine_combo.setFixedWidth(110)
        for label, val in [("⚡ Groq","groq"),("🌟 Gemini","gemini"),("🏠 Ollama","ollama")]:
            self.engine_combo.addItem(label, val)
        self.listen_btn = QPushButton("▶  Start Mic")
        self.listen_btn.setFixedWidth(100)
        self.listen_btn.setObjectName("listenBtn")
        self.listen_btn.clicked.connect(self._toggle_listen)
        h.addWidget(self.mode_combo); h.addWidget(self.engine_combo)
        h.addStretch(); h.addWidget(self.listen_btn)
        return frame

    def _build_tabs(self):
        self.tabs = QTabWidget(); self.tabs.setObjectName("tabs")
        self.tabs.addTab(self._build_mic_tab(),        "🎙  Mic")
        self.tabs.addTab(self._build_screenshot_tab(), "📸  Screenshot")
        self.tabs.addTab(self._build_watch_tab(),      "👁  Auto Watch")
        return self.tabs

    def _build_mic_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12,10,12,8); v.setSpacing(8)
        v.addWidget(self._slabel("🎙  HEARD","#00E5FF"))
        self.heard_text = QTextEdit(); self.heard_text.setReadOnly(True)
        self.heard_text.setFixedHeight(72); self.heard_text.setObjectName("heardBox")
        self.heard_text.setPlaceholderText("Listening for audio...")
        v.addWidget(self.heard_text)
        v.addWidget(self._slabel("🤖  AI RESPONSE","#69FF47"))
        self.mic_response = QTextEdit(); self.mic_response.setReadOnly(True)
        self.mic_response.setObjectName("responseBox")
        self.mic_response.setPlaceholderText("AI answer appears here...")
        v.addWidget(self.mic_response, 1)
        v.addLayout(self._action_btns(self.mic_response))
        return w

    def _build_screenshot_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12,10,12,8); v.setSpacing(8)
        info = QLabel("Captures your entire screen → AI reads it → Answers automatically")
        info.setStyleSheet("color:#6B7280;font-size:10px;font-style:italic;font-family:'Segoe UI';")
        info.setWordWrap(True)
        v.addWidget(info)
        self.screenshot_btn = QPushButton("📸  Capture Screen & Get Answer")
        self.screenshot_btn.setObjectName("screenshotBtn")
        self.screenshot_btn.setFixedHeight(46)
        self.screenshot_btn.clicked.connect(self._do_screenshot)
        delay_row = QHBoxLayout()
        delay_lbl = QLabel("Capture delay:"); delay_lbl.setStyleSheet("color:#888;font-size:11px;font-family:'Segoe UI';")
        self.delay_combo = QComboBox(); self.delay_combo.setObjectName("combo"); self.delay_combo.setFixedWidth(100)
        for d in ["Instant","2 seconds","3 seconds","5 seconds"]:
            self.delay_combo.addItem(d)
        delay_row.addWidget(delay_lbl); delay_row.addWidget(self.delay_combo); delay_row.addStretch()
        v.addWidget(self.screenshot_btn); v.addLayout(delay_row)
        v.addWidget(self._slabel("👁  TEXT DETECTED ON SCREEN","#FFD700"))
        self.ocr_text = QTextEdit(); self.ocr_text.setReadOnly(True)
        self.ocr_text.setFixedHeight(72); self.ocr_text.setObjectName("heardBox")
        self.ocr_text.setPlaceholderText("Text extracted from screen appears here...")
        v.addWidget(self.ocr_text)
        v.addWidget(self._slabel("🤖  AI RESPONSE","#69FF47"))
        self.screenshot_response = QTextEdit(); self.screenshot_response.setReadOnly(True)
        self.screenshot_response.setObjectName("responseBox")
        self.screenshot_response.setPlaceholderText("AI answer appears here after screenshot...")
        v.addWidget(self.screenshot_response, 1)
        v.addLayout(self._action_btns(self.screenshot_response))
        return w

    def _build_watch_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.setContentsMargins(12,10,12,8); v.setSpacing(8)
        info = QLabel("Watches a screen region continuously. When new question appears → AI answers automatically!")
        info.setStyleSheet("color:#6B7280;font-size:10px;font-style:italic;font-family:'Segoe UI';")
        info.setWordWrap(True); v.addWidget(info)
        self.region_label = QLabel("📍  No region selected — click Select Region or Full Screen")
        self.region_label.setStyleSheet(
            "color:#FFD700;font-size:10px;font-weight:600;"
            "background:rgba(255,215,0,0.08);border:1px solid rgba(255,215,0,0.2);"
            "border-radius:6px;padding:6px 10px;font-family:'Segoe UI';")
        self.region_label.setWordWrap(True); v.addWidget(self.region_label)
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        self.select_region_btn = QPushButton("🖱  Select Region")
        self.select_region_btn.setObjectName("regionBtn")
        self.select_region_btn.clicked.connect(self._select_region)
        self.fullscreen_btn = QPushButton("🖥  Full Screen")
        self.fullscreen_btn.setObjectName("regionBtn")
        self.fullscreen_btn.clicked.connect(self._use_fullscreen)
        self.watch_btn = QPushButton("👁  Start Watching")
        self.watch_btn.setObjectName("watchBtn")
        self.watch_btn.clicked.connect(self._toggle_watch)
        btn_row.addWidget(self.select_region_btn); btn_row.addWidget(self.fullscreen_btn); btn_row.addWidget(self.watch_btn)
        v.addLayout(btn_row)
        int_row = QHBoxLayout()
        int_lbl = QLabel("Check every:"); int_lbl.setStyleSheet("color:#888;font-size:11px;font-family:'Segoe UI';")
        self.interval_combo = QComboBox(); self.interval_combo.setObjectName("combo"); self.interval_combo.setFixedWidth(110)
        for intv in ["1 second","2 seconds","3 seconds","5 seconds"]:
            self.interval_combo.addItem(intv)
        self.interval_combo.setCurrentIndex(1)
        self.interval_combo.currentIndexChanged.connect(self._update_interval)
        int_row.addWidget(int_lbl); int_row.addWidget(self.interval_combo); int_row.addStretch()
        v.addLayout(int_row)
        v.addWidget(self._slabel("👁  DETECTED ON SCREEN","#FFD700"))
        self.watch_detected = QTextEdit(); self.watch_detected.setReadOnly(True)
        self.watch_detected.setFixedHeight(72); self.watch_detected.setObjectName("heardBox")
        self.watch_detected.setPlaceholderText("Screen text appears here automatically...")
        v.addWidget(self.watch_detected)
        v.addWidget(self._slabel("🤖  AUTO AI RESPONSE","#69FF47"))
        self.watch_response = QTextEdit(); self.watch_response.setReadOnly(True)
        self.watch_response.setObjectName("responseBox")
        self.watch_response.setPlaceholderText("AI answers automatically when new content detected...")
        v.addWidget(self.watch_response, 1)
        v.addLayout(self._action_btns(self.watch_response))
        return w

    def _build_statusbar(self):
        bar = QFrame(); bar.setFixedHeight(28); bar.setObjectName("statusBar")
        h = QHBoxLayout(bar); h.setContentsMargins(12,0,12,0)
        self.status_label = QLabel("⏳ Loading Whisper...")
        self.status_label.setStyleSheet("color:#888;font-size:10px;")
        self.count_label = QLabel("0 answers")
        self.count_label.setStyleSheet("color:#555;font-size:10px;")
        h.addWidget(self.status_label); h.addStretch(); h.addWidget(self.count_label)
        return bar

    def _slabel(self, text, color):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{color};font-size:9px;font-weight:700;letter-spacing:1.5px;font-family:'Segoe UI';")
        return lbl

    def _action_btns(self, textbox):
        row = QHBoxLayout(); row.setSpacing(6)
        c = QPushButton("📋  Copy Answer"); c.setObjectName("copyBtn"); c.clicked.connect(lambda: self._copy(textbox))
        d = QPushButton("🗑  Clear"); d.setObjectName("clearBtn"); d.clicked.connect(textbox.clear)
        f = QPushButton("📁  Transcripts"); f.setObjectName("clearBtn"); f.clicked.connect(self._open_transcripts)
        row.addWidget(c); row.addWidget(d); row.addWidget(f)
        return row

    def _icon_btn(self, text, color, callback):
        btn = QPushButton(text); btn.setFixedSize(26,26)
        btn.setStyleSheet(f"QPushButton{{background:transparent;color:{color};border:none;font-size:13px;border-radius:5px;}}QPushButton:hover{{background:rgba(255,255,255,0.08);}}")
        btn.clicked.connect(callback); return btn

    def _connect_signals(self):
        self.signals.transcript_ready.connect(self._on_transcript)
        self.signals.response_ready.connect(self._on_mic_response)
        self.signals.status_update.connect(self.status_label.setText)
        self.signals.model_loaded.connect(lambda: self.status_label.setText("✅ Ready — Mic, Screenshot & Auto-Watch available"))
        self.signals.screen_text_ready.connect(self._on_screen_text)
        self.signals.vision_ready.connect(self._on_vision_response)
        self.engine_combo.currentIndexChanged.connect(lambda: self.ai_engine.set_engine(self.engine_combo.currentData()))
        self.trigger_auto_watch.connect(self._do_auto_watch_ai)

    def _load_whisper_async(self):
        def load():
            self.transcriber.load_model(lambda m: self.signals.status_update.emit(m))
            self.signals.model_loaded.emit()
        threading.Thread(target=load, daemon=True).start()

    def _toggle_listen(self):
        if not self.transcriber.is_loaded:
            self.status_label.setText("⏳ Whisper still loading..."); return
        self._start_listening() if not self.is_listening else self._stop_listening()

    def _start_listening(self):
        self.is_listening = True
        self.listen_btn.setText("■  Stop Mic"); self.listen_btn.setProperty("active","true"); self.listen_btn.setStyle(self.listen_btn.style())
        mode = self.mode_combo.currentData(); engine = self.engine_combo.currentData()
        self.ai_engine.set_engine(engine); self.transcript_mgr.start_session(mode, engine.upper())
        self.audio_capture = AudioCapture(self._on_audio_chunk); self.audio_capture.start()
        self.status_label.setText(f"🔴 Listening | {mode} | {engine.upper()}")

    def _stop_listening(self):
        self.is_listening = False
        self.listen_btn.setText("▶  Start Mic"); self.listen_btn.setProperty("active","false"); self.listen_btn.setStyle(self.listen_btn.style())
        if self.audio_capture: self.audio_capture.stop(); self.audio_capture = None
        self.transcript_mgr.stop_session()
        self.status_label.setText(f"⏹ Stopped | {self.transcript_mgr.get_entry_count()} saved")

    def _on_audio_chunk(self, audio_chunk, sample_rate):
        def process():
            text = self.transcriber.transcribe(audio_chunk, sample_rate)
            if text:
                self.signals.transcript_ready.emit(text)
                worker = AIWorker(text, get_system_prompt(self.mode_combo.currentData()), self.ai_engine, self.signals)
                self.workers.append(worker)
                worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
                worker.start()
        threading.Thread(target=process, daemon=True).start()

    def _on_transcript(self, text):
        self.heard_text.setPlainText(text); self.status_label.setText("⚡ Generating response...")

    def _on_mic_response(self, response, engine, elapsed):
        self.mic_response.setPlainText(response)
        self.transcript_mgr.add_entry(self.heard_text.toPlainText(), response)
        self.count_label.setText(f"{self.transcript_mgr.get_entry_count()} answers")
        self.status_label.setText(f"✅ {engine} | {elapsed}s | {'🔴 Listening' if self.is_listening else 'Ready'}")

    def _do_screenshot(self):
        delays = {"Instant":0,"2 seconds":2,"3 seconds":3,"5 seconds":5}
        delay = delays.get(self.delay_combo.currentText(), 0)
        self.screenshot_btn.setText("⏳  Capturing...")
        self.screenshot_btn.setEnabled(False)
        self.status_label.setText(f"📸 Capturing in {self.delay_combo.currentText()}...")

        def _prepare_capture():
            self.hide()
            # Allow window to actually vanish before snapping the screen
            QTimer.singleShot(150, _execute_capture)

        def _execute_capture():
            QApplication.processEvents()
            screenshot, ocr_text = self.screen_vision.capture_and_read()
            self.show()
            
            if screenshot:
                if ocr_text: self.signals.screen_text_ready.emit(ocr_text)
                self.status_label.setText("🤖 Vision AI analyzing screen...")
                worker = VisionWorker(screenshot, self.mode_combo.currentData(), self.vision_client, self.signals)
                self.workers.append(worker)
                worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
                worker.start()
            else:
                self.status_label.setText("❌ Screenshot failed — check Tesseract install")
            
            self.screenshot_btn.setText("📸  Capture Screen & Get Answer")
            self.screenshot_btn.setEnabled(True)

        QTimer.singleShot(max(10, delay * 1000), _prepare_capture)

    def _on_screen_text(self, text):
        short = text[:500] + "..." if len(text) > 500 else text
        self.ocr_text.setPlainText(short); self.watch_detected.setPlainText(short)

    def _on_vision_response(self, response, engine, elapsed):
        self.screenshot_response.setPlainText(response); self.watch_response.setPlainText(response)
        self.transcript_mgr.add_entry("[Screen]", response)
        self.count_label.setText(f"{self.transcript_mgr.get_entry_count()} answers")
        self.status_label.setText(f"✅ {engine} | {elapsed}s")

    def _select_region(self):
        self.hide(); QTimer.singleShot(300, self._open_selector)

    def _open_selector(self):
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self._on_region_selected)
        self.selector.cancelled.connect(lambda: self.show())
        self.selector.show()

    def _on_region_selected(self, x1, y1, x2, y2):
        self.watch_region = (x1, y1, x2, y2)
        self.screen_vision.set_region(x1, y1, x2, y2)
        self.region_label.setText(f"📍  Region: ({x1},{y1}) → ({x2},{y2})  [{x2-x1}×{y2-y1}px]")
        self.show(); self.status_label.setText("✅ Region selected — click 'Start Watching'")

    def _use_fullscreen(self):
        self.watch_region = None; self.screen_vision.watch_region = None
        self.region_label.setText("📍  Full screen selected — click 'Start Watching'")

    def _toggle_watch(self):
        self._start_watching() if not self.is_watching else self._stop_watching()

    def _start_watching(self):
        self.is_watching = True
        self.watch_btn.setText("⏹  Stop Watching"); self.watch_btn.setProperty("active","true"); self.watch_btn.setStyle(self.watch_btn.style())
        self.screen_vision.start_watching(self.watch_region)
        self.status_label.setText(f"👁 Watching {'full screen' if not self.watch_region else 'region'} for new content...")

    def _stop_watching(self):
        self.is_watching = False
        self.watch_btn.setText("👁  Start Watching"); self.watch_btn.setProperty("active","false"); self.watch_btn.setStyle(self.watch_btn.style())
        self.screen_vision.stop_watching(); self.status_label.setText("⏹ Auto-watch stopped")

    def _on_screen_text_detected(self, text):
        # Called from background threading.Thread by ScreenVision.
        # Fire signal to securely cross into GUI main thread!
        self.trigger_auto_watch.emit(text)

    def _do_auto_watch_ai(self, text):
        # Safe to access GUI widgets since we're in the main thread now
        self.signals.screen_text_ready.emit(text)
        watch_signals = WorkerSignals()
        watch_signals.response_ready.connect(
            lambda r, e, t: self.signals.vision_ready.emit(r, e, t)
        )
        worker = AIWorker(
            f"Answer this from screen:\n{text[:800]}",
            get_system_prompt(self.mode_combo.currentData()),
            self.ai_engine,
            watch_signals
        )
        self.workers.append(worker)
        worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        worker.start()

    def _update_interval(self):
        intervals = {"1 second":1.0,"2 seconds":2.0,"3 seconds":3.0,"5 seconds":5.0}
        self.screen_vision.watch_interval = intervals.get(self.interval_combo.currentText(), 2.0)

    def _copy(self, textbox):
        text = textbox.toPlainText()
        if text:
            pyperclip.copy(text); self.status_label.setText("📋 Copied!")
            QTimer.singleShot(2000, lambda: self.status_label.setText("✅ Ready"))

    def _open_transcripts(self):
        open_folder(self.transcript_mgr.get_transcript_dir())

    def _toggle_minimize(self):
        if not self._is_minimized:
            # Minimize: collapse to title-bar only
            self._normal_height = self.height()
            self._is_minimized = True
            self.setMinimumHeight(46)
            self.setMaximumHeight(46)
            self.resize(self.width(), 46)
        else:
            # Restore
            self._is_minimized = False
            self.setMinimumSize(300, 380)
            self.setMaximumSize(16777215, 16777215)
            self.resize(self.width(), self._normal_height)

    # ── Title-bar drag (called from bar.mousePressEvent / bar.mouseMoveEvent) ──
    def _drag_start(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def _drag_move(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos and not self._resize_dir:
            self.move(e.globalPos() - self._drag_pos)

    # ── Resize helpers ──
    def _get_resize_dir(self, pos):
        """Return (str direction, Qt cursor) for a local mouse position, or None."""
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
        """Update window geometry based on mouse movement during resize."""
        if not self._resize_dir or not self._resize_start_geom or not self._resize_start_pos:
            return
        dx = global_pos.x() - self._resize_start_pos.x()  # type: ignore
        dy = global_pos.y() - self._resize_start_pos.y()  # type: ignore
        g  = self._resize_start_geom
        x, y, w, h = g.x(), g.y(), g.width(), g.height()  # type: ignore
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        d = self._resize_dir
        if d in ("r",  "tr", "br"): w  = max(min_w, w + dx)
        if d in ("l",  "tl", "bl"): new_x = x + dx; new_w = w - dx
        if d in ("b",  "bl", "br"): h  = max(min_h, h + dy)
        if d in ("t",  "tl", "tr"): new_y = y + dy; new_h = h - dy
        if d in ("l",  "tl", "bl") and new_w >= min_w:  # type: ignore
            x = new_x; w = new_w  # type: ignore
        if d in ("t",  "tl", "tr") and new_h >= min_h:  # type: ignore
            y = new_y; h = new_h  # type: ignore
        self.setGeometry(x, y, w, h)

    # ── Event filter: intercepts container mouse events and routes to resize logic ──
    def eventFilter(self, obj, event):
        if obj is not self.container:
            return super().eventFilter(obj, event)

        etype = event.type()

        if etype == QEvent.MouseMove:
            # Remap local pos from container coords → window coords (they match
            # since container always fills the window, but mapTo is explicit)
            win_pos = self.container.mapTo(self, event.pos())

            if event.buttons() == Qt.LeftButton and self._resize_dir:
                # Active resize drag
                self._apply_resize(event.globalPos())
                return True
            elif event.buttons() == Qt.LeftButton and self._drag_pos:
                # Title-bar drag handled via _drag_move; nothing extra needed
                pass
            else:
                # Hover — show resize cursor near edges, normal cursor inside
                result = self._get_resize_dir(win_pos)
                if result:
                    self.container.setCursor(QCursor(result[1]))
                else:
                    self.container.unsetCursor()

        elif etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            win_pos = self.container.mapTo(self, event.pos())
            result  = self._get_resize_dir(win_pos)
            if result:
                self._resize_dir        = result[0]  # type: ignore
                self._resize_start_geom = self.geometry()
                self._resize_start_pos  = event.globalPos()
                return True   # consume — don’t pass to child widgets

        elif etype == QEvent.MouseButtonRelease:
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

    def resizeEvent(self, e):
        """Keep the inner container perfectly filling the window at all times."""
        if hasattr(self, "container"):
            self.container.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(0,0,0,0))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 14, 14)

    def closeEvent(self, e):
        if self.is_listening: self._stop_listening()
        if self.is_watching: self._stop_watching()
        e.accept()

    def _stylesheet(self):
        return """
        #container {
            background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(12,14,22,0.97),stop:1 rgba(8,10,18,0.97));
            border-radius:14px; border:1px solid rgba(0,229,255,0.18);
        }
        #titleBar { background:rgba(0,229,255,0.05); border-bottom:1px solid rgba(0,229,255,0.12); border-top-left-radius:14px; border-top-right-radius:14px; }
        #controls { background:rgba(255,255,255,0.02); border-bottom:1px solid rgba(255,255,255,0.05); }
        #statusBar { background:rgba(0,0,0,0.2); border-top:1px solid rgba(255,255,255,0.05); border-bottom-left-radius:14px; border-bottom-right-radius:14px; }
        QTabWidget#tabs::pane { border:none; background:transparent; }
        QTabBar::tab { background:rgba(255,255,255,0.04); color:#888; padding:8px 16px; border:none; font-family:'Segoe UI'; font-size:11px; }
        QTabBar::tab:selected { background:rgba(0,229,255,0.1); color:#00E5FF; border-bottom:2px solid #00E5FF; }
        QTabBar::tab:hover { background:rgba(255,255,255,0.08); color:#CCC; }
        QComboBox#combo { background:rgba(255,255,255,0.06); color:#E0E0E0; border:1px solid rgba(255,255,255,0.1); border-radius:7px; padding:4px 10px; font-size:12px; font-family:'Segoe UI'; }
        QComboBox QAbstractItemView { background:#0D1117; color:#E0E0E0; selection-background-color:rgba(0,229,255,0.2); border:1px solid rgba(0,229,255,0.2); border-radius:6px; }
        QPushButton#listenBtn { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00B4DB,stop:1 #0083B0); color:white; border:none; border-radius:7px; padding:5px 12px; font-size:11px; font-weight:600; font-family:'Segoe UI'; }
        QPushButton#listenBtn[active="true"] { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF4E50,stop:1 #F9D423); }
        QPushButton#screenshotBtn { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #4F46E5); color:white; border:none; border-radius:8px; font-size:13px; font-weight:700; font-family:'Segoe UI'; }
        QPushButton#screenshotBtn:disabled { background:#333; color:#666; }
        QPushButton#regionBtn { background:rgba(255,215,0,0.1); color:#FFD700; border:1px solid rgba(255,215,0,0.3); border-radius:7px; padding:6px 12px; font-size:11px; font-family:'Segoe UI'; }
        QPushButton#watchBtn { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #059669,stop:1 #10B981); color:white; border:none; border-radius:7px; padding:6px 14px; font-size:11px; font-weight:700; font-family:'Segoe UI'; }
        QPushButton#watchBtn[active="true"] { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #FF4E50,stop:1 #F9D423); }
        QPushButton#copyBtn { background:rgba(105,255,71,0.1); color:#69FF47; border:1px solid rgba(105,255,71,0.25); border-radius:7px; padding:5px 12px; font-size:11px; font-family:'Segoe UI'; }
        QPushButton#clearBtn { background:rgba(255,255,255,0.05); color:#888; border:1px solid rgba(255,255,255,0.08); border-radius:7px; padding:5px 12px; font-size:11px; font-family:'Segoe UI'; }
        QTextEdit#heardBox { background:rgba(0,229,255,0.04); color:#B0BEC5; border:1px solid rgba(0,229,255,0.12); border-radius:8px; padding:8px; font-size:12px; font-family:'Segoe UI'; }
        QTextEdit#responseBox { background:rgba(105,255,71,0.04); color:#E8F5E9; border:1px solid rgba(105,255,71,0.15); border-radius:8px; padding:10px; font-size:13px; font-family:'Segoe UI'; }
        QScrollBar:vertical { background:transparent; width:4px; }
        QScrollBar::handle:vertical { background:rgba(0,229,255,0.3); border-radius:2px; }
        """
