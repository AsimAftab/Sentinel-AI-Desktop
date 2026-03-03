# src/tools/meeting_tools.py

import os
import json
import webbrowser
import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional
from langchain_core.tools import tool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.token_manager import get_token_manager

from src.utils.log_config import configure_logging

configure_logging()
log = logging.getLogger("meeting")


def _get_local_tz() -> str:
    """Return the local timezone name string (e.g. 'America/New_York', 'EST', 'UTC+5')."""
    local_tz = datetime.now().astimezone().tzinfo
    return str(local_tz)


# Google Calendar and Meet API scopes
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_calendar_service(user_id: Optional[str] = None):
    """
    Authenticate and return Google Calendar API service.
    Uses TokenManager to retrieve credentials from database or file.

    Args:
        user_id: Optional user ID. If not provided, will try to auto-detect from user context.
    """
    log.info("Starting get_calendar_service with user_id=%s", user_id)

    try:
        log.info("Getting TokenManager instance")
        token_manager = get_token_manager()
        log.info("TokenManager obtained. MongoDB available: %s", token_manager.mongodb_available)

        # Get credentials using TokenManager
        log.info("Fetching calendar credentials for user_id=%s", user_id)
        creds = token_manager.get_calendar_credentials(user_id=user_id, scopes=SCOPES)

        if not creds:
            error_msg = (
                "❌ No valid Google Calendar credentials found!\n\n"
                "Please authenticate using the frontend:\n"
                "1. Login to Sentinel AI Frontend\n"
                "2. Click 'Connect' button for Google Meet\n"
                "3. Complete OAuth flow\n\n"
                "Or if using backend standalone:\n"
                "1. Run frontend and authenticate\n"
                "2. Token will be saved to database\n"
                "3. Backend will automatically use it"
            )
            log.error("No valid Google Calendar credentials found")
            raise ValueError(error_msg)

        log.info("Credentials obtained successfully")
        log.info("Credentials valid=%s, expired=%s, has_refresh_token=%s", creds.valid, creds.expired, bool(creds.refresh_token))

        # Build and return service
        log.info("Building Google Calendar API service")
        service = build("calendar", "v3", credentials=creds)
        log.info("Calendar service built successfully")
        return service

    except Exception as e:
        log.error("Error in get_calendar_service: %s: %s", type(e).__name__, e)
        log.error("Traceback:\n%s", traceback.format_exc())
        raise


