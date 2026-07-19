"""Typed event schema shared by the WebSocket protocol and internal emitters."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Lifecycle
    READY = "ready"
    ERROR = "error"
    STATUS = "status"

    # Chat turn
    TURN_STARTED = "turn_started"
    ROUTING = "routing"
    AGENT_STARTED = "agent_started"
    AGENT_FINISHED = "agent_finished"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    TOKEN = "token"
    RESPONSE = "response"
    TURN_FINISHED = "turn_finished"

    # Proactive
    REMINDER = "reminder"

    # Voice (Phase 2)
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING = "listening"
    TRANSCRIBED = "transcribed"
    SPEAKING = "speaking"
    SPEECH_FINISHED = "speech_finished"


class Event(BaseModel):
    type: EventType
    session_id: str | None = None
    turn_id: str | None = None
    agent: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    ts: float = Field(default_factory=time.time)

    def to_wire(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)
