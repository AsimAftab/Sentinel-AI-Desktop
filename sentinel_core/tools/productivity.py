"""Productivity tools: reminders and timers, persisted in SQLite.

The scheduler in app.py fires due reminders as spoken alerts + Windows toasts.
Times arrive as ISO strings — the agent converts natural language ("in 20
minutes", "tomorrow 9am") using the current date/time from its prompt.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from langchain_core.tools import tool

from ..store import Store

logger = logging.getLogger(__name__)

_store: Store | None = None


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%a %b %d, %I:%M %p")


@tool
def set_reminder(text: str, due_iso: str) -> str:
    """Schedule a reminder that will be spoken and shown as a notification.

    Args:
        text: what to remind about, phrased for the user (e.g. "Call mom").
        due_iso: local date-time in ISO format, e.g. "2026-07-19T17:00:00".
            Compute it from the current date/time in your instructions.
    """
    try:
        due = datetime.fromisoformat(due_iso)
    except ValueError:
        return f"Invalid date-time: {due_iso!r}. Use ISO format like 2026-07-19T17:00:00."
    if due <= datetime.now():
        return f"That time ({_fmt(due.timestamp())}) is in the past."
    reminder_id = _get_store().add_reminder(text, due.timestamp())
    return f"Reminder #{reminder_id} set for {_fmt(due.timestamp())}: {text}"


@tool
def set_timer(minutes: float, label: str = "Timer") -> str:
    """Start a countdown timer (an alarm after N minutes).

    Args:
        minutes: duration in minutes (e.g. 10, 0.5 for 30 seconds).
        label: what the timer is for, e.g. "Pasta".
    """
    if not 0 < minutes <= 24 * 60:
        return "Timer must be between a few seconds and 24 hours."
    due = datetime.now() + timedelta(minutes=minutes)
    reminder_id = _get_store().add_reminder(f"{label} — time's up!", due.timestamp())
    return f"Timer #{reminder_id} ({label}) set for {minutes:g} minutes from now."


@tool
def list_reminders() -> str:
    """List all pending reminders and timers with their ids and due times."""
    pending = _get_store().pending_reminders()
    if not pending:
        return "No pending reminders."
    return "\n".join(f"#{r['id']} — {_fmt(r['due_at'])}: {r['text']}" for r in pending)


@tool
def cancel_reminder(reminder_id: int) -> str:
    """Cancel a pending reminder or timer by its id (list them first if unsure)."""
    if _get_store().cancel_reminder(reminder_id):
        return f"Reminder #{reminder_id} cancelled."
    return f"No pending reminder #{reminder_id} found."


TOOLS = [set_reminder, set_timer, list_reminders, cancel_reminder]