@tool
def create_instant_meeting(
    title: str = "Quick Meeting",
    duration_minutes: int = 60,
    attendees: Optional[str] = None,
    description: Optional[str] = None,
    auto_open: bool = True,
) -> str:
    """
    Creates an instant Google Meet meeting starting now with enhanced controls.
    Returns the meeting link that can be joined immediately.

    Args:
        title: Meeting title/subject (default: "Quick Meeting")
        duration_minutes: Meeting duration in minutes (default: 60)
        attendees: Comma-separated email addresses to invite (optional)
        description: Meeting description/agenda (optional)
        auto_open: Auto-open meeting in browser (default: True)
    """
    try:
        log.info("Starting create_instant_meeting: title='%s', duration=%dmin", title, duration_minutes)

        log.info("Getting Calendar service")
        service = get_calendar_service()
        log.info("Calendar service obtained successfully")

        # Calculate start and end times
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(minutes=duration_minutes)
        log.info("Times calculated - Start: %s, End: %s", start_time, end_time)

        # Create event with Google Meet
        local_tz = _get_local_tz()
        event = {
            "summary": title,
            "description": description or "Instant meeting created by Sentinel AI",
            "start": {
                "dateTime": start_time.isoformat() + "Z",
                "timeZone": local_tz,
            },
            "end": {
                "dateTime": end_time.isoformat() + "Z",
                "timeZone": local_tz,
            },
            "conferenceData": {
                "createRequest": {
                    "requestId": f"sentinel-{int(start_time.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        # Add attendees if provided
        if attendees:
            attendee_list = [{"email": email.strip()} for email in attendees.split(",")]
            event["attendees"] = attendee_list
            log.info("Added %d attendee(s): %s", len(attendee_list), [a['email'] for a in attendee_list])

        log.info("Event object created")

        # Insert event with conference data
        log.info("Inserting event into Google Calendar")
        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all" if attendees else "none",  # Send invites if attendees
            )
            .execute()
        )
        log.info("Event created successfully. Event ID: %s", event.get('id'))
        log.debug("Full event response: %s", json.dumps(event, indent=2))

        # Extract meeting link
        meet_link = event.get("hangoutLink")
        log.info("Extracted meeting link: %s", meet_link)

        if meet_link:
            # Build response message
            result = f"✅ Created instant meeting: '{title}'\n"
            result += f"📅 Duration: {duration_minutes} minutes\n"
            result += f"🔗 Meeting link: {meet_link}\n"

            if attendees:
                attendee_count = len(attendees.split(","))
                result += f"👥 Invited: {attendee_count} attendee(s)\n"
                result += f"✉️ Calendar invites sent!\n"

            if description:
                result += f"📝 Agenda: {description[:50]}{'...' if len(description) > 50 else ''}\n"

            # Open meeting in browser if requested
            if auto_open:
                log.info("Opening meeting in browser")
                webbrowser.open(meet_link)
                result += "\n✨ Opening meeting in browser..."

            return result
        else:
            log.warning("No hangoutLink in event response")
            return f"✅ Created calendar event but Google Meet link generation failed. Please check your Google Calendar."

    except FileNotFoundError as e:
        log.error("FileNotFoundError: %s\n%s", e, traceback.format_exc())
        return f"❌ Credentials file not found. Please ensure credentials.json is in the Sentinel-AI-Frontend directory."
    except HttpError as e:
        log.error("Google API HttpError: %s\n%s", e, traceback.format_exc())
        details = e.error_details if hasattr(e, "error_details") else ""
        return f"❌ Google Calendar API error: {e}. {details}"
    except Exception as e:
        log.error("Unexpected error: %s: %s\n%s", type(e).__name__, e, traceback.format_exc())
        return f"❌ Error creating meeting: {e}"


@tool
def schedule_meeting(
    title: str,
    start_datetime: str,
    duration_minutes: int = 60,
    attendees: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """
    Schedules a Google Meet meeting for a future date/time.

    Args:
        title: Meeting title/subject
        start_datetime: Start date and time in format "YYYY-MM-DD HH:MM" (e.g., "2025-12-01 14:30")
        duration_minutes: Meeting duration in minutes (default 60)
        attendees: Comma-separated email addresses (optional)
        description: Meeting description (optional)
    """
    try:
        service = get_calendar_service()

        # Parse start datetime
        try:
            start_dt = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M")
        except ValueError:
            return "❌ Invalid date format. Use: YYYY-MM-DD HH:MM (e.g., '2025-12-01 14:30')"

        end_dt = start_dt + timedelta(minutes=duration_minutes)

        # Build event
        local_tz = _get_local_tz()
        event = {
            "summary": title,
            "description": description or f"Meeting scheduled by Sentinel AI",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": local_tz,
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": local_tz,
            },
            "conferenceData": {
                "createRequest": {
                    "requestId": f"sentinel-{int(start_dt.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        # Add attendees if provided
        if attendees:
            attendee_list = [{"email": email.strip()} for email in attendees.split(",")]
            event["attendees"] = attendee_list

        # Insert event
        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all" if attendees else "none",
            )
            .execute()
        )

        meet_link = event.get("hangoutLink")
        event_link = event.get("htmlLink")

        result = f"✅ Meeting scheduled!\n\n"
        result += f"📅 **{title}**\n"
        result += f"🕐 {start_datetime} (Duration: {duration_minutes} min)\n"

        if attendees:
            result += f"👥 Attendees: {attendees}\n"

        if meet_link:
            result += f"🔗 Google Meet: {meet_link}\n"

        if event_link:
            result += f"📆 Calendar: {event_link}\n"

        result += "\n✉️ Calendar invites sent!" if attendees else ""

        return result

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error scheduling meeting: {e}"


@tool
def list_upcoming_meetings(max_results: int = 5) -> str:
    """
    Lists upcoming meetings from Google Calendar.

    Args:
        max_results: Maximum number of meetings to return (1-20)
    """
    try:
        service = get_calendar_service()

        # Get current time
        now = datetime.now(timezone.utc).isoformat() + "Z"

        # Fetch upcoming events
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=min(max_results, 20),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return "📅 No upcoming meetings found in your calendar."

        result = f"📅 **Upcoming Meetings ({len(events)}):**\n\n"

        for i, event in enumerate(events, 1):
            summary = event.get("summary", "No Title")
            start = event["start"].get("dateTime", event["start"].get("date"))

            # Format datetime
            try:
                if "T" in start:
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    formatted_time = start
            except (ValueError, AttributeError):
                formatted_time = start

            result += f"{i}. **{summary}**\n"
            result += f"   🕐 {formatted_time}\n"

            # Add meeting link if available
            meet_link = event.get("hangoutLink")
            if meet_link:
                result += f"   🔗 {meet_link}\n"

            # Add attendees count
            attendees = event.get("attendees", [])
            if attendees:
                result += f"   👥 {len(attendees)} attendee(s)\n"

            result += "\n"

        return result

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error listing meetings: {e}"


@tool
def get_next_meeting() -> str:
    """
    Gets details about the next upcoming meeting and opens the Google Meet link.
    """
    try:
        service = get_calendar_service()

        # Get current time
        now = datetime.now(timezone.utc).isoformat() + "Z"

        # Fetch next event
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return "📅 No upcoming meetings found."

        event = events[0]
        summary = event.get("summary", "No Title")
        start = event["start"].get("dateTime", event["start"].get("date"))

        # Format datetime
        try:
            if "T" in start:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M")

                # Calculate time until meeting
                time_diff = dt - datetime.now(dt.tzinfo)
                minutes_until = int(time_diff.total_seconds() / 60)

                if minutes_until > 0:
                    time_info = f"Starts in {minutes_until} minutes"
                else:
                    time_info = "Happening now!"
            else:
                formatted_time = start
                time_info = "All-day event"
        except (ValueError, AttributeError):
            formatted_time = start
            time_info = ""

        result = f"📅 **Next Meeting:**\n\n"
        result += f"📌 {summary}\n"
        result += f"🕐 {formatted_time}"

        if time_info:
            result += f" ({time_info})"

        result += "\n"

        # Add attendees
        attendees = event.get("attendees", [])
        if attendees:
            result += f"👥 {len(attendees)} attendee(s)\n"

        # Open meeting link
        meet_link = event.get("hangoutLink")
        if meet_link:
            webbrowser.open(meet_link)
            result += f"🔗 Meeting link: {meet_link}\n\n✨ Opening Google Meet..."
        else:
            result += "\n⚠️ No Google Meet link found for this event."

        return result

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error getting next meeting: {e}"


@tool
def join_meeting_by_code(meeting_code: str) -> str:
    """
    Joins a Google Meet meeting using a meeting code.

    Args:
        meeting_code: Google Meet code (e.g., "abc-defg-hij")
    """
    try:
        # Clean up meeting code
        meeting_code = meeting_code.strip().lower()

        # Build Google Meet URL
        meet_url = f"https://meet.google.com/{meeting_code}"

        # Open in browser
        webbrowser.open(meet_url)

        return f"✅ Joining Google Meet: {meeting_code}\n🔗 {meet_url}\n\n✨ Opening in browser..."

    except Exception as e:
        return f"❌ Error joining meeting: {e}"


@tool
def preview_cancel_next_meeting() -> str:
    """
    Preview the next upcoming meeting that would be cancelled, WITHOUT deleting it.
    Use this to confirm with the user before actually cancelling.
    """
    try:
        service = get_calendar_service()

        # Get current time
        now = datetime.now(timezone.utc).isoformat() + "Z"

        # Fetch next event
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return "📅 No upcoming meetings to cancel."

        event = events[0]
        summary = event.get("summary", "No Title")
        event_id = event["id"]
        start = event["start"].get("dateTime", event["start"].get("date"))

        attendees = event.get("attendees", [])
        attendee_count = len(attendees)

        result = f"⚠️ **Meeting that would be cancelled:**\n\n"
        result += f"📌 Title: {summary}\n"
        result += f"🆔 Event ID: {event_id}\n"
        result += f"🕐 Start: {start}\n"
        if attendee_count:
            result += f"👥 {attendee_count} attendee(s) will be notified\n"
        result += f"\nTo confirm cancellation, use cancel_next_meeting(event_id=\"{event_id}\")."

        return result

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error previewing meeting: {e}"


@tool
def cancel_next_meeting(event_id: Optional[str] = None) -> str:
    """
    Cancels a meeting on the calendar. If event_id is provided, cancels that specific event.
    Otherwise cancels the next upcoming meeting.

    Args:
        event_id: Optional event ID of the meeting to cancel. If not provided, cancels the next upcoming meeting.
    """
    try:
        service = get_calendar_service()

        if event_id:
            # Cancel a specific event by ID
            try:
                event = service.events().get(calendarId="primary", eventId=event_id).execute()
                summary = event.get("summary", "No Title")
            except HttpError:
                return f"❌ Could not find meeting with ID: {event_id}"

            service.events().delete(
                calendarId="primary",
                eventId=event_id,
                sendUpdates="all",
            ).execute()

            return f"✅ Cancelled meeting: '{summary}'\n\n✉️ Cancellation notices sent to attendees."

        # No event_id provided — fetch the next upcoming event
        now = datetime.now(timezone.utc).isoformat() + "Z"

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        if not events:
            return "📅 No upcoming meetings to cancel."

        event = events[0]
        summary = event.get("summary", "No Title")
        target_event_id = event["id"]

        # Delete the event
        service.events().delete(
            calendarId="primary",
            eventId=target_event_id,
            sendUpdates="all",  # Notify attendees
        ).execute()

        return f"✅ Cancelled meeting: '{summary}'\n\n✉️ Cancellation notices sent to attendees."

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error cancelling meeting: {e}"


@tool
def create_quick_meeting_template(template_type: str, title: Optional[str] = None) -> str:
    """
    Create a meeting using a predefined template for common meeting types.

    Args:
        template_type: Type of meeting - options: "standup", "1on1", "brainstorm", "review", "demo"
        title: Optional custom title (will use template default if not provided)
    """
    templates = {
        "standup": {
            "title": "Daily Standup",
            "duration": 15,
            "description": "Quick team sync:\n- What did you do yesterday?\n- What are you doing today?\n- Any blockers?",
        },
        "1on1": {
            "title": "1-on-1 Meeting",
            "duration": 30,
            "description": "One-on-one discussion:\n- Updates and progress\n- Concerns and feedback\n- Career development",
        },
        "brainstorm": {
            "title": "Brainstorming Session",
            "duration": 45,
            "description": "Creative brainstorming:\n- Problem statement\n- Idea generation\n- Action items",
        },
        "review": {
            "title": "Code/Design Review",
            "duration": 30,
            "description": "Review session:\n- Overview of changes\n- Discussion and feedback\n- Approval and next steps",
        },
        "demo": {
            "title": "Product Demo",
            "duration": 30,
            "description": "Product demonstration:\n- Feature overview\n- Live demo\n- Q&A session",
        },
    }

    template_type = template_type.lower()
    if template_type not in templates:
        return f"❌ Unknown template type. Available templates: {', '.join(templates.keys())}"

    template = templates[template_type]
    meeting_title = title or template["title"]

    # Create instant meeting with template settings
    return create_instant_meeting(
        title=meeting_title,
        duration_minutes=template["duration"],
        description=template["description"],
    )


@tool
def update_meeting_details(
    meeting_id: str,
    new_title: Optional[str] = None,
    new_description: Optional[str] = None,
    add_attendees: Optional[str] = None,
) -> str:
    """
    Update an existing meeting's details.

    Args:
        meeting_id: The meeting/event ID to update
        new_title: New meeting title (optional)
        new_description: New description (optional)
        add_attendees: Comma-separated emails to add as attendees (optional)
    """
    try:
        service = get_calendar_service()

        # Get current event
        event = service.events().get(calendarId="primary", eventId=meeting_id).execute()

        # Update fields
        if new_title:
            event["summary"] = new_title

        if new_description:
            event["description"] = new_description

        if add_attendees:
            current_attendees = event.get("attendees", [])
            new_attendee_list = [{"email": email.strip()} for email in add_attendees.split(",")]
            event["attendees"] = current_attendees + new_attendee_list

        # Update the event
        updated_event = (
            service.events()
            .update(calendarId="primary", eventId=meeting_id, body=event, sendUpdates="all")
            .execute()
        )

        result = f"✅ Meeting updated!\n"
        result += f"📅 {updated_event.get('summary')}\n"

        if add_attendees:
            result += f"👥 Added {len(new_attendee_list)} new attendee(s)\n"

        meet_link = updated_event.get("hangoutLink")
        if meet_link:
            result += f"🔗 {meet_link}\n"

        return result

    except HttpError as e:
        log.error("HttpError updating meeting: %s\n%s", e, traceback.format_exc())
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        log.error("Error updating meeting: %s\n%s", e, traceback.format_exc())
        return f"❌ Error updating meeting: {e}"


@tool
def set_meeting_reminder(minutes_before: int = 10) -> str:
    """
    Set a default reminder for the next upcoming meeting.

    Args:
        minutes_before: Minutes before meeting to send reminder (default: 10)
    """
    try:
        service = get_calendar_service()

        # Get next meeting
        now = datetime.now(timezone.utc).isoformat() + "Z"
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        if not events:
            return "📅 No upcoming meetings to set reminder for."

        event = events[0]
        event_id = event["id"]
        title = event.get("summary", "Untitled")

        # Add reminder
        event["reminders"] = {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": minutes_before},
                {"method": "email", "minutes": minutes_before},
            ],
        }

        # Update event
        service.events().update(calendarId="primary", eventId=event_id, body=event).execute()

        return f"✅ Reminder set for '{title}'\n⏰ {minutes_before} minutes before meeting\n📧 Email + popup notification"

    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error setting reminder: {e}"


@tool
def get_meeting_details(meeting_id: str) -> str:
    """
    Get detailed information about a specific meeting.

    Args:
        meeting_id: The meeting/event ID
    """
    try:
        service = get_calendar_service()

        event = service.events().get(calendarId="primary", eventId=meeting_id).execute()

        result = f"📅 **Meeting Details:**\n\n"
        result += f"📌 Title: {event.get('summary', 'Untitled')}\n"

        # Times
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        result += f"🕐 Start: {start}\n"
        result += f"🕐 End: {end}\n"

        # Description
        if event.get("description"):
            result += f"\n📝 Description:\n{event['description']}\n"

        # Attendees
        attendees = event.get("attendees", [])
        if attendees:
            result += f"\n👥 Attendees ({len(attendees)}):\n"
            for attendee in attendees[:5]:  # Show first 5
                status = attendee.get("responseStatus", "unknown")
                result += f"  - {attendee['email']} ({status})\n"
            if len(attendees) > 5:
                result += f"  ... and {len(attendees) - 5} more\n"

        # Meeting link
        meet_link = event.get("hangoutLink")
        if meet_link:
            result += f"\n🔗 Meeting Link: {meet_link}\n"

        # Reminders
        reminders = event.get("reminders", {})
        if not reminders.get("useDefault") and reminders.get("overrides"):
            result += f"\n⏰ Reminders:\n"
            for reminder in reminders["overrides"]:
                result += f"  - {reminder['method']}: {reminder['minutes']} min before\n"

        return result

    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error getting meeting details: {e}"


# Meeting tools list - updated with new controls
meeting_tools = [
    create_instant_meeting,
    schedule_meeting,
    create_quick_meeting_template,
    list_upcoming_meetings,
    get_next_meeting,
    join_meeting_by_code,
    preview_cancel_next_meeting,
    cancel_next_meeting,
    update_meeting_details,
    set_meeting_reminder,
    get_meeting_details,
]
