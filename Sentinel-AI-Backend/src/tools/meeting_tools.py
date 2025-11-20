# src/tools/meeting_tools.py

import os
import json
import webbrowser
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Calendar and Meet API scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

# Paths for credentials and token
# Look in both Backend and Frontend directories
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), 'Sentinel-AI-Frontend')

CREDENTIALS_PATH = None
TOKEN_PATH = None

# Check for credentials.json in multiple locations
for path in [
    os.path.join(BACKEND_DIR, 'credentials.json'),
    os.path.join(FRONTEND_DIR, 'credentials.json'),
]:
    if os.path.exists(path):
        CREDENTIALS_PATH = path
        break

# Check for token.json in multiple locations
for path in [
    os.path.join(BACKEND_DIR, 'token.json'),
    os.path.join(FRONTEND_DIR, 'token.json'),
]:
    if os.path.exists(path):
        TOKEN_PATH = path
        break

# Default paths if not found
if not CREDENTIALS_PATH:
    CREDENTIALS_PATH = os.path.join(BACKEND_DIR, 'credentials.json')
if not TOKEN_PATH:
    TOKEN_PATH = os.path.join(BACKEND_DIR, 'token.json')


def get_calendar_service():
    """
    Authenticate and return Google Calendar API service.
    Handles OAuth flow if needed.
    """
    creds = None

    # Load token if it exists
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"⚠️ Corrupted token file, will re-authenticate. Error: {e}")
            creds = None

    # Refresh or run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token
                with open(TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"⚠️ Token refresh failed: {e}. Running OAuth flow...")
                creds = None

        if not creds:
            # Run full OAuth flow
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"❌ Google OAuth credentials not found!\n\n"
                    f"Expected: {CREDENTIALS_PATH}\n\n"
                    f"Please:\n"
                    f"1. Go to https://console.cloud.google.com/\n"
                    f"2. Create OAuth 2.0 credentials\n"
                    f"3. Download credentials.json\n"
                    f"4. Place in: Sentinel-AI-Backend/credentials.json"
                )

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)

            # Save token
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())

    # Build and return service
    service = build('calendar', 'v3', credentials=creds)
    return service


@tool
def create_instant_meeting(title: str = "Quick Meeting", duration_minutes: int = 60) -> str:
    """
    Creates an instant Google Meet meeting starting now.
    Returns the meeting link that can be joined immediately.

    Args:
        title: Meeting title/subject
        duration_minutes: Meeting duration in minutes (default 60)
    """
    try:
        service = get_calendar_service()

        # Calculate start and end times
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(minutes=duration_minutes)

        # Create event with Google Meet
        event = {
            'summary': title,
            'description': f'Instant meeting created by Sentinel AI',
            'start': {
                'dateTime': start_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f'sentinel-{int(start_time.timestamp())}',
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            },
        }

        # Insert event with conference data
        event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()

        # Extract meeting link
        meet_link = event.get('hangoutLink')

        if meet_link:
            # Open meeting in browser
            webbrowser.open(meet_link)

            return f"✅ Created instant meeting: '{title}'\n📅 Duration: {duration_minutes} minutes\n🔗 Meeting link: {meet_link}\n\n✨ Opening meeting in browser..."
        else:
            return f"✅ Created calendar event but Google Meet link generation failed. Please check your Google Calendar."

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error creating meeting: {e}"


@tool
def schedule_meeting(
    title: str,
    start_datetime: str,
    duration_minutes: int = 60,
    attendees: Optional[str] = None,
    description: Optional[str] = None
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
        event = {
            'summary': title,
            'description': description or f'Meeting scheduled by Sentinel AI',
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f'sentinel-{int(start_dt.timestamp())}',
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            },
        }

        # Add attendees if provided
        if attendees:
            attendee_list = [{'email': email.strip()} for email in attendees.split(',')]
            event['attendees'] = attendee_list

        # Insert event
        event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1,
            sendUpdates='all' if attendees else 'none'
        ).execute()

        meet_link = event.get('hangoutLink')
        event_link = event.get('htmlLink')

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
        now = datetime.utcnow().isoformat() + 'Z'

        # Fetch upcoming events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=min(max_results, 20),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return "📅 No upcoming meetings found in your calendar."

        result = f"📅 **Upcoming Meetings ({len(events)}):**\n\n"

        for i, event in enumerate(events, 1):
            summary = event.get('summary', 'No Title')
            start = event['start'].get('dateTime', event['start'].get('date'))

            # Format datetime
            try:
                if 'T' in start:
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_time = start
            except:
                formatted_time = start

            result += f"{i}. **{summary}**\n"
            result += f"   🕐 {formatted_time}\n"

            # Add meeting link if available
            meet_link = event.get('hangoutLink')
            if meet_link:
                result += f"   🔗 {meet_link}\n"

            # Add attendees count
            attendees = event.get('attendees', [])
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
        now = datetime.utcnow().isoformat() + 'Z'

        # Fetch next event
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=1,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return "📅 No upcoming meetings found."

        event = events[0]
        summary = event.get('summary', 'No Title')
        start = event['start'].get('dateTime', event['start'].get('date'))

        # Format datetime
        try:
            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M')

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
        except:
            formatted_time = start
            time_info = ""

        result = f"📅 **Next Meeting:**\n\n"
        result += f"📌 {summary}\n"
        result += f"🕐 {formatted_time}"

        if time_info:
            result += f" ({time_info})"

        result += "\n"

        # Add attendees
        attendees = event.get('attendees', [])
        if attendees:
            result += f"👥 {len(attendees)} attendee(s)\n"

        # Open meeting link
        meet_link = event.get('hangoutLink')
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
def cancel_next_meeting() -> str:
    """
    Cancels the next upcoming meeting on the calendar.
    """
    try:
        service = get_calendar_service()

        # Get current time
        now = datetime.utcnow().isoformat() + 'Z'

        # Fetch next event
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=1,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return "📅 No upcoming meetings to cancel."

        event = events[0]
        summary = event.get('summary', 'No Title')
        event_id = event['id']

        # Delete the event
        service.events().delete(
            calendarId='primary',
            eventId=event_id,
            sendUpdates='all'  # Notify attendees
        ).execute()

        return f"✅ Cancelled meeting: '{summary}'\n\n✉️ Cancellation notices sent to attendees."

    except FileNotFoundError as e:
        return str(e)
    except HttpError as e:
        return f"❌ Google Calendar API error: {e}"
    except Exception as e:
        return f"❌ Error cancelling meeting: {e}"


# Meeting tools list
meeting_tools = [
    create_instant_meeting,
    schedule_meeting,
    list_upcoming_meetings,
    get_next_meeting,
    join_meeting_by_code,
    cancel_next_meeting
]
