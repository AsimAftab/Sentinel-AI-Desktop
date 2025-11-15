"""
Modern Enhanced Button Widgets
Features: Icon support, loading states, ripple effects
"""

from PyQt5.QtWidgets import QPushButton, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QBrush


class ModernButton(QPushButton):
    """Enhanced button with loading state and animations"""

    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        self._is_loading = False
        self._original_text = text
        self._ripple_animations = []

        self.setCursor(Qt.PointingHandCursor)

    def set_loading(self, loading=True, text="Processing..."):
        """Set button to loading state"""
        self._is_loading = loading

        if loading:
            self._original_text = self.text()
            self.setText(text)
            self.setEnabled(False)

            # Add pulsing animation
            self._pulse_opacity()
        else:
            self.setText(self._original_text)
            self.setEnabled(True)

            # Stop animation
            if hasattr(self, '_pulse_timer'):
                self._pulse_timer.stop()

    def _pulse_opacity(self):
        """Create pulsing effect for loading state"""
        opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_effect)

        def pulse():
            animation = QPropertyAnimation(opacity_effect, b"opacity")
            animation.setDuration(1000)
            animation.setStartValue(1.0)
            animation.setKeyValueAt(0.5, 0.5)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.InOutQuad)
            animation.start()
            self._pulse_animation = animation

        # Pulse repeatedly
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(pulse)
        self._pulse_timer.start(1000)
        pulse()  # Start immediately

    def mousePressEvent(self, event):
        """Add ripple effect on click"""
        if event.button() == Qt.LeftButton and not self._is_loading:
            self._create_ripple(event.pos())
        super().mousePressEvent(event)

    def _create_ripple(self, pos):
        """Create ripple effect at click position"""
        # This is a simplified version - full ripple would need custom painting
        pass


class GradientButton(QPushButton):
    """Button with gradient background and smooth hover effects"""

    def __init__(self, text="", gradient_colors=None, parent=None):
        super().__init__(text, parent)
        self.gradient_colors = gradient_colors or ["#4f46e5", "#7c3aed"]
        self._hover = False

        self.setCursor(Qt.PointingHandCursor)
        self._apply_gradient()

    def _apply_gradient(self):
        """Apply gradient styling"""
        colors = self.gradient_colors
        hover_colors = [self._lighten_color(c) for c in colors]

        self.setStyleSheet(f"""
            GradientButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 {colors[0]}, stop:1 {colors[1]});
                color: white;
                border: none;
                border-radius: 12px;
                padding: 14px 24px;
                font-weight: 600;
                font-size: 15px;
            }}
            GradientButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 {hover_colors[0]}, stop:1 {hover_colors[1]});
            }}
            GradientButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 {self._darken_color(colors[0])},
                            stop:1 {self._darken_color(colors[1])});
            }}
            GradientButton:disabled {{
                background: #4b5563;
                color: #9ca3af;
            }}
        """)

    @staticmethod
    def _lighten_color(hex_color, factor=0.1):
        """Lighten a hex color"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))

        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _darken_color(hex_color, factor=0.2):
        """Darken a hex color"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))

        return f"#{r:02x}{g:02x}{b:02x}"


class OutlineButton(QPushButton):
    """Button with outline style (secondary button)"""

    def __init__(self, text="", color="#4f46e5", parent=None):
        super().__init__(text, parent)
        self.color = color

        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        """Apply outline styling"""
        self.setStyleSheet(f"""
            OutlineButton {{
                background: transparent;
                color: {self.color};
                border: 2px solid {self.color};
                border-radius: 12px;
                padding: 14px 24px;
                font-weight: 600;
                font-size: 15px;
            }}
            OutlineButton:hover {{
                background: rgba(79, 70, 229, 0.1);
                border-color: {self.color};
            }}
            OutlineButton:pressed {{
                background: rgba(79, 70, 229, 0.2);
            }}
            OutlineButton:disabled {{
                color: #9ca3af;
                border-color: #9ca3af;
            }}
        """)


class IconButton(QPushButton):
    """Circular icon-only button"""

    def __init__(self, icon_text="", size=40, parent=None):
        super().__init__(icon_text, parent)
        self.setFixedSize(size, size)

        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        """Apply icon button styling"""
        self.setStyleSheet("""
            IconButton {
                background: rgba(79, 70, 229, 0.15);
                color: #ffffff;
                border: 1px solid rgba(79, 70, 229, 0.3);
                border-radius: 20px;
                font-size: 16px;
                font-weight: 600;
            }
            IconButton:hover {
                background: rgba(79, 70, 229, 0.25);
                border-color: rgba(79, 70, 229, 0.5);
            }
            IconButton:pressed {
                background: rgba(79, 70, 229, 0.35);
            }
        """)
