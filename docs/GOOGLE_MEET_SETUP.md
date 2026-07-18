# 📅 Google Meet & Calendar Integration Setup

## Overview
Sentinel AI now includes a **Meeting agent** that can create and manage Google Meet meetings directly through voice commands!

---

## 🎯 Features

The Meeting agent can:
- ✅ **Create instant meetings** - Start a Google Meet right now
- ✅ **Schedule future meetings** - Plan meetings with date/time
- ✅ **List upcoming meetings** - See what's on your calendar
- ✅ **Join meetings** - Open Google Meet links automatically
- ✅ **Cancel meetings** - Remove meetings from calendar
- ✅ **Send invites** - Add attendees and send calendar invites

---

## 🚀 Quick Setup (3 Steps)

### Step 1: Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Google Calendar API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Desktop app"
   - Download `credentials.json`

### Step 2: Add Credentials to Backend

Copy `credentials.json` to the Backend directory:

```bash
# Copy from Downloads to Backend
cp ~/Downloads/credentials.json "Sentinel-AI-Backend/credentials.json"
```

**Or manually:**
- Place `credentials.json` in: `Sentinel-AI-Backend/credentials.json`

### Step 3: First Run (OAuth Authorization)

The first time you use a Meeting command, it will:
1. Open a browser for Google authentication
2. Ask you to sign in with your Google account
3. Request Calendar permissions
4. Save `token.json` for future use

**That's it!** No more authentication needed afterward.

---

## 🎤 Voice Commands

### Create Instant Meeting
```
"Sentinel, create a quick meeting"
"Sentinel, start an instant meeting called Team Standup"
"Sentinel, create a 30-minute meeting"
```

### Schedule Future Meeting
```
"Sentinel, schedule a meeting tomorrow at 2 PM"
"Sentinel, schedule a meeting for 2025-12-01 at 14:30"
"Sentinel, schedule a meeting titled Sprint Planning on Friday at 10 AM"
```

### List Meetings
```
"Sentinel, show my upcoming meetings"
"Sentinel, what meetings do I have today?"
"Sentinel, list my next 5 meetings"
```

### Join Meeting
```
"Sentinel, join my next meeting"
"Sentinel, open my next meeting"
"Sentinel, join meeting with code abc-defg-hij"
```

### Cancel Meeting
```
"Sentinel, cancel my next meeting"
```

---

## 📋 Tool Details

### 1. `create_instant_meeting`
Creates a Google Meet meeting starting immediately.

**Parameters:**
- `title`: Meeting name (default: "Quick Meeting")
- `duration_minutes`: Duration in minutes (default: 60)

**Example:**
```python
create_instant_meeting(title="Team Standup", duration_minutes=30)
```

**Returns:**
- Meeting link
- Calendar event
- Opens meeting in browser

---

### 2. `schedule_meeting`
Schedules a future meeting with Google Meet.

**Parameters:**
- `title`: Meeting name (required)
- `start_datetime`: "YYYY-MM-DD HH:MM" format (required)
- `duration_minutes`: Duration (default: 60)
- `attendees`: Comma-separated emails (optional)
- `description`: Meeting details (optional)

**Example:**
```python
schedule_meeting(
    title="Sprint Planning",
    start_datetime="2025-12-01 14:30",
    duration_minutes=90,
    attendees="john@example.com, jane@example.com",
    description="Q4 planning session"
)
```

**Returns:**
- Google Meet link
- Calendar event link
- Sends invites to attendees

---

### 3. `list_upcoming_meetings`
Shows upcoming calendar events.

**Parameters:**
- `max_results`: Number of meetings (1-20, default: 5)

**Returns:**
- Meeting titles
- Start times
- Google Meet links
- Attendee counts

---

### 4. `get_next_meeting`
Gets and opens the next meeting.

**Returns:**
- Next meeting details
- Time until meeting
- Opens Google Meet link

---

### 5. `join_meeting_by_code`
Joins a meeting using its code.

**Parameters:**
- `meeting_code`: Meeting code (e.g., "abc-defg-hij")

**Example:**
```python
join_meeting_by_code("abc-defg-hij")
```

---

### 6. `cancel_next_meeting`
Cancels the next upcoming meeting.

**Returns:**
- Confirmation
- Sends cancellation notices

---

## 🔧 Technical Details

### Authentication Flow

1. **First Use:**
   ```
   User: "Sentinel, create a meeting"
   → Opens browser for Google OAuth
   → User signs in and grants permissions
   → Saves token.json
   → Creates meeting
   ```

2. **Subsequent Uses:**
   ```
   User: "Sentinel, create a meeting"
   → Loads token.json
   → Creates meeting immediately
   ```

### Token Management

- **credentials.json**: OAuth client secrets (from Google Console)
- **token.json**: User's access/refresh tokens (auto-generated)

**Token locations checked:**
1. `Sentinel-AI-Backend/token.json`
2. `Sentinel-AI-Frontend/token.json`

