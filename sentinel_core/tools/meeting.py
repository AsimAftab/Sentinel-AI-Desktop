"""Meeting tools — Google Meet + Calendar via the Google Calendar API.

Ported from the legacy meeting_tools.py. Times are handled in the user's local
timezone; errors are returned as short strings, never tracebacks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _service():
    """Build a Calendar API client (lazy — never at import time)."""
    from googleapiclient.discovery import build

    from sentinel_core.google_auth import get_credentials

    return build("calendar", "v3", credentials=get_credentials(SCOPES))


def _err(action: str, exc: Exception) -> str:
    """Short human-readable error string; full details go to the log only."""
    from googleapiclient.errors import HttpError

    logger.error("Meeting tool failed (%s): %s", action, exc, exc_info=True)
    if isinstance(exc, ValueError):  # setup instructions from google_auth
        return str(exc)
    if isinstance(exc, HttpError):
        return f"Google Calendar API error while trying to {action} (HTTP {exc.status_code})."
    return f"Could not {action}: {type(exc).__name__}: {exc}"


def _local_tz_name() -> str:
    return str(datetime.now().astimezone().tzinfo)


def _parse_attendees(attendees: str | None) -> list[dict] | None:
    if not attendees:
        return None
    emails = [e.strip() for e in attendees.split(",") if e.strip()]
    bad = [e for e in emails if "@" not in e]
    if bad:
        raise ValueError(f"Invalid attendee email address(es): {', '.join(bad)}")
    return [{"email": e} for e in emails]


def _insert_meet_event(
    title: str,
    start: datetime,
    duration_minutes: int,
    attendees: str | None,
    description: str | None,
) -> dict:
    attendee_list = _parse_attendees(attendees)
    end = start + timedelta(minutes=duration_minutes)
    tz = _local_tz_name()
    body: dict = {
        "summary": title,
        "description": description or "Meeting created by Sentinel AI",
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
        "conferenceData": {
            "createRequest": {
                "requestId": f"sentinel-{int(start.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if attendee_list:
        body["attendees"] = attendee_list
    return (
        _service()
        .events()
        .insert(
            calendarId="primary",
            body=body,
            conferenceDataVersion=1,
            sendUpdates="all" if attendee_list else "none",
        )
        .execute()
    )


def _format_event_time(event: dict) -> str:
    start = event.get("start", {})
    raw = start.get("dateTime") or start.get("date") or "?"
    try:
        if "T" in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone()
            return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        pass
    return raw


@tool
def create_instant_meeting(
    title: str = "Quick Meeting",
    duration_minutes: int = 60,
    attendees: str | None = None,
    description: str | None = None,
) -> str:
    """Create a Google Meet meeting starting now and return its join link.

    Args:
        title: Meeting title.
        duration_minutes: Duration in minutes (1-480).
        attendees: Optional comma-separated attendee email addresses (invites are sent).
        description: Optional meeting description or agenda.
    """
    try:
        if not 1 <= duration_minutes <= 480:
            return "Duration must be between 1 and 480 minutes."
        event = _insert_meet_event(
            title, datetime.now().astimezone(), duration_minutes, attendees, description
        )
        link = event.get("hangoutLink")
        if not link:
            return "Calendar event created, but no Google Meet link was generated."
        lines = [f"Created instant meeting '{title}' ({duration_minutes} min).", f"Link: {link}"]
        if attendees:
            lines.append(f"Invites sent to: {attendees}")
        return "\n".join(lines)
    except Exception as exc:
        return _err("create the meeting", exc)


@tool
def schedule_meeting(
    title: str,
    start_datetime: str,
    duration_minutes: int = 60,
    attendees: str | None = None,
    description: str | None = None,
) -> str:
    """Schedule a Google Meet meeting for a future date/time (user's local timezone).

    Args:
        title: Meeting title.
        start_datetime: Local start time as "YYYY-MM-DD HH:MM" (e.g. "2026-08-01 14:30").
        duration_minutes: Duration in minutes (1-480).
        attendees: Optional comma-separated attendee email addresses (invites are sent).
        description: Optional meeting description or agenda.
    """
    try:
        if not title.strip():
            return "Meeting title must not be empty."
        if not 1 <= duration_minutes <= 480:
            return "Duration must be between 1 and 480 minutes."
        try:
            start = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").astimezone()
        except ValueError:
            return "Invalid date format. Use: YYYY-MM-DD HH:MM (e.g. '2026-08-01 14:30')."
        if start < datetime.now().astimezone():
            return f"Start time {start_datetime} is in the past. Use a future date/time."
        event = _insert_meet_event(title, start, duration_minutes, attendees, description)
        lines = [
            f"Scheduled '{title}' for {start_datetime} ({duration_minutes} min, "
            f"{_local_tz_name()})."
        ]
        if link := event.get("hangoutLink"):
            lines.append(f"Meet link: {link}")
        if attendees:
            lines.append(f"Invites sent to: {attendees}")
        return "\n".join(lines)
    except Exception as exc:
        return _err("schedule the meeting", exc)


@tool
def list_upcoming_meetings(max_results: int = 5) -> str:
    """List upcoming events from the user's primary Google Calendar.

    Args:
        max_results: Maximum number of events to return (1-20).
    """
    try:
        max_results = max(1, min(20, max_results))
        events = (
            _service()
            .events()
            .list(
                calendarId="primary",
                timeMin=datetime.now().astimezone().isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )
        if not events:
            return "No upcoming meetings found in your calendar."
        lines = [f"Upcoming meetings ({len(events)}):"]
        for i, event in enumerate(events, 1):
            lines.append(f"{i}. {event.get('summary', 'No title')} — {_format_event_time(event)}")
            lines.append(f"   id: {event['id']}")
            if link := event.get("hangoutLink"):
                lines.append(f"   link: {link}")
            if n := len(event.get("attendees", [])):
                lines.append(f"   attendees: {n}")
        return "\n".join(lines)
    except Exception as exc:
        return _err("list upcoming meetings", exc)


@tool
def cancel_meeting(event_id: str) -> str:
    """Cancel (delete) a calendar meeting by its event id; attendees are notified.

    Get the event id from list_upcoming_meetings first, and confirm with the
    user before cancelling.

    Args:
        event_id: The calendar event id to cancel.
    """
    try:
        if not event_id.strip():
            return "An event id is required. Use list_upcoming_meetings to find it."
        service = _service()
        try:
            event = service.events().get(calendarId="primary", eventId=event_id).execute()
        except Exception:
            return f"No meeting found with id '{event_id}'. Use list_upcoming_meetings."
        service.events().delete(calendarId="primary", eventId=event_id, sendUpdates="all").execute()
        return (
            f"Cancelled meeting '{event.get('summary', 'No title')}'. "
            "Cancellation notices were sent to attendees."
        )
    except Exception as exc:
        return _err("cancel the meeting", exc)


@tool
def get_meeting_link(event_id: str | None = None) -> str:
    """Get the Google Meet join link for a meeting (next upcoming one by default).

    Args:
        event_id: Optional calendar event id. If omitted, uses the next upcoming meeting.
    """
    try:
        service = _service()
        if event_id:
            try:
                event = service.events().get(calendarId="primary", eventId=event_id).execute()
            except Exception:
                return f"No meeting found with id '{event_id}'. Use list_upcoming_meetings."
        else:
            events = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=datetime.now().astimezone().isoformat(),
                    maxResults=1,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
                .get("items", [])
            )
            if not events:
                return "No upcoming meetings found."
            event = events[0]
        title = event.get("summary", "No title")
        when = _format_event_time(event)
        if link := event.get("hangoutLink"):
            return f"'{title}' at {when}\nMeet link: {link}"
        return f"'{title}' at {when} has no Google Meet link."
    except Exception as exc:
        return _err("get the meeting link", exc)


TOOLS = [
    create_instant_meeting,
    schedule_meeting,
    list_upcoming_meetings,
    cancel_meeting,
    get_meeting_link,
]
