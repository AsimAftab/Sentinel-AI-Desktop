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
def create_routine(name: str, time_hhmm: str, prompt: str, days: str = "daily") -> str:
    """Create (or update) a recurring routine: at the given time, Sentinel runs
    the prompt through its agents and announces the result (toast + spoken).

    Args:
        name: short handle, e.g. "morning brief".
        time_hhmm: 24h local time, e.g. "09:00".
        prompt: what Sentinel should do, e.g. "Summarize today's weather in
            Mumbai and my next calendar events".
        days: "daily" or comma-separated weekdays like "mon,tue,wed,thu,fri".
    """
    import re

    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time_hhmm):
        return f"Invalid time {time_hhmm!r} — use 24h HH:MM like 09:00 or 17:30."
    _get_store().add_routine(name.strip(), time_hhmm, prompt.strip(), days.strip().lower())
    return f'Routine "{name}" will run {days} at {time_hhmm}.'


@tool
def list_routines() -> str:
    """List all recurring routines with their schedule and prompt."""
    routines = _get_store().list_routines()
    if not routines:
        return "No routines set up."
    return "\n".join(
        f'"{r["name"]}" — {r["days"]} at {r["time_hhmm"]}'
        f'{"" if r["enabled"] else " (disabled)"}: {r["prompt"][:80]}'
        for r in routines
    )


@tool
def delete_routine(name: str) -> str:
    """Delete a recurring routine by name."""
    if _get_store().delete_routine(name.strip()):
        return f'Routine "{name}" deleted.'
    return f'No routine named "{name}" found.'


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


TOOLS = [
    set_reminder,
    set_timer,
    list_reminders,
    cancel_reminder,
    create_routine,
    list_routines,
    delete_routine,
]
