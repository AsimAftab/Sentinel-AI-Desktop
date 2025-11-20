# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sentinel AI is a voice-activated AI assistant desktop application that combines:
- **Backend**: Voice-activated LangGraph-based multi-agent system with wake word detection
- **Frontend**: PyQt5 desktop application with user authentication and service management
- **Integration Layer**: Unified launcher that runs both components with thread-safe inter-process communication

## Quick Start Commands

### Running the Application
```bash
# Run the integrated system (recommended)
python launcher.py

# Run backend standalone
cd Sentinel-AI-Backend && python main.py

# Run frontend standalone
cd Sentinel-AI-Frontend && python main.py
```

### Setup
```bash
# Install all dependencies (~305 packages, 20-60 minutes)
python setup_launcher.py
```

### Environment Configuration
The application requires environment variables in two `.env` files:

**Sentinel-AI-Backend/.env** (AI backend services):
- `PORCUPINE_KEY` - Picovoice wake word detection API key
- `TAVILY_API_KEY` - Tavily search API key
- `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI` - Spotify integration
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION` - Azure OpenAI LLM
- `ELEVENLABS_API_KEY` - ElevenLabs text-to-speech API key
- `ELEVENLABS_VOICE_ID` - Optional voice ID (defaults to Sarah)
- `TTS_ENABLED` - Enable/disable text-to-speech (true/false)
- `GENIUS_API_TOKEN` - Optional Genius API for full lyrics text

**Sentinel-AI-Frontend/.env** (Database):
- `MONGODB_CONNECTION_STRING` - MongoDB Atlas connection string
- `MONGODB_DATABASE`, `MONGODB_COLLECTION_USERS` - Database and collection names

**Sentinel-AI-Frontend/credentials.json** - Google OAuth credentials for Google Meet integration

## Architecture

### Unified Launcher Pattern (launcher.py)

The launcher orchestrates both components WITHOUT modifying their source code:

1. **Main Thread**: Runs PyQt5 frontend (Qt requirement)
2. **Child Thread**: Runs backend voice assistant (daemon mode)
3. **Communication**: Thread-safe queues via `integration/communication.py`
4. **Enhancement**: Runtime monkey-patching via `integration/backend_runner.py` and `integration/frontend_enhancer.py`

**Key Principle**: Backend and Frontend source code remain UNCHANGED. All integration happens in the `integration/` layer.

### Communication Bus (integration/communication.py)

Thread-safe singleton managing bidirectional message queues:

**Message Types**:
- `STATUS_UPDATE` - Backend status changes (STARTING, READY, LISTENING, PROCESSING, ERROR, STOPPED)
- `WAKE_WORD_DETECTED` - Wake word "Sentinel" detected
- `COMMAND_RECEIVED` - Voice command captured
- `RESPONSE_GENERATED` - AI agent response ready
- `ERROR` - Error occurred
- `SHUTDOWN_REQUEST` - Graceful shutdown signal

**Queues**:
- `frontend_queue`: Backend → Frontend messages
- `backend_queue`: Frontend → Backend messages

### Backend Architecture (Sentinel-AI-Backend/)

**Entry Point**: `main.py` → validates `TAVILY_API_KEY` → calls `src/utils/orchestrator.py:run_sentinel_agent()`

**Voice Pipeline** (`src/utils/orchestrator.py`):
1. `WakeWordListener` - Detects "Sentinel" wake word using Porcupine
2. `SpeechRecognitionAgent` - Captures voice command using Google Speech Recognition
3. `route_to_langgraph()` - Routes command to LangGraph multi-agent system
4. `TextToSpeech` - Converts AI responses to speech using ElevenLabs (NEW!)

**Multi-Agent System** (`src/graph/graph_builder.py`):
- **LLM**: Azure OpenAI GPT (configured via environment variables)
- **Supervisor Agent**: Routes tasks to specialized agents (Browser, Music, or FINISH)
- **Browser Agent**: Uses `browser_tools` for web search/scraping (Tavily search, Selenium)
- **Music Agent**: Uses `music_tools` for Spotify integration (search, play, control playback)
- **Graph Framework**: LangGraph with ReAct agents using `langgraph.prebuilt.create_react_agent`

**Key Files**:
- `src/utils/wake_word_listener.py` - Porcupine wake word detection
- `src/utils/speech_recognizer.py` - Google Speech Recognition wrapper
- `src/utils/text_to_speech.py` - ElevenLabs TTS integration (NEW!)
- `src/utils/langgraph_router.py` - Routes commands to LangGraph
- `src/graph/graph_builder.py` - Multi-agent graph definition
- `src/graph/agent_state.py` - Shared state structure for agents
- `src/tools/browser_tools.py` - Enhanced web tools (search, weather, news, translation, etc.)
- `src/tools/music_tools.py` - Enhanced Spotify/YouTube tools (lyrics, genres, moods)
- `src/tools/playwright_music_tools.py` - Playwright-based auto-play music tools (NEW!)

### Frontend Architecture (Sentinel-AI-Frontend/)

**Entry Point**: `main.py` → Creates `QApplication` → Shows `MainApp` (QStackedWidget)

**Page Flow**:
1. `LoginPage` - User authentication (keyring-based session management)
2. `SignupPage` - User registration
3. `DashboardPage` - Main dashboard with service cards and backend status widget

**Key Components**:
- `auth/keyring_auth.py` - Secure credential storage using system keyring
- `auth/session_manager.py` - Session persistence and validation
- `database/user_service.py` - MongoDB user management
- `services/meet_service.py` - Google Meet integration (OAuth2, event scheduling)
- `services/service_manager.py` - Service lifecycle management
- `ui/views/dashboard.py` - Main dashboard view

**Backend Status Widget** (injected by `integration/frontend_enhancer.py`):
- Color-coded status indicator
- Activity log showing backend events
- Timer-based polling (100ms) of communication bus
- Displays wake word detections, commands, responses, errors

### Integration Layer (integration/)

**Purpose**: Connect backend and frontend without modifying their source code.

**backend_runner.py**:
- Runs backend in daemon thread
- Monkey-patches backend modules at runtime to inject `comm_bus`
- Patches: `wake_word_listener.py`, `speech_recognizer.py`, `langgraph_router.py`
- Sends status updates to frontend queue

**frontend_enhancer.py**:
- Patches `DashboardPage.__init__()` to add `BackendStatusWidget`
- Injects status widget into dashboard layout
- No source file modification

**status_widget.py**:
- Custom PyQt5 widget showing backend status
- Polls `comm_bus.get_frontend_message()` every 100ms
- Updates UI based on message type and status

**communication.py**:
- Singleton `CommunicationBus` class
- Thread-safe `Queue` objects for message passing
- `Message` dataclass with type, status, data, error, timestamp

## Development Patterns

### Monkey Patching Pattern

When adding integration features, ALWAYS use runtime patching in `integration/` rather than modifying source:

```python
# integration/backend_runner.py example
from src.utils.wake_word_listener import WakeWordListener

