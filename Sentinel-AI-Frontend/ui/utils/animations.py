"""
Modern UI Animations for Sentinel AI
Provides smooth transitions and micro-interactions
"""

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QSize, Qt, QTimer
from PyQt5.QtWidgets import QGraphicsOpacityEffect


class UIAnimations:
    """Collection of reusable UI animations"""

    @staticmethod
    def fade_in(widget, duration=300, start_opacity=0.0, end_opacity=1.0):
        """Fade in animation for widgets"""
        opacity_effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(opacity_effect)

        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(start_opacity)
        animation.setEndValue(end_opacity)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()

        # Store animation to prevent garbage collection
        widget._fade_animation = animation
        return animation

    @staticmethod
    def fade_out(widget, duration=300, callback=None):
        """Fade out animation for widgets"""
        opacity_effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(opacity_effect)

        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        widget._fade_animation = animation
        return animation

    @staticmethod
    def slide_in_from_top(widget, duration=400, distance=50):
        """Slide widget in from top"""
        start_pos = widget.pos()
        widget.move(start_pos.x(), start_pos.y() - distance)

        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(QPoint(start_pos.x(), start_pos.y() - distance))
        animation.setEndValue(start_pos)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()

        widget._slide_animation = animation
        return animation

    @staticmethod
    def slide_in_from_right(widget, duration=400, distance=50):
        """Slide widget in from right"""
        start_pos = widget.pos()
        widget.move(start_pos.x() + distance, start_pos.y())

        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(QPoint(start_pos.x() + distance, start_pos.y()))
        animation.setEndValue(start_pos)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()

        widget._slide_animation = animation
        return animation

    @staticmethod
    def bounce_effect(widget, duration=600):
        """Create a bounce effect on widget"""
        original_size = widget.size()

        # First expand
        expand_animation = QPropertyAnimation(widget, b"size")
        expand_animation.setDuration(duration // 2)
        expand_animation.setStartValue(original_size)
        expand_animation.setEndValue(QSize(int(original_size.width() * 1.05),
                                           int(original_size.height() * 1.05)))
        expand_animation.setEasingCurve(QEasingCurve.OutQuad)

        # Then contract back
        contract_animation = QPropertyAnimation(widget, b"size")
        contract_animation.setDuration(duration // 2)
        contract_animation.setStartValue(QSize(int(original_size.width() * 1.05),
                                               int(original_size.height() * 1.05)))
        contract_animation.setEndValue(original_size)
        contract_animation.setEasingCurve(QEasingCurve.InQuad)

        # Chain animations
        expand_animation.finished.connect(contract_animation.start)
        expand_animation.start()

        widget._bounce_animation = (expand_animation, contract_animation)
        return expand_animation

    @staticmethod
    def pulse_effect(widget, duration=1000, repeat=3):
        """Create a pulsing opacity effect"""
        opacity_effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(opacity_effect)

        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 0.5)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.setLoopCount(repeat)
        animation.start()

        widget._pulse_animation = animation
        return animation

    @staticmethod
    def shake_effect(widget, duration=500, intensity=10):
        """Shake widget horizontally (for errors)"""
        original_pos = widget.pos()

        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Create shake keyframes
        animation.setKeyValueAt(0, original_pos)
        animation.setKeyValueAt(0.1, QPoint(original_pos.x() + intensity, original_pos.y()))
        animation.setKeyValueAt(0.2, QPoint(original_pos.x() - intensity, original_pos.y()))
        animation.setKeyValueAt(0.3, QPoint(original_pos.x() + intensity, original_pos.y()))
        animation.setKeyValueAt(0.4, QPoint(original_pos.x() - intensity, original_pos.y()))
        animation.setKeyValueAt(0.5, QPoint(original_pos.x() + intensity//2, original_pos.y()))
        animation.setKeyValueAt(0.6, QPoint(original_pos.x() - intensity//2, original_pos.y()))
        animation.setKeyValueAt(0.7, QPoint(original_pos.x() + intensity//3, original_pos.y()))
        animation.setKeyValueAt(0.8, QPoint(original_pos.x() - intensity//3, original_pos.y()))
        animation.setKeyValueAt(1, original_pos)

        animation.start()
        widget._shake_animation = animation
        return animation


class HoverEffect:
    """Manage hover effects for widgets"""

    @staticmethod
    def install_button_hover(button, scale_factor=1.02):
        """Install hover scale effect on button"""
        original_size = button.size()

        def on_enter(event):
            if hasattr(button, '_hover_animation'):
                button._hover_animation.stop()

            animation = QPropertyAnimation(button, b"size")
            animation.setDuration(150)
            animation.setStartValue(button.size())
            animation.setEndValue(QSize(int(original_size.width() * scale_factor),
                                       int(original_size.height() * scale_factor)))
            animation.setEasingCurve(QEasingCurve.OutCubic)
            animation.start()
            button._hover_animation = animation

            # Call original event handler
            if hasattr(button, '_original_enter_event'):
                button._original_enter_event(event)

        def on_leave(event):
            if hasattr(button, '_hover_animation'):
                button._hover_animation.stop()

            animation = QPropertyAnimation(button, b"size")
            animation.setDuration(150)
            animation.setStartValue(button.size())
            animation.setEndValue(original_size)
            animation.setEasingCurve(QEasingCurve.OutCubic)
            animation.start()
            button._hover_animation = animation

            # Call original event handler
            if hasattr(button, '_original_leave_event'):
                button._original_leave_event(event)

        # Store original event handlers
        button._original_enter_event = button.enterEvent
        button._original_leave_event = button.leaveEvent

        # Override with new handlers
        button.enterEvent = on_enter
        button.leaveEvent = on_leave
