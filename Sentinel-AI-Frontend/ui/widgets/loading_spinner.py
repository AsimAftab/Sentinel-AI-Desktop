"""
Modern Loading Spinner Widget for Sentinel AI
Smooth circular loading animation
"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
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
        self._opacity = 0.0

        # Make it a normal child widget that overlays the parent
        # Remove Qt.Tool flag to make it a true child widget
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Hide by default
        self.hide()

        # Create spinner
        self.spinner = LoadingSpinner(self, size=60, color=QColor(59, 130, 246))

        # Fade animation
        self.fade_animation = QPropertyAnimation(self, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)

    def _position_spinner(self):
        """Center the spinner"""
        if self.width() > 0 and self.height() > 0:
            x = (self.width() - self.spinner.width()) // 2
            y = (self.height() - self.spinner.height()) // 2 - 20
            self.spinner.move(x, y)

    def paintEvent(self, event):
        """Paint semi-transparent background and message"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Semi-transparent dark background with blur effect
        bg_color = QColor(10, 14, 26)
        bg_color.setAlpha(int(180 * self._opacity))
        painter.fillRect(self.rect(), bg_color)

        # Draw message below spinner
        text_color = QColor(226, 232, 240)
        text_color.setAlpha(int(255 * self._opacity))
        painter.setPen(text_color)

        # Use larger, better font for message
        font = painter.font()
        font.setPointSize(14)
        font.setWeight(500)
        painter.setFont(font)

        text_rect = QRectF(0, self.height() // 2 + 60, self.width(), 40)
        painter.drawText(text_rect, Qt.AlignCenter, self.message)

    def show_overlay(self):
        """Show loading overlay with fade-in animation"""
        # Update geometry to match parent before showing
        if self.parent():
            # Set geometry to cover entire parent widget
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())

        # Position spinner after geometry is set
        self._position_spinner()
        self.spinner.start()
        self.show()
        self.raise_()  # Ensure it's on top of all siblings

        # Fade in
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()

    def hide_overlay(self):
        """Hide loading overlay with fade-out animation"""
        # Fade out
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self._finish_hide)
        self.fade_animation.start()

    def _finish_hide(self):
        """Complete hiding after fade-out"""
        self.spinner.stop()
        self.hide()
        self.fade_animation.finished.disconnect(self._finish_hide)

    def resizeEvent(self, event):
        """Reposition spinner on resize and update geometry"""
        super().resizeEvent(event)
        # Update geometry to match parent if visible
        if self.isVisible() and self.parent():
            self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        self._position_spinner()

    @pyqtProperty(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()
