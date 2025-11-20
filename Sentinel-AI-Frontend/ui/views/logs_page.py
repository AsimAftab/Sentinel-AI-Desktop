"""
Logs page for displaying backend logs in real-time.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QFrame
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont, QTextCursor
import sys
import os
from pathlib import Path

# Add integration path BEFORE importing
integration_path = Path(__file__).parent.parent.parent.parent / "integration"
if str(integration_path) not in sys.path:
    sys.path.insert(0, str(integration_path))

from communication import CommunicationBus, MessageType


class LogsPage(QWidget):
    """Widget for displaying real-time backend logs."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.comm_bus = CommunicationBus()
        self.log_count = 0
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the logs page UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header section
        header_frame = QFrame()
        header_frame.setObjectName("logs_header")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 15, 20, 15)
        
        title = QLabel("📋 Backend Logs")
        title.setObjectName("logs_title")
        title.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #1f2937;
            margin-bottom: 5px;
        """)
        
        subtitle = QLabel("Real-time logs from the Sentinel AI backend")
        subtitle.setStyleSheet("""
            font-size: 13px;
            color: #6b7280;
        """)
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        self.clear_btn = QPushButton("🗑️ Clear Logs")
        self.clear_btn.setObjectName("clear_logs_btn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_logs)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        
        self.log_count_label = QLabel("Logs: 0")
        self.log_count_label.setStyleSheet("""
            font-size: 12px;
            color: #6b7280;
            padding: 8px 12px;
        """)
        
        controls_layout.addWidget(self.clear_btn)
        controls_layout.addWidget(self.log_count_label)
        controls_layout.addStretch()
        
        # Log display area
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setObjectName("log_display")
        
        # Use monospace font for logs
        log_font = QFont("Consolas", 9)
        if not log_font.exactMatch():
            log_font = QFont("Courier New", 9)
        self.log_display.setFont(log_font)
        
        self.log_display.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 12px;
                selection-background-color: #264f78;
            }
        """)
        
        # Add components to layout
        layout.addWidget(header_frame)
        layout.addLayout(controls_layout)
        layout.addWidget(self.log_display)
        
        # Start polling for logs
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_logs)
        self.timer.start(100)  # Poll every 100ms
        
    def update_logs(self):
        """Poll for new log messages from the backend."""
        new_logs = False
        messages_received = 0
        
        while True:
            msg = self.comm_bus.get_frontend_message()
            if not msg:
                break
                
            if msg.type == MessageType.LOG:
                # Append log to display
                self.log_display.append(msg.data)
                self.log_count += 1
                new_logs = True
                messages_received += 1
        
        if new_logs:
            # Auto-scroll to bottom
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_display.setTextCursor(cursor)
            
            # Update count label
            self.log_count_label.setText(f"Logs: {self.log_count}")
            
            # Debug output
            if messages_received > 0:
                print(f"[LogsPage] Received {messages_received} log messages (Total: {self.log_count})")
    
    def clear_logs(self):
        """Clear all logs from the display."""
        self.log_display.clear()
        self.log_count = 0
        self.log_count_label.setText("Logs: 0")
