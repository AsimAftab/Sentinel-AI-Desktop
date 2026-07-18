# 📅 Google Meet Integration - Quick Start

## Setup in 3 Steps

### Step 1: Enable Google Calendar API (5 minutes)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project or select existing
3. Enable "Google Calendar API"
4. Create OAuth 2.0 credentials (Desktop app)
5. Download `credentials.json`

### Step 2: Add Credentials (30 seconds)
Place `credentials.json` in:
```
Sentinel-AI-Backend/credentials.json
```

### Step 3: First Run - Authenticate (1 minute)
```bash
python launcher.py
```

Say: **"Sentinel, create a meeting"**

- Browser opens for Google sign-in
- Grant Calendar permissions
- `token.json` saved automatically
- Meeting created!

---

## ✅ You're Done!

Now you can:

### Create Instant Meetings
```
"Sentinel, create a quick meeting"
"Sentinel, start a 30-minute meeting"
```

### Schedule Meetings
```
"Sentinel, schedule a meeting tomorrow at 2 PM"
"Sentinel, schedule Sprint Planning for Friday at 10 AM"
```

### List Meetings
```
"Sentinel, show my upcoming meetings"
"Sentinel, what meetings do I have today?"
```

### Join Meetings
```
"Sentinel, join my next meeting"
"Sentinel, open my next meeting"
```

---

## 🎯 Example Workflow

**Create instant meeting:**
```
You: "Sentinel, create a quick meeting"

Sentinel:
  🔊 "Created instant meeting: Quick Meeting
       Duration: 60 minutes
       Opening meeting in browser..."

  → Browser opens with Google Meet
  → Meeting link: https://meet.google.com/xxx-yyyy-zzz
```

**Schedule future meeting:**
```
You: "Sentinel, schedule a meeting tomorrow at 3 PM"

Sentinel:
  🔊 "Meeting scheduled!
       Team Meeting
       Tomorrow at 3:00 PM
       Google Meet link created"

  → Calendar event added
  → Meet link generated
```

---

## 📋 Quick Reference

| Voice Command | Action |
|--------------|--------|
| "create a meeting" | Instant Meet, starts now |
| "schedule a meeting" | Future meeting with date/time |
| "show meetings" | List upcoming events |
| "join next meeting" | Open next Meet link |
| "cancel next meeting" | Remove from calendar |

---

## 🔧 Troubleshooting

### "credentials.json not found"
→ Download from Google Console
→ Place in `Sentinel-AI-Backend/`

### OAuth browser doesn't open
→ Copy URL from console
→ Paste in browser manually

### "Insufficient permission"
→ Delete `token.json`
→ Re-run and re-authenticate

---

## 📚 Full Documentation

See `GOOGLE_MEET_SETUP.md` for:
- Detailed setup instructions
- All available commands
- Advanced features
- API customization

---

**Quick Links:**
- [Full Setup Guide](GOOGLE_MEET_SETUP.md)
- [Google Cloud Console](https://console.cloud.google.com/)
- [What's New](WHATS_NEW.md)

**Last Updated:** 2025-11-21
