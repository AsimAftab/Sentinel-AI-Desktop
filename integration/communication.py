"""
Thread-safe communication layer between frontend and backend.
"""

from queue import Queue
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime


class MessageType(Enum):
    """Types of messages exchanged between threads."""
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    WAKE_WORD_DETECTED = "wake_word_detected"
    COMMAND_RECEIVED = "command_received"
    RESPONSE_GENERATED = "response_generated"
    BACKEND_READY = "backend_ready"
    BACKEND_STOPPING = "backend_stopping"
    SHUTDOWN_REQUEST = "shutdown_request"
    LOG = "log"  # For streaming backend logs to frontend


class BackendStatus(Enum):
    """Backend operational status."""
    STARTING = "Starting..."
    READY = "Ready"
    LISTENING = "Listening for wake word"
    PROCESSING = "Processing command"
    ERROR = "Error"
    STOPPED = "Stopped"


@dataclass
class Message:
    """Message structure for inter-thread communication."""
    type: MessageType
    status: Optional[BackendStatus] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class CommunicationBus:
    """Singleton communication bus for thread-safe messaging."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.frontend_queue = Queue()  # Backend -> Frontend messages
        self.backend_queue = Queue()   # Frontend -> Backend messages
        self._initialized = True

    def send_to_frontend(self, message: Message):
        """Send message from backend to frontend."""
        self.frontend_queue.put(message)

    def send_to_backend(self, message: Message):
        """Send message from frontend to backend."""
        self.backend_queue.put(message)

    def get_frontend_message(self, block=False, timeout=None):
        """Get message for frontend (non-blocking by default)."""
        try:
            return self.frontend_queue.get(block=block, timeout=timeout)
        except:
            return None

    def get_backend_message(self, block=False, timeout=None):
        """Get message for backend (non-blocking by default)."""
        try:
            return self.backend_queue.get(block=block, timeout=timeout)
        except:
            return None

    def clear(self):
        """Clear all queues."""
        while not self.frontend_queue.empty():
            try:
                self.frontend_queue.get_nowait()
            except:
                break
        while not self.backend_queue.empty():
            try:
                self.backend_queue.get_nowait()
            except:
                break
