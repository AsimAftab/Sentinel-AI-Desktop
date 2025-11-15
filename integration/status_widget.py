"""
Status widget for displaying backend status in the frontend.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from .communication import CommunicationBus, MessageType, BackendStatus


class BackendStatusWidget(QWidget):
    """
    Widget that displays backend status and can be added to the frontend dashboard.
    """

    backend_error_signal = pyqtSignal(str)  # Signal for error notifications

    def __init__(self, parent=None):
        super().__init__(parent)
        self.comm_bus = CommunicationBus()
        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        """Setup the status widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container frame - professional spacious style
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 rgba(79, 70, 229, 0.1), stop:1 rgba(124, 58, 237, 0.1));
                border: 2px solid rgba(79, 70, 229, 0.3);
                border-radius: 12px;
                padding: 16px 20px;
            }
        """)
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(16, 12, 16, 12)
        frame_layout.setSpacing(16)

        # Status indicator (larger)
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: gray; font-size: 24px; border: none;")
        frame_layout.addWidget(self.status_indicator)

        # Status text container
        text_container = QVBoxLayout()
        text_container.setSpacing(4)

        # Title (larger, more prominent)
        title = QLabel("Voice Assistant")
        title.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                border: none;
            }
        """)
        text_container.addWidget(title)

        # Status label (larger font)
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                border: none;
            }
        """)
        text_container.addWidget(self.status_label)

        frame_layout.addLayout(text_container)
        frame_layout.addStretch()

        # Activity label (larger, more readable)
        self.activity_label = QLabel("")
        self.activity_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.activity_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 11px;
                font-style: italic;
                border: none;
            }
        """)
        frame_layout.addWidget(self.activity_label)

        layout.addWidget(frame)

        # Set minimum and maximum height for better appearance
        self.setMinimumHeight(85)
        self.setMaximumHeight(100)

    def setup_timer(self):
        """Setup timer to poll for messages from backend."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_messages)
        self.timer.start(100)  # Check every 100ms

    def check_messages(self):
        """Check for new messages from backend thread."""
        while True:
            message = self.comm_bus.get_frontend_message(block=False)
            if message is None:
                break

            self.handle_message(message)

    def handle_message(self, message):
        """Handle incoming message from backend."""
        if message.type == MessageType.STATUS_UPDATE and message.status:
            self.update_status(message.status)

        elif message.type == MessageType.WAKE_WORD_DETECTED:
            self.update_activity("Wake word detected!")

        elif message.type == MessageType.COMMAND_RECEIVED:
            command = message.data or "Unknown"
            self.update_activity(f"Command: {command}")

        elif message.type == MessageType.RESPONSE_GENERATED:
            response = message.data or "Response generated"
            # Truncate long responses
            if len(str(response)) > 100:
                response = str(response)[:100] + "..."
            self.update_activity(f"Response: {response}")

        elif message.type == MessageType.ERROR:
            error_msg = message.error or "Unknown error"
            self.update_status(BackendStatus.ERROR)
            self.update_activity(f"Error: {error_msg}")
            self.backend_error_signal.emit(error_msg)

    def update_status(self, status: BackendStatus):
        """Update status display."""
        self.status_label.setText(status.value)

        # Update indicator color based on status
        color_map = {
            BackendStatus.STARTING: "#FFA500",  # Orange
            BackendStatus.READY: "#00FF00",     # Green
            BackendStatus.LISTENING: "#00FF00", # Green
            BackendStatus.PROCESSING: "#FFFF00",# Yellow
            BackendStatus.ERROR: "#FF0000",     # Red
            BackendStatus.STOPPED: "#808080",   # Gray
        }

        color = color_map.get(status, "#808080")
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 20px; border: none;")

    def update_activity(self, text: str):
        """Update activity log - compact format."""
        # Keep only the most relevant part, truncate if needed
        if len(text) > 40:
            text = text[:37] + "..."
        self.activity_label.setText(text)