If Frontend already has `token.json`, the Backend will use it!

### Required Google API Scopes

```python
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]
```

---

## 🎯 Integration Architecture

```
┌─────────────────────┐
│   Voice Command     │
│ "Create a meeting"  │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│    Supervisor       │
│  Routes to Meeting  │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│   Meeting Agent     │
│   (6 tools)         │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│  Google Calendar    │
│       API           │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│   Google Meet       │
│   (Link Created)    │
└─────────────────────┘
```

---

## 🧪 Testing

### Test 1: Instant Meeting
```bash
python launcher.py
```

Say:
```
"Sentinel, create an instant meeting"
```

**Expected:**
- Browser opens with Google Meet
- Calendar event created
- Voice confirms meeting creation

### Test 2: Scheduled Meeting
```
"Sentinel, schedule a meeting for tomorrow at 3 PM"
```

**Expected:**
- Meeting added to calendar
- Google Meet link generated
- Voice confirms scheduling

### Test 3: List Meetings
```
"Sentinel, show my upcoming meetings"
```

**Expected:**
- Lists next 5 meetings
- Shows titles, times, and Meet links
- Voice reads them aloud

---

## 🔒 Security Notes

### OAuth Token Security

**credentials.json:**
- Contains OAuth client ID and secret
- Not user-specific
- Can be shared across installations
- **Add to .gitignore**

**token.json:**
- Contains user's access tokens
- User-specific and sensitive
- **Add to .gitignore**
- **NEVER commit to Git!**

### Recommended .gitignore

```gitignore
# OAuth credentials
credentials.json
token.json

# Environment variables
.env
```

---

## 📁 File Structure

```
Sentinel-AI-Backend/
├── credentials.json        # OAuth client secrets (from Google)
├── token.json             # User tokens (auto-generated)
├── src/
│   └── tools/
│       └── meeting_tools.py  # Google Meet integration
└── .env

Sentinel-AI-Frontend/
├── credentials.json        # Shared OAuth client (optional)
└── token.json             # Shared token (if already authenticated)
```

---

## ❓ Troubleshooting

### Error: "credentials.json not found"

**Solution:**
1. Download from Google Cloud Console
2. Place in `Sentinel-AI-Backend/credentials.json`

### Error: "Insufficient permission"

**Cause:** OAuth token has wrong scopes

**Solution:**
1. Delete `token.json`
2. Run Sentinel again
3. Re-authenticate with full permissions

### Error: "Access blocked: This app hasn't been verified"

**Solution:**
1. Click "Advanced"
2. Click "Go to [Your App] (unsafe)"
3. This is normal for development apps

### Browser doesn't open for OAuth

**Solution:**
1. Check firewall settings
2. Copy URL from console manually
3. Paste in browser

### Meeting link not generating

**Check:**
1. Google Calendar API is enabled
2. OAuth scopes include Calendar access
3. Internet connection is working

---

## 🎨 Customization

### Change Default Meeting Duration

Edit `meeting_tools.py`:

```python
@tool
def create_instant_meeting(title: str = "Quick Meeting", duration_minutes: int = 60):
    # Change default from 60 to your preferred duration
    pass
```

### Add More Meeting Features

Extend with:
- Meeting reminders
- Recurring meetings
- Custom meeting templates
- Integration with Zoom/Teams

---

## 📊 API Quotas

**Google Calendar API (Free Tier):**
- **10,000 requests/day**
- **200,000 requests/day** (with verification)

**Typical usage:**
- Create meeting: 1 request
- List meetings: 1 request
- ~1,000 meetings/day possible

---

## 🌟 Advanced Usage

### Schedule with Multiple Attendees

```python
schedule_meeting(
    title="Q4 Review",
    start_datetime="2025-12-15 10:00",
    duration_minutes=120,
    attendees="alice@company.com, bob@company.com, charlie@company.com",
    description="Quarterly business review and planning"
)
```

### Create Quick Team Standup

```python
create_instant_meeting(
    title="Daily Standup",
    duration_minutes=15
)
```

---

## 📝 Environment Variables (Optional)

Add to `.env` for customization:

```env
# Google OAuth (optional - uses credentials.json by default)
GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
GOOGLE_TOKEN_PATH=path/to/token.json
```

---

## ✅ Checklist

- [ ] Google Cloud project created
- [ ] Calendar API enabled
- [ ] OAuth credentials downloaded
- [ ] `credentials.json` in Backend folder
- [ ] Tested instant meeting creation
- [ ] Tested scheduled meeting
- [ ] Tested listing meetings

---

## 🎉 You're Done!

Now you can:
- ✅ Create meetings with voice
- ✅ Schedule meetings naturally
- ✅ Manage calendar through Sentinel
- ✅ Join meetings hands-free

**Try it:**
```
"Sentinel, create a quick meeting"
```

---

**Last Updated:** 2025-11-21
**Version:** 1.0