# Save original method
original_wait = WakeWordListener.wait_for_wake_word

# Define patched version
def patched_wait(self):
    self.comm_bus.send_to_frontend(Message(MessageType.STATUS_UPDATE, status=BackendStatus.LISTENING))
    result = original_wait(self)
    if result:
        self.comm_bus.send_to_frontend(Message(MessageType.WAKE_WORD_DETECTED))
    return result

# Apply patch
WakeWordListener.comm_bus = comm_bus
WakeWordListener.wait_for_wake_word = patched_wait
```

### Adding New Backend Tools

1. Create tool in `Sentinel-AI-Backend/src/tools/` (e.g., `email_tools.py`)
2. Define tools using `@tool` decorator from `langchain.tools`
3. Add tools to agent in `src/graph/graph_builder.py`:
   ```python
   from src.tools.email_tools import email_tools
   email_agent_tools = email_tools
   email_agent_node = create_agent_node(llm, email_agent_tools, "Email")
   workflow.add_node("Email", email_agent_node)
   ```
4. Update supervisor prompt to include new agent
5. Update router function with new conditional edge

### Adding New Frontend Services

1. Create service module in `Sentinel-AI-Frontend/services/` (e.g., `calendar_service.py`)
2. Add service card to `ui/views/dashboard.py`
3. Use `service_manager.py` for lifecycle management if needed
4. Store OAuth tokens using `token_store.py` pattern

### Shutdown Handling

The launcher ensures graceful shutdown:
1. User closes window → `QMainWindow.closeEvent()`
2. Enhanced close event calls `launcher.shutdown()`
3. Backend runner sets `running = False`
4. Backend thread exits cleanly (cleans up Porcupine, speech recognizer)
5. Communication bus queues cleared
6. PyQt event loop exits

## Dependencies

**Backend** (294 packages):
- Core: `langgraph`, `langchain`, `langchain-openai`
- Voice: `PyAudio`, `SpeechRecognition`, `pvporcupine` (wake word)
- Tools: `spotipy` (Spotify), `tavily-python` (search), `selenium` (browser)
- ML: `transformers`, `torch`, `sentence-transformers`

**Frontend** (11 packages):
- UI: `PyQt5`
- Auth: `keyring`, `bcrypt`
- Database: `pymongo`, `dnspython`
- Google APIs: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

**Integration** (0 packages):
- Uses only Python standard library (`queue`, `threading`, `dataclasses`)

## Testing Individual Components

### Test Backend Voice Pipeline
```bash
cd Sentinel-AI-Backend
python main.py
# Say "Sentinel" → Say command → Check LangGraph response
```

### Test Frontend UI
```bash
cd Sentinel-AI-Frontend
python main.py
# Test login, signup, dashboard navigation
```

### Test Specific Backend Agent
```python
# In Sentinel-AI-Backend/
from src.graph.graph_builder import graph

result = graph.invoke({
    "messages": [("user", "play some jazz music")]
})
print(result["messages"][-1])
```

## Common Issues

### TAVILY_API_KEY Not Found
Backend validates this on startup in `main.py`. Ensure it's in `Sentinel-AI-Backend/.env`.

### PyQt5 Main Thread Error
Qt requires GUI on main thread. Always run frontend via `launcher.py` which ensures proper threading.

### Wake Word Not Detected
Check `PORCUPINE_KEY` in backend `.env`. Wake word file: `src/wakeword/Sentinel_en_windows_v3_0_0.ppn`

### MongoDB Connection Failed
Verify `MONGODB_CONNECTION_STRING` in frontend `.env`. Check network connectivity to MongoDB Atlas.

### Google Meet OAuth Error
Ensure `credentials.json` exists in `Sentinel-AI-Frontend/`. Token stored in `token.json` after first auth.

## Code Style Notes

- Backend uses print statements for logging (no logging framework currently)
- Frontend uses PyQt5 signals/slots for event handling
- Integration layer uses dataclasses and type hints
- Environment variables loaded via `python-dotenv`
