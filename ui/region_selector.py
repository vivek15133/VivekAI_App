"""
VivekAI_App - Screen Region Selector
Lets user drag-select which part of screen to watch
"""

from PyQt5.QtWidgets import QWidget, QApplication, QRubberBand
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush


class RegionSelector(QWidget):
    """
    Full-screen overlay that lets user drag-select a region
    Emits region_selected(x1, y1, x2, y2) when done
    """
    region_selected = pyqtSignal(int, int, int, int)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.5)
        self.setCursor(Qt.CrossCursor)

        # Cover entire screen
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        self.origin = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.selecting = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # Instructions
        painter.setPen(QPen(QColor(0, 229, 255), 2))
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "🖱  Drag to select the screen region to watch\n"
            "Press ESC to cancel"
        )

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
