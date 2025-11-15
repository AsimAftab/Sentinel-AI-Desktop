"""
Modern Toast Notification System for Sentinel AI
Elegant, non-intrusive notifications with auto-dismiss
"""

from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QFont


class ToastNotification(QWidget):
    """Modern toast notification widget"""

    closed = pyqtSignal()

    # Toast types
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __init__(self, message, toast_type=INFO, duration=3000, parent=None):
        super().__init__(parent)
        self.message = message
        self.toast_type = toast_type
        self.duration = duration

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.setup_ui()
        self.apply_styling()

        # Auto-dismiss timer
        QTimer.singleShot(duration, self.fade_out)

    def setup_ui(self):
        """Setup the toast UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Icon label
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(24, 24)

        icon_map = {
            self.SUCCESS: "✓",
            self.ERROR: "✗",
            self.WARNING: "⚠",
            self.INFO: "ℹ"
        }
        self.icon_label.setText(icon_map.get(self.toast_type, "ℹ"))
        self.icon_label.setFont(QFont("Segoe UI", 14, QFont.Bold))

        # Message label
        self.message_label = QLabel(self.message)
        self.message_label.setWordWrap(True)
        self.message_label.setFont(QFont("Segoe UI", 11))

        layout.addWidget(self.icon_label)
        layout.addWidget(self.message_label, 1)

        self.setLayout(layout)
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        self.adjustSize()

    def apply_styling(self):
        """Apply modern styling based on toast type"""
        color_schemes = {
            self.SUCCESS: {
                "bg": "rgba(16, 185, 129, 0.95)",
                "border": "#10b981",
                "text": "#ffffff",
                "icon": "#ffffff"
            },
            self.ERROR: {
                "bg": "rgba(239, 68, 68, 0.95)",
                "border": "#ef4444",
                "text": "#ffffff",
                "icon": "#ffffff"
            },
            self.WARNING: {
                "bg": "rgba(245, 158, 11, 0.95)",
                "border": "#f59e0b",
                "text": "#ffffff",
                "icon": "#ffffff"
            },
            self.INFO: {
                "bg": "rgba(79, 70, 229, 0.95)",
                "border": "#4f46e5",
                "text": "#ffffff",
                "icon": "#ffffff"
            }
        }

        scheme = color_schemes.get(self.toast_type, color_schemes[self.INFO])

        self.setStyleSheet(f"""
            ToastNotification {{
                background: {scheme['bg']};
                border: 2px solid {scheme['border']};
                border-radius: 12px;
            }}
        """)

        self.icon_label.setStyleSheet(f"color: {scheme['icon']};")
        self.message_label.setStyleSheet(f"color: {scheme['text']};")

    def show_animated(self):
        """Show toast with fade-in animation"""
        self.show()

        # Fade in animation
        opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_effect)

        self.fade_in_animation = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(300)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_in_animation.start()

    def fade_out(self):
        """Fade out and close toast"""
        opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacity_effect)

        self.fade_out_animation = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(300)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_out_animation.finished.connect(self.close)
        self.fade_out_animation.start()

    def closeEvent(self, event):
        """Emit closed signal when toast is closed"""
        self.closed.emit()
        super().closeEvent(event)


class ToastManager:
    """Manages multiple toast notifications"""

    _instance = None
    _toasts = []
    _spacing = 15
    _margin = 20

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToastManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    def show_success(cls, message, parent=None, duration=3000):
        """Show success toast"""
        return cls._show_toast(message, ToastNotification.SUCCESS, parent, duration)

    @classmethod
    def show_error(cls, message, parent=None, duration=4000):
        """Show error toast"""
        return cls._show_toast(message, ToastNotification.ERROR, parent, duration)

    @classmethod
    def show_warning(cls, message, parent=None, duration=3500):
        """Show warning toast"""
        return cls._show_toast(message, ToastNotification.WARNING, parent, duration)

    @classmethod
    def show_info(cls, message, parent=None, duration=3000):
        """Show info toast"""
        return cls._show_toast(message, ToastNotification.INFO, parent, duration)

    @classmethod
    def _show_toast(cls, message, toast_type, parent, duration):
        """Internal method to create and show toast"""
        toast = ToastNotification(message, toast_type, duration, parent)

        # Position toast
        cls._position_toast(toast, parent)

        # Add to active toasts list
        cls._toasts.append(toast)

        # Remove from list when closed
        toast.closed.connect(lambda: cls._remove_toast(toast))

        # Show with animation
        toast.show_animated()

        return toast

    @classmethod
    def _position_toast(cls, toast, parent):
        """Position toast in bottom-right corner"""
        if parent:
            parent_rect = parent.geometry()
            x = parent_rect.right() - toast.width() - cls._margin
            y = parent_rect.bottom() - toast.height() - cls._margin

            # Stack toasts vertically
            for existing_toast in cls._toasts:
                if existing_toast.isVisible():
                    y -= existing_toast.height() + cls._spacing

            toast.move(x, y)
        else:
            # Fallback positioning
            from PyQt5.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            x = screen.right() - toast.width() - cls._margin
            y = screen.bottom() - toast.height() - cls._margin

            for existing_toast in cls._toasts:
                if existing_toast.isVisible():
                    y -= existing_toast.height() + cls._spacing

            toast.move(x, y)

    @classmethod
    def _remove_toast(cls, toast):
        """Remove toast from active list"""
        if toast in cls._toasts:
            cls._toasts.remove(toast)
            cls._reposition_toasts()

    @classmethod
    def _reposition_toasts(cls):
        """Reposition all visible toasts"""
        # This could be enhanced with smooth animations
        pass
