# Sentinel AI - Voice Commands Guide

## Quick Start

1. **Wake Sentinel**: Say **"Sentinel"** (wait for confirmation beep)
2. **Give Command**: Speak your command naturally
3. **Listen**: Sentinel will respond and perform the action

---

## Table of Contents
- [Web & Search Commands](#web--search-commands)
- [Weather & News Commands](#weather--news-commands)
- [Translation & Utility Commands](#translation--utility-commands)
- [Music Commands (Spotify)](#music-commands-spotify)
- [Music Commands (YouTube)](#music-commands-youtube)
- [Music Discovery & Moods](#music-discovery--moods)
- [Lyrics Commands](#lyrics-commands)
- [Meeting & Calendar Commands](#meeting--calendar-commands)
- [Pro Tips](#pro-tips)

---

## Web & Search Commands

### Web Search
```
"Search for Python tutorials"
"Look up machine learning news"
"Find restaurants near me"
"Search the web for best smartphones 2025"
```

### Open Websites
```
"Open YouTube"
"Open github.com in the browser"
"Go to reddit.com"
"Launch twitter.com"
```

### Search and Open
```
"Search for flights to Tokyo and open the first link"
"Look up weather forecast and open the result"
"Find the nearest coffee shop and open it"
```

### Web Scraping
```
"Extract text from https://example.com/article"
"Scrape the content from this webpage"
"Get all the text from that Wikipedia article"
```

### Get Links from Page
```
"Get all links from bbc.com"
"Show me links on the homepage of github.com"
"Extract links from this website"
```

### Download Files
```
"Download the PDF from that link"
"Download https://example.com/file.pdf as research.pdf"
"Save this file to my computer"
```

### Website Status
```
"Check if google.com is online"
"Is facebook.com working?"
"Test website status for amazon.com"
```

### URL Shortening
```
"Shorten this URL: https://example.com/very/long/path"
"Create a short link for this website"
"Make this URL shorter"
```

---

## Weather & News Commands

### Current Weather
```
"What's the weather in London?"
"Get current weather for New York"
"How's the weather in Tokyo right now?"
"Weather in my location"
```

### Weather Forecast
```
"Get 3-day weather forecast for Seattle"
"What's the weather forecast for Paris?"
"Show me the 5-day forecast for Los Angeles"
```

### Latest News
```
"Get latest news"
"Show me news about artificial intelligence"
"What's happening in technology today?"
"Latest news on climate change"
"Give me tech news headlines"
```

---

## Translation & Utility Commands

### Translation
```
"Translate 'Hello, how are you?' to Spanish"
"Translate 'Good morning' to French"
"How do you say 'Thank you' in Japanese?"
"Convert this text to German: I love programming"
```

**Supported Languages**: English (en), Spanish (es), French (fr), German (de), Italian (it), Portuguese (pt), Japanese (ja), Chinese (zh), Korean (ko), Russian (ru), Arabic (ar), Hindi (hi)

### Currency Conversion
```
"Convert 100 USD to EUR"
"How much is 50 GBP in USD?"
"Exchange rate for 1000 JPY to USD"
"Convert 500 dollars to pounds"
```

### Word Definitions
```
"What's the definition of serendipity?"
"Define 'ephemeral'"
"Tell me what 'paradigm' means"
"Look up the word 'ubiquitous'"
```

---

## Music Commands (Spotify)

> **Requirements**: Spotify Premium account, Spotify app running on a device

### Play Songs
```
"Play Blinding Lights by The Weeknd"
"Play some jazz music"
"Play Shape of You"
"Play Ed Sheeran's Perfect"
"Play Bohemian Rhapsody by Queen"
```

### Playback Control
```
"Pause the music"
"Resume music"
"Play"
"Pause"
"Next song"
"Skip to the next song"
"Previous song"
"Go back to the previous song"
```

### Volume Control
```
"Set volume to 50%"
"Turn volume up to 80"
"Set volume to maximum"
"Lower volume to 30%"
```

### Current Song Info
```
"What song is playing?"
"What's currently playing?"
"Tell me about this song"
"Song information"
```

---

## Music Commands (YouTube)

### Auto-Play (Recommended)
```
"Play Hotel California on YouTube"
"Auto-play Shape of You on YouTube Music"
"Play Levitating on YouTube Music"
"Play Stairway to Heaven on YouTube"
```

### Search (Manual)
```
"Search for Imagine Dragons on YouTube"
"Look up Coldplay music videos"
"Find acoustic versions on YouTube Music"
```

### Smart Platform Selection
```
"Play some classical music on any platform"
"Play Despacito anywhere"
"Play jazz music"
```
*Tries Spotify first, falls back to YouTube if needed*

### YouTube Music Specific
```
"Open YouTube Music"
"Search for David Bowie albums on YouTube Music"
"Play the 80s hits playlist"
"Open my YouTube Music library"
```

### Radio Stations
```
"Create a radio station based on The Beatles"
"Start a station like Pink Floyd"
"Make a radio from this song"
```

### Playback Control (Playwright)
```
"Pause YouTube Music"
"Skip to next song on YouTube"
"Go to previous track"
"Like this song"
"Dislike this song"
```

### Close Browser
```
"Close the music browser"
"Stop the music and close browser"
```

---

## Music Discovery & Moods

### Genre Playlists
```
"Play a jazz playlist"
"Play rock music"
"Play classical music"
"Play hip hop playlist"
"Play electronic music"
"Play pop music"
"Play country music"
```

**Supported Genres**: jazz, rock, classical, pop, hip hop, electronic, country, r&b, blues, reggae, metal, folk, punk, indie, soul, funk

### Mood-Based Music
```
"Play relaxing music"
"Play workout music"
"Play focus music"
"Play party music"
"Play sleep music"
"Play study music"
"Play happy music"
"Play sad music"
"Play romantic music"
"Play energetic music"
```

**Supported Moods**: relaxing, workout, focus, party, sleep, study, happy, sad, romantic, energetic, chill, upbeat, calm, intense, mellow

### Music Discovery
```
"Discover music similar to Pink Floyd"
"Find new music like Taylor Swift"
"Recommend songs based on jazz"
"Discover new rock bands"
```

---

## Lyrics Commands

### Get Lyrics
```
"Show me the lyrics to Bohemian Rhapsody"
"Get lyrics for Imagine by John Lennon"
"Find lyrics to Shape of You"
"What are the words to Hotel California?"
```

> **Note**: Requires GENIUS_API_TOKEN in .env for full lyrics. Falls back to web search if not configured.

---

## Meeting & Calendar Commands

> **Requirements**: Google OAuth credentials (credentials.json), Google Calendar access

### Create Instant Meeting
```
"Create an instant meeting"
"Start a meeting right now"
"Create a quick Google Meet"
"Make a meeting called 'Team Standup'"
"Create a 90-minute meeting"
```

### Schedule Future Meetings
```
"Schedule a meeting titled 'Project Review' on December 15 at 10 AM"
"Create a meeting for tomorrow at 2 PM"
"Schedule 'Client Call' on 2025-12-20 at 14:30 for 60 minutes"
"Book a meeting next Monday at 9 AM with john@example.com"
"Schedule meeting with john@example.com and jane@example.com tomorrow at 3 PM"
```

**Date Format**: "YYYY-MM-DD HH:MM" (24-hour format)
**Example**: "2025-12-15 14:30" = December 15, 2025 at 2:30 PM

### List Meetings
```
"Show me my next 5 meetings"
"List my upcoming meetings"
"What meetings do I have today?"
"Show my calendar for this week"
```

### Join Meetings
```
"What's my next meeting?"
"Join my next meeting"
"Get details about next meeting"
"Open my next Google Meet"
```

### Join by Code
```
"Join meeting with code abc-defg-hij"
"Connect to meeting code xyz-mnop-qrs"
```

### Cancel Meetings
```
"Cancel my next meeting"
"Delete the next meeting"
"Remove my upcoming meeting"
```
*Automatically notifies all attendees*

---

## Pro Tips

### 🎯 Natural Language
You can speak naturally! Sentinel understands:
- "Hey, can you search for Python tutorials?"
- "I want to play some jazz music"
- "Could you tell me the weather in London?"
- "Please create a meeting for tomorrow"

### 🔄 Multi-Step Commands
Sentinel can handle complex requests:
- "Search for the best laptop 2025 and open the first result"
- "Play relaxing music and tell me the weather"
- "Create a meeting tomorrow and show my upcoming calendar"

### 🎵 Music Platform Priority
- Spotify commands work ONLY if Spotify Premium + active device
- YouTube commands work always (no subscription needed)
- "Play [song]" tries Spotify first, falls back to YouTube

### 📱 Spotify Active Device Required
For Spotify commands to work:
1. Open Spotify app on your phone/computer
2. Play any song briefly (to activate device)
3. Then Sentinel can control playback

### 🌐 Free APIs Used
These work without API keys:
- Weather (wttr.in)
- Translation (MyMemory)
- Currency (exchangerate-api)
- Definitions (Free Dictionary API)
- URL Shortening (TinyURL)

### 🔑 API Keys Required
These need configuration:
- Web Search: `TAVILY_API_KEY` (required)
- Spotify: `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`
- Meetings: Google OAuth `credentials.json`
- Full Lyrics: `GENIUS_API_TOKEN` (optional - falls back to web scraping)
- Text-to-Speech: `ELEVENLABS_API_KEY` (optional)
- Wake Word: `PORCUPINE_KEY` (required)

### ⚡ Performance Tips
- **Web Search**: Results in 2-3 seconds
- **Music Play**: 3-5 seconds (Spotify), 5-10 seconds (YouTube auto-play)
- **Weather**: 1-2 seconds (free API, no key needed)
- **Meetings**: 3-5 seconds (requires Google OAuth)

### 🎭 Wake Word
- Always start with **"Sentinel"**
- Wait for confirmation sound/feedback
- Speak clearly and at normal pace
- If not detected, try again with emphasis: **"SEN-ti-nel"**

### 🛠️ Troubleshooting

**"No active Spotify device found"**
- Open Spotify app
- Play and pause any song
- Try voice command again

**"Google OAuth error"**
- Check `credentials.json` exists in `Sentinel-AI-Frontend/`
- Run `python fix_token.py` to re-authenticate

**"Web search failed"**
- Verify `TAVILY_API_KEY` in `Sentinel-AI-Backend/.env`
- Get free key at https://tavily.com/

**"YouTube auto-play not working"**
- Try: "Auto-play [song] on YouTube Music"
- Or use Playwright version: "Play [song] on YouTube Music"

---

## Command Categories Summary

| Category | Commands | Examples |
|----------|----------|----------|
| 🌐 **Web & Search** | 14 tools | Search, open websites, scrape, download files |
| 🌤️ **Weather & News** | 3 tools | Current weather, forecasts, latest news |
| 🔧 **Utilities** | 4 tools | Translation, currency, definitions, URL shortening |
| 🎵 **Music (Spotify)** | 8 tools | Play, pause, skip, volume, current song |
| 🎥 **Music (YouTube)** | 19 tools | Auto-play, playlists, genres, moods, lyrics |
| 🎭 **Music Control** | 6 tools | Playwright automation for YouTube Music |
| 📅 **Meetings** | 6 tools | Create, schedule, list, join, cancel meetings |
| **TOTAL** | **60+ capabilities** | **Natural voice interaction** |

---

## Example Conversations

### Scenario 1: Work Morning Routine
```
You: "Sentinel"
Sentinel: [beep]

You: "What's my next meeting?"
Sentinel: "Your next meeting is 'Team Standup' at 9:00 AM. Opening Google Meet now."

You: "What's the weather today?"
Sentinel: "Current weather in San Francisco: 68°F, Partly Cloudy."

You: "Play some focus music"
Sentinel: "Playing focus music playlist on YouTube Music."
```

### Scenario 2: Research Task
```
You: "Sentinel"
Sentinel: [beep]

You: "Search for latest AI breakthroughs 2025"
Sentinel: "Here are the top 5 results about AI breakthroughs..."

You: "Open the first result"
Sentinel: "Opening article in browser."

You: "Extract text from that page"
Sentinel: "Here's the extracted content: [text summary]"
```

### Scenario 3: Music Discovery
```
You: "Sentinel"
Sentinel: [beep]

You: "Discover music similar to Coldplay"
Sentinel: "Opening music discovery for Coldplay-style artists..."

You: "Play the first suggestion"
Sentinel: "Now playing [song] by [artist]."

You: "Show me the lyrics"
Sentinel: "Here are the lyrics to [song]..."
```

### Scenario 4: Meeting Management
```
You: "Sentinel"
Sentinel: [beep]

You: "Schedule a meeting titled 'Project Review' tomorrow at 2 PM with john@example.com"
Sentinel: "Meeting 'Project Review' scheduled for [date] at 2:00 PM. Calendar invite sent to john@example.com."

You: "Show my upcoming meetings"
Sentinel: "You have 3 upcoming meetings: 1. Team Standup at 9 AM today, 2. Project Review at 2 PM tomorrow..."
```

---

## Advanced Features

### Chaining Commands
Some agents can handle multi-step requests:
```
"Search for best Italian restaurants in Boston and open the first one"
"Play some jazz and tell me the weather"
"Create a meeting and show my calendar"
```

### Context Awareness
The supervisor agent routes your requests intelligently:
- Music keywords → Music Agent
- Meeting/calendar keywords → Meeting Agent
- Search/web keywords → Browser Agent
- Everything else → Best matching agent

### Platform Fallbacks
Music commands automatically try multiple platforms:
1. Try Spotify (if configured)
2. Fall back to YouTube Music (auto-play)
3. Fall back to regular YouTube
4. Report if all fail

---

## Keyboard Shortcuts (When Available)

While using the application:
- **Ctrl+M**: Mute/unmute microphone
- **Ctrl+Q**: Quit application
- **Esc**: Cancel current operation

---

## Configuration Files

### Backend (.env)
```
TAVILY_API_KEY=your_key_here
PORCUPINE_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview
ELEVENLABS_API_KEY=your_key (optional)
TTS_ENABLED=true
GENIUS_API_TOKEN=your_key (optional)
SPOTIPY_CLIENT_ID=your_id (optional)
SPOTIPY_CLIENT_SECRET=your_secret (optional)
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
```

### Frontend (.env)
```
MONGODB_CONNECTION_STRING=your_connection_string
MONGODB_DATABASE=sentinel_ai
MONGODB_COLLECTION_USERS=users
```

---

## Getting Help

### Documentation
- **TECH_STACK.md** - Complete technology stack
- **ARCHITECTURE_DIAGRAM.txt** - System architecture
- **GOOGLE_MEET_SETUP.md** - Google OAuth setup
- **ELEVENLABS_SETUP.md** - Text-to-speech setup
- **WHY_LANGCHAIN.md** - Why we use LangChain
- **REQUIREMENTS_CLEANUP.md** - Dependencies explanation

### Troubleshooting
1. Check all API keys in `.env` files
2. Verify internet connection
3. Ensure microphone permissions granted
4. Check logs in application for errors
5. Restart application if unresponsive

### Community
- GitHub Issues: Report bugs or request features
- Documentation: Read setup guides for specific features

---

*Sentinel AI Voice Commands Guide*
*Last Updated: November 21, 2025*
*Total Commands: 60+ capabilities across 47 tools*
