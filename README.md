# 🤖 Sentinel AI Desktop

<div align="center">

![Sentinel AI](https://img.shields.io/badge/Sentinel-AI-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange?style=for-the-badge)
![PyQt5](https://img.shields.io/badge/PyQt5-Desktop-red?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A powerful voice-activated AI assistant with multi-agent capabilities for desktop automation, music control, web browsing, meeting management, and productivity.**

[Features](#-key-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Voice Commands](#-voice-commands)
- [Project Structure](#-project-structure)
- [Documentation](#-documentation)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**Sentinel AI Desktop** is an advanced voice-activated AI assistant that combines the power of LangGraph multi-agent systems with a sleek PyQt5 desktop interface. Built with a unique unified launcher architecture, Sentinel AI seamlessly integrates backend voice processing with frontend service management to provide a comprehensive desktop automation experience.

### What Makes Sentinel AI Special?

- 🗣️ **Wake Word Activation**: Just say "Sentinel" to activate the assistant
- 🤖 **5 Specialized AI Agents**: 66+ tools for comprehensive task automation
- 🎵 **Music Control**: Spotify and YouTube integration with auto-play
- 📅 **Meeting Management**: Google Meet and Calendar integration
- ⚙️ **System Control**: Volume, brightness, applications, screenshots
- ⏱️ **Productivity Tools**: Timers, alarms, and task management
- 🌐 **Web Browsing**: Search, weather, news, translation, and more
- 🎨 **Modern UI**: Beautiful PyQt5 dashboard with real-time backend status
- 🔒 **Secure**: MongoDB authentication with keyring-based session management

---

## ✨ Key Features

### 🎤 Voice-Activated Control
- Wake word detection using Picovoice Porcupine
- Google Speech Recognition for command processing
- ElevenLabs text-to-speech for natural responses
- Multi-turn conversation support

### 🤖 Multi-Agent System (66+ Tools)

#### 1️⃣ **Browser Agent** (14 tools)
- Web search (Tavily API)
- Weather forecasts
- Latest news
- Translation services
- Currency exchange
- Website scraping
- File downloads

#### 2️⃣ **Music Agent** (25+ tools)
- Spotify integration
- YouTube auto-play
- Lyrics search (full & snippet)
- Mood-based playlists
- Genre discovery
- Playback control

#### 3️⃣ **Meeting Agent** (6 tools)
- Create instant meetings
- Schedule meetings
- List upcoming events
- Join meetings
- Cancel meetings
- Google Calendar integration

#### 4️⃣ **System Agent** (15 tools)
- Volume control (increase, decrease, set, mute)
- Brightness control (increase, decrease, set)
- Application management (open, close, list)
- Screenshot capture
- System information

#### 5️⃣ **Productivity Agent** (6 tools)
- Set timers (1 min - 8 hours)
- Set alarms (specific times)
- List active timers
- Cancel timers/alarms
- Named timers for workflows

### 🖥️ Desktop Application
- **Secure Authentication**: MongoDB-based user management
- **Session Management**: Keyring-based credential storage
- **Service Cards**: Quick access to integrated services
- **Backend Status Widget**: Real-time monitoring of voice assistant
- **Modern UI**: Custom QSS styling with responsive design

### 🔧 Integration Layer
- Thread-safe communication bus
- Runtime monkey-patching (no source modification)
- Graceful shutdown handling
- Message queues for inter-process communication

---

## 🏗️ Architecture

Sentinel AI uses a unique **Unified Launcher Pattern** that orchestrates both components without modifying source code:

```
┌─────────────────────────────────────────────────────────┐
│                    launcher.py                          │
│                  (Unified Orchestrator)                 │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐  ┌──────▼────────┐
│ Main Thread  │  │ Child Thread  │
│  (PyQt5 UI)  │  │ (Voice Agent) │
└───────┬──────┘  └──────┬────────┘
        │                 │
        │  ┌─────────────┐│
        └──┤ Comm Bus    ├┘
           │ (Thread-Safe)│
           └─────────────┘
```

### Components

1. **Backend (Sentinel-AI-Backend/)**
   - Voice pipeline with wake word detection
   - LangGraph multi-agent system
   - 5 specialized agents with 66+ tools
   - Azure OpenAI integration

2. **Frontend (Sentinel-AI-Frontend/)**
   - PyQt5 desktop application
   - User authentication & session management
   - Service management dashboard
   - Real-time backend status monitoring

3. **Integration Layer (integration/)**
   - `communication.py` - Thread-safe message bus
   - `backend_runner.py` - Backend thread management
   - `frontend_enhancer.py` - Runtime UI patching
   - `status_widget.py` - Backend status widget

---

## 💻 Installation

### Prerequisites

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **RAM**: Minimum 4GB (8GB recommended)
- **Disk Space**: ~5GB for all dependencies

### Step 1: Clone the Repository

```bash
git clone https://github.com/AsimAftab/Sentinel-AI-Desktop.git
cd Sentinel-AI-Desktop
```

### Step 2: Install Dependencies

#### Option A: Automated Installation (Recommended)
```bash
python setup_launcher.py
```
*This installs ~305 packages and may take 20-60 minutes*

#### Option B: Manual Installation
```bash
# Install backend dependencies (~295 packages)
cd Sentinel-AI-Backend
pip install -r requirements.txt

# Install frontend dependencies (~11 packages)
cd ../Sentinel-AI-Frontend
pip install -r requirements.txt

cd ..
```

### Step 3: Install System Dependencies

#### For Audio (Wake Word Detection)
- **Windows**: PyAudio is included in requirements
- **Linux**: 
  ```bash
  sudo apt-get install portaudio19-dev python3-pyaudio
  ```
- **macOS**: 
  ```bash
  brew install portaudio
  ```

---

## 🚀 Quick Start

### 1. Configure Environment Variables

Create `.env` files with your API keys:

#### Backend Configuration (`Sentinel-AI-Backend/.env`)

```bash
# Required
PORCUPINE_KEY=your_picovoice_api_key
TAVILY_API_KEY=your_tavily_api_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_API_KEY=your_azure_api_key
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Optional (for enhanced features)
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=sarah_voice_id
TTS_ENABLED=true
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
GENIUS_API_TOKEN=your_genius_token

# Optional (for debugging)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=sentinel-ai-desktop
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

#### Frontend Configuration (`Sentinel-AI-Frontend/.env`)

```bash
MONGODB_CONNECTION_STRING=your_mongodb_atlas_connection_string
MONGODB_DATABASE=sentinel_ai
MONGODB_COLLECTION_USERS=users
```

#### Google Meet Setup (`Sentinel-AI-Frontend/credentials.json`)

Download OAuth credentials from Google Cloud Console and place in `Sentinel-AI-Frontend/credentials.json`

See [GOOGLE_MEET_SETUP.md](GOOGLE_MEET_SETUP.md) for detailed instructions.

### 2. Run Sentinel AI

```bash
# Run the integrated system (recommended)
python launcher.py
```

Or run components individually:

```bash
# Backend only (voice assistant)
cd Sentinel-AI-Backend
python main.py

# Frontend only (desktop UI)
cd Sentinel-AI-Frontend
python main.py
```

### 3. First Time Setup

1. **Create Account**: Sign up in the desktop application
2. **Login**: Use your credentials to access the dashboard
3. **Test Voice**: Say "Sentinel" and give a command
4. **Explore**: Try different voice commands from each agent

---

## ⚙️ Configuration

### API Keys Required

| Service | Purpose | Get Key From |
|---------|---------|--------------|
| **Picovoice Porcupine** | Wake word detection | [console.picovoice.ai](https://console.picovoice.ai) |
| **Tavily** | Web search | [tavily.com](https://tavily.com) |
| **Azure OpenAI** | LLM backend | [azure.microsoft.com](https://azure.microsoft.com) |
| **MongoDB Atlas** | User database | [mongodb.com/atlas](https://mongodb.com/atlas) |

### Optional API Keys

| Service | Purpose | Get Key From |
|---------|---------|--------------|
| **ElevenLabs** | Text-to-speech | [elevenlabs.io](https://elevenlabs.io) |
| **Spotify** | Music control | [developer.spotify.com](https://developer.spotify.com) |
| **Genius** | Full lyrics | [genius.com/api-clients](https://genius.com/api-clients) |
| **LangSmith** | Debugging/tracing | [smith.langchain.com](https://smith.langchain.com) |

### Environment Templates

Use the example files as templates:
- `Sentinel-AI-Backend/.env.example`

---

## 🎯 Usage

### Voice Command Pattern

1. **Say**: "Sentinel" (wait for beep confirmation)
2. **Speak**: Your command naturally
3. **Listen**: Sentinel responds and performs the action

### Example Workflows

#### 📚 Study Session
```
"Sentinel, play focus music"              → Music Agent
"Sentinel, set a 50 minute timer"         → Productivity Agent
"Sentinel, set volume to 40"              → System Agent
"Sentinel, take a screenshot of my notes" → System Agent
```

#### 💼 Work Meeting Prep
```
"Sentinel, what's the weather tomorrow?"     → Browser Agent
"Sentinel, schedule a meeting at 3pm"        → Meeting Agent
"Sentinel, set alarm for 2:55 PM"            → Productivity Agent
"Sentinel, open PowerPoint"                  → System Agent
```

#### 🎵 Music Discovery
```
"Sentinel, play some jazz music"
"Sentinel, show me lyrics for this song"
"Sentinel, play happy music"
"Sentinel, create a playlist called Coding"
```

---

## 🗣️ Voice Commands

### Browser Agent Commands
```
"Search for Python tutorials"
"What's the weather in London?"
"Get latest tech news"
"Translate hello to Spanish"
"Open github.com"
```

### Music Agent Commands
```
"Play Shape of You by Ed Sheeran"
"Play some jazz music"
"Show me lyrics for Bohemian Rhapsody"
"Play happy music"
"Next song" / "Previous song" / "Pause"
```

### Meeting Agent Commands
```
"Create a meeting now"
"Schedule a meeting for tomorrow at 3pm"
"List my meetings today"
"Join my next meeting"
"Cancel my meeting at 2pm"
```

### System Agent Commands
```
"Increase volume by 10"
"Set brightness to 75"
"Open notepad"
"Take a screenshot"
"List running applications"
"Close Chrome"
```

### Productivity Agent Commands
```
"Set a timer for 5 minutes"
"Set a 25 minute timer named Pomodoro"
"Set an alarm for 3:30 PM"
"List my timers"
"Cancel all timers"
```

📖 **Full Command Reference**: See [VOICE_COMMANDS.md](VOICE_COMMANDS.md)

---

## 📁 Project Structure

```
Sentinel-AI-Desktop/
├── launcher.py                      # Unified launcher (main entry point)
├── setup_launcher.py                # Automated dependency installer
├── requirements.txt                 # Root dependencies (empty - uses components)
├── integration/                     # Integration layer (thread-safe communication)
│   ├── communication.py             # Message bus for inter-process communication
│   ├── backend_runner.py            # Backend thread management
│   ├── frontend_enhancer.py         # Runtime UI patching
│   └── status_widget.py             # Backend status widget
├── Sentinel-AI-Backend/             # Voice assistant backend
│   ├── main.py                      # Backend entry point
│   ├── requirements.txt             # Backend dependencies (~295 packages)
│   ├── .env                         # Backend configuration (create from .env.example)
│   └── src/
│       ├── graph/                   # LangGraph multi-agent system
│       │   ├── graph_builder.py     # Agent orchestration
│       │   └── agent_state.py       # Shared state
│       ├── tools/                   # Agent tools (66+ tools)
│       │   ├── browser_tools.py     # Web tools (14 tools)
│       │   ├── music_tools.py       # Music tools (19 tools)
│       │   ├── playwright_music_tools.py  # Auto-play (6 tools)
│       │   ├── meeting_tools.py     # Meeting tools (6 tools)
│       │   ├── system_tools.py      # System tools (15 tools)
│       │   └── productivity_tools.py # Productivity tools (6 tools)
│       └── utils/                   # Voice processing utilities
│           ├── orchestrator.py      # Main voice pipeline
│           ├── wake_word_listener.py # Porcupine wake word
│           ├── speech_recognizer.py  # Google Speech API
│           └── text_to_speech.py    # ElevenLabs TTS
├── Sentinel-AI-Frontend/            # Desktop application frontend
│   ├── main.py                      # Frontend entry point
│   ├── requirements.txt             # Frontend dependencies (~11 packages)
│   ├── .env                         # Frontend configuration (MongoDB)
│   ├── credentials.json             # Google OAuth (for Meet integration)
│   ├── auth/                        # Authentication system
│   │   ├── keyring_auth.py          # Secure credential storage
│   │   └── session_manager.py       # Session management
│   ├── database/                    # Database layer
│   │   └── user_service.py          # MongoDB user management
│   ├── services/                    # Service integrations
│   │   ├── meet_service.py          # Google Meet & Calendar
│   │   └── service_manager.py       # Lifecycle management
│   └── ui/                          # User interface
│       ├── views/                   # UI pages
│       │   ├── login.py             # Login page
│       │   ├── signup.py            # Signup page
│       │   └── dashboard.py         # Main dashboard
│       └── qss/                     # Stylesheets
│           └── style.qss            # Custom styling
└── Documentation/                   # Additional documentation
    ├── AGENTS_OVERVIEW.md           # Complete agent reference
    ├── VOICE_COMMANDS.md            # Voice command guide
    ├── GOOGLE_MEET_SETUP.md         # Google Meet setup guide
    ├── MEETING_QUICKSTART.md        # Meeting features quickstart
    ├── SYSTEM_CONTROL_AGENT.md      # System agent documentation
    ├── PRODUCTIVITY_AGENT.md        # Productivity agent guide
    ├── SCREENSHOT_FEATURE.md        # Screenshot feature guide
    ├── CLAUDE.md                    # Developer guide for Claude AI
    └── ARCHITECTURE_DIAGRAM.txt     # Detailed architecture diagram
```

---

## 📚 Documentation

### User Guides
- **[Voice Commands Guide](VOICE_COMMANDS.md)** - Complete reference of all voice commands
- **[Agents Overview](AGENTS_OVERVIEW.md)** - Detailed agent capabilities and examples
- **[Meeting Quickstart](MEETING_QUICKSTART.md)** - Google Meet integration guide
- **[Google Meet Setup](GOOGLE_MEET_SETUP.md)** - OAuth configuration instructions

### Feature Documentation
- **[System Control Agent](SYSTEM_CONTROL_AGENT.md)** - Volume, brightness, apps, screenshots
- **[Productivity Agent](PRODUCTIVITY_AGENT.md)** - Timers and alarms
- **[Screenshot Feature](SCREENSHOT_FEATURE.md)** - Screenshot capture capabilities

### Developer Documentation
- **[CLAUDE.md](CLAUDE.md)** - Complete developer guide and architecture
- **[Architecture Diagram](ARCHITECTURE_DIAGRAM.txt)** - Visual system architecture

---

## 🐛 Troubleshooting

### Common Issues

#### TAVILY_API_KEY Not Found
**Solution**: Backend validates this on startup. Ensure it's in `Sentinel-AI-Backend/.env`

#### PyQt5 Main Thread Error
**Solution**: Qt requires GUI on main thread. Always run via `launcher.py`

#### Wake Word Not Detected
**Solution**: 
- Check `PORCUPINE_KEY` in backend `.env`
- Verify microphone permissions
- Test with louder/clearer voice

#### MongoDB Connection Failed
**Solution**: 
- Verify `MONGODB_CONNECTION_STRING` in frontend `.env`
- Check network connectivity to MongoDB Atlas
- Ensure IP is whitelisted in MongoDB Atlas

#### Google Meet OAuth Error
**Solution**: 
- Ensure `credentials.json` exists in `Sentinel-AI-Frontend/`
- Check OAuth consent screen configuration
- Delete `token.json` and re-authenticate

### Debug Mode

Enable LangSmith tracing for detailed debugging:

```bash
# Add to Sentinel-AI-Backend/.env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=sentinel-ai-debug
```

View traces at [smith.langchain.com](https://smith.langchain.com)

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Adding New Agents

1. Create tool file in `Sentinel-AI-Backend/src/tools/`
2. Define tools using `@tool` decorator
3. Add agent in `src/graph/graph_builder.py`
4. Update supervisor prompt
5. Add routing logic
6. Document in AGENTS_OVERVIEW.md

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings to functions
- Keep commits focused and atomic

### Testing

- Test individual agents: `python test_[agent]_agent.py`
- Test integration: `python launcher.py`
- Test voice commands manually

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

### Technologies & Frameworks
- **[LangGraph](https://github.com/langchain-ai/langgraph)** - Multi-agent orchestration
- **[LangChain](https://github.com/langchain-ai/langchain)** - LLM framework
- **[PyQt5](https://www.riverbankcomputing.com/software/pyqt/)** - Desktop UI framework
- **[Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)** - LLM backend
- **[Picovoice Porcupine](https://picovoice.ai/platform/porcupine/)** - Wake word detection
- **[ElevenLabs](https://elevenlabs.io/)** - Text-to-speech
- **[Tavily](https://tavily.com/)** - Web search API

### Libraries & Tools
- Google Speech Recognition
- Spotify API (spotipy)
- Google Meet & Calendar APIs
- MongoDB Atlas
- Playwright, Selenium, BeautifulSoup4
- And many more amazing open-source libraries!

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/AsimAftab/Sentinel-AI-Desktop/issues)
- **Discussions**: [GitHub Discussions](https://github.com/AsimAftab/Sentinel-AI-Desktop/discussions)
- **Email**: Contact the repository owner

---

## 🗺️ Roadmap

### Planned Features
- 📧 **Email Agent** - Gmail integration (read, send, search)
- 📁 **File Manager Agent** - File operations and organization
- 🏠 **Smart Home Agent** - IoT device control
- 🤖 **Custom Workflows** - User-defined automation sequences
- 🌍 **Multi-language Support** - Support for more languages
- 📱 **Mobile Companion App** - Remote control capabilities

---

<div align="center">

**Made with ❤️ by Asim Aftab**

⭐ **Star this repo if you find it helpful!** ⭐

[Report Bug](https://github.com/AsimAftab/Sentinel-AI-Desktop/issues) • [Request Feature](https://github.com/AsimAftab/Sentinel-AI-Desktop/issues)

</div>
