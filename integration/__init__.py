"""
Integration layer for Sentinel AI project.
Provides event-based communication between frontend and backend.
"""

__version__ = "2.0.0"

# Export event bus components for easy importing
from .event_bus import EventBus, EventType, BackendStatus, Event

__all__ = ['EventBus', 'EventType', 'BackendStatus', 'Event']
