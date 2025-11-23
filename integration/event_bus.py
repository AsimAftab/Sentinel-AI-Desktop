"""
Event-based communication system for Frontend-Backend integration.
Replaces monkey patching with a clean, type-safe event system.
"""

from queue import Queue
from enum import Enum
from typing import Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import threading


class EventType(Enum):
    """Types of events emitted by backend and frontend."""
    # Backend lifecycle
    BACKEND_STARTING = "backend_starting"
    BACKEND_READY = "backend_ready"
    BACKEND_STOPPED = "backend_stopped"
    BACKEND_ERROR = "backend_error"

    # Voice assistant workflow
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING_FOR_COMMAND = "listening_for_command"
    COMMAND_RECEIVED = "command_received"
    PROCESSING_COMMAND = "processing_command"
    RESPONSE_GENERATED = "response_generated"

    # TTS events
    TTS_SPEAKING = "tts_speaking"
    TTS_FINISHED = "tts_finished"

    # Conversation events
    FOLLOW_UP_DETECTED = "follow_up_detected"
    CONVERSATION_ENDED = "conversation_ended"

    # Logging
    LOG_MESSAGE = "log_message"

    # Frontend to Backend
    SHUTDOWN_REQUEST = "shutdown_request"


class BackendStatus(Enum):
    """Backend operational status for UI display."""
    STARTING = "Starting..."
    READY = "Ready"
    LISTENING = "Listening for 'Sentinel'"
    WAKE_WORD_DETECTED = "Wake word detected"
    PROCESSING = "Processing command"
    SPEAKING = "Speaking response"
    ERROR = "Error"
    STOPPED = "Stopped"


@dataclass
class Event:
    """Event structure for inter-thread communication."""
    type: EventType
    status: Optional[BackendStatus] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """
    Thread-safe event bus for frontend-backend communication.
    Singleton pattern ensures single instance across all threads.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.frontend_queue = Queue()  # Backend -> Frontend events
        self.backend_queue = Queue()   # Frontend -> Backend events
        self._subscribers = {}  # Event type -> list of callback functions
        self._initialized = True

    def emit(self, event_type: EventType, status: Optional[BackendStatus] = None,
             data: Optional[Any] = None, error: Optional[str] = None):
        """
        Emit an event to the event bus.

        Args:
            event_type: Type of event
            status: Optional backend status
            data: Optional event data
            error: Optional error message
        """
        event = Event(
            type=event_type,
            status=status,
            data=data,
            error=error
        )

        # Send to frontend queue
        self.frontend_queue.put(event)

        # Notify subscribers
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"⚠️ Error in event subscriber: {e}")

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """
        Subscribe to a specific event type.

        Args:
            event_type: Type of event to listen for
            callback: Function to call when event occurs
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        """
        Unsubscribe from a specific event type.

        Args:
            event_type: Type of event
            callback: Callback function to remove
        """
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    def get_event(self, block=False, timeout=None) -> Optional[Event]:
        """
        Get next event from frontend queue (non-blocking by default).

        Args:
            block: Whether to block until event is available
            timeout: Timeout in seconds (only if blocking)

        Returns:
            Event object or None
        """
        try:
            return self.frontend_queue.get(block=block, timeout=timeout)
        except:
            return None

    def send_to_backend(self, event_type: EventType, data: Optional[Any] = None):
        """
        Send event from frontend to backend.

        Args:
            event_type: Type of event
            data: Optional event data
        """
        event = Event(type=event_type, data=data)
        self.backend_queue.put(event)

    def get_backend_event(self, block=False, timeout=None) -> Optional[Event]:
        """
        Get event from backend queue.

        Args:
            block: Whether to block until event is available
            timeout: Timeout in seconds

        Returns:
            Event object or None
        """
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

    def has_events(self) -> bool:
        """Check if there are pending frontend events."""
        return not self.frontend_queue.empty()


# Convenience function for backend usage
def get_event_bus() -> EventBus:
    """Get the singleton EventBus instance."""
    return EventBus()
