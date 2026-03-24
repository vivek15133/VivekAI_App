"""
VivekAI_App - Screen Region Selector v3.1
Lets user drag-select which part of screen to watch.
FIXED: Invisible to screen share (SetWindowDisplayAffinity on Windows,
       NSWindowSharingNone on macOS).  Resize cursor never leaks.
"""

import platform as _platform
from PyQt5.QtWidgets import QWidget, QApplication, QRubberBand
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush


class RegionSelector(QWidget):
    """
    Full-screen overlay that lets user drag-select a region.
    Emits region_selected(x1, y1, x2, y2) when done.
    INVISIBLE to screen-share / OBS / recording software.
    """
    region_selected = pyqtSignal(int, int, int, int)
    cancelled       = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint  |
            Qt.WindowStaysOnTopHint |
            Qt.Tool                 |
            Qt.WindowDoesNotAcceptFocus   # extra: keeps it out of alt-tab list
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.55)
        self.setCursor(Qt.CrossCursor)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.origin      = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.selecting   = False

        # Apply screen-capture exclusion AFTER the window handle exists
        QTimer.singleShot(200, self._exclude_from_capture)

    # ── Screen-capture exclusion ──────────────────────────────────────────────
    def _exclude_from_capture(self):
        """Make this window invisible to all screen-capture/sharing APIs."""
        system = _platform.system()
        if system == "Windows":
            self._exclude_windows()
        elif system == "Darwin":
            self._exclude_macos()

    def _exclude_windows(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011  (Win10 2004+)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            print("[RegionSelector] Windows capture exclusion applied")
        except Exception as e:
            print(f"[RegionSelector] Windows exclusion failed: {e}")

    def _exclude_macos(self):
        try:
            import ctypes, ctypes.util
            objc = ctypes.cdll.LoadLibrary(
                ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib"
            )
            objc.objc_getClass.restype  = ctypes.c_void_p
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.objc_msgSend.restype   = ctypes.c_void_p
            objc.objc_msgSend.argtypes  = [ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_void_p]
            ns_view  = ctypes.c_void_p(int(self.winId()))
            window   = objc.objc_msgSend(ns_view,
                            objc.sel_registerName(b"window"), None)
            # NSWindowSharingNone = 0
            objc.objc_msgSend(window,
                objc.sel_registerName(b"setSharingType:"),
                ctypes.c_void_p(0))
            print("[RegionSelector] macOS capture exclusion applied")
        except Exception as e:
            print(f"[RegionSelector] macOS exclusion failed: {e}")

    # ── Drawing ───────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        painter.setPen(QPen(QColor(0, 229, 255), 2))
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "🖱  Drag to select the screen region to watch\n"
            "Press ESC to cancel"
        )

    # ── Mouse interaction ─────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            self.selecting = True

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.rubber_band.setGeometry(
                QRect(self.origin, event.pos()).normalized()
            )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            self.rubber_band.hide()
            rect = QRect(self.origin, event.pos()).normalized()
            if rect.width() > 50 and rect.height() > 50:
                self.region_selected.emit(
                    rect.x(), rect.y(),
                    rect.x() + rect.width(),
                    rect.y() + rect.height()
                )
            else:
                self.cancelled.emit()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
