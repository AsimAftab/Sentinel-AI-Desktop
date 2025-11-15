"""
Modern Loading Spinner Widget for Sentinel AI
Smooth circular loading animation
"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QConicalGradient


class LoadingSpinner(QWidget):
    """Circular loading spinner with gradient effect"""

    def __init__(self, parent=None, size=48, color=None):
        super().__init__(parent)
        self.angle = 0
        self.size = size
        self.color = color or QColor(79, 70, 229)  # Default indigo

        self.setFixedSize(size, size)

        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(20)  # Update every 20ms for smooth animation

    def rotate(self):
        """Rotate the spinner"""
        self.angle = (self.angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        """Custom paint for spinner"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Create gradient
        gradient = QConicalGradient(self.size / 2, self.size / 2, self.angle)
        gradient.setColorAt(0, QColor(self.color.red(), self.color.green(),
                                      self.color.blue(), 0))
        gradient.setColorAt(0.5, QColor(self.color.red(), self.color.green(),
                                       self.color.blue(), 200))
        gradient.setColorAt(1, self.color)

        # Draw spinning arc
        pen = QPen()
        pen.setWidth(4)
        pen.setBrush(gradient)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        rect = QRectF(4, 4, self.size - 8, self.size - 8)
        painter.drawArc(rect, 0, 270 * 16)  # Draw 270 degrees

    def start(self):
        """Start spinner animation"""
        if not self.timer.isActive():
            self.timer.start(20)
            self.show()

    def stop(self):
        """Stop spinner animation"""
        self.timer.stop()
        self.hide()


class LoadingOverlay(QWidget):
    """Full-screen loading overlay with spinner and message"""

    def __init__(self, parent=None, message="Loading..."):
        super().__init__(parent)
        self.message = message

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        if parent:
            self.setGeometry(parent.rect())

        self.spinner = LoadingSpinner(self, size=64)
        self.spinner.move(
            (self.width() - self.spinner.width()) // 2,
            (self.height() - self.spinner.height()) // 2 - 30
        )

    def paintEvent(self, event):
        """Paint semi-transparent background and message"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Semi-transparent background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))

        # Draw message below spinner
        painter.setPen(QColor(255, 255, 255))
        text_rect = QRectF(0, self.height() // 2 + 50, self.width(), 30)
        painter.drawText(text_rect, Qt.AlignCenter, self.message)

    def show_overlay(self):
        """Show loading overlay"""
        self.spinner.start()
        self.show()
        self.raise_()

    def hide_overlay(self):
        """Hide loading overlay"""
        self.spinner.stop()
        self.hide()
