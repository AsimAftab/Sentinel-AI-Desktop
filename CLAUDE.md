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

Dependencies are also managed via `uv` and `pyproject.toml` (dependency groups: `backend`, `frontend`, `dev`; lockfile `uv.lock`).

### Lint / Format / Typecheck
```bash
uv run lint        # ruff check .
uv run format      # ruff format . (ruff is the sole formatter — no black, no isort)
uv run typecheck   # pyright
```

Ruff config lives in `pyproject.toml` (line-length 100, rules E/F/I/B, target py311). Pyright config in `pyrightconfig.json`.

### Testing
There is no formal test suite (no pytest). Testing is script-based: `test_threading.py` at the root and `Sentinel-AI-Frontend/devTest/` scripts (e.g. `test_atlas_connection.py`), plus the manual component tests described in "Testing Individual Components" below.

### Environment Configuration
The application requires environment variables in two `.env` files:

**Sentinel-AI-Backend/.env** (AI backend services):
- `PORCUPINE_KEY` - Picovoice wake word detection API key
- `TAVILY_API_KEY` - Tavily search API key
- `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI` - Spotify integration
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION` - Azure OpenAI LLM
- `ELEVENLABS_API_KEY` - ElevenLabs text-to-speech API key
- `TTS_ENABLED` - Enable/disable text-to-speech (true/false)
- `TTS_FALLBACK_ENABLED`, `TTS_FALLBACK_RATE` - Offline TTS fallback when ElevenLabs unavailable
- `GENIUS_API_TOKEN` - Optional Genius API for full lyrics text
- `LANGCHAIN_TRACING_V2` - Enable LangSmith tracing (true/false) for debugging
- `LANGCHAIN_API_KEY` - LangSmith API key from https://smith.langchain.com/settings
- `LANGCHAIN_PROJECT` - LangSmith project name (e.g., "sentinel-ai-desktop-backend")
- `LANGCHAIN_ENDPOINT` - LangSmith API endpoint (https://api.smith.langchain.com)

**LLM provider selection** (backend `.env`; can also be configured live from the frontend Settings page, persisted to MongoDB via `settings_service.py`):
- `LLM_PROVIDER` - Primary provider: `azure` (default) | `ollama` | `openai` | `zhipu`
- `LLM_TEMPERATURE`, `LLM_FALLBACK_ENABLED`, `LLM_CACHE_ENABLED` - Global LLM behavior
- `AZURE_OPENAI_ENABLED` - Enable Azure provider (default true; other providers default disabled)
- `OLLAMA_ENABLED`, `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT` - Local Ollama provider
- `OPENAI_ENABLED`, `OPENAI_API_KEY`, `OPENAI_MODEL` - OpenAI provider
- `ZHIPU_ENABLED`, `ZHIPU_API_KEY`, `ZHIPU_MODEL`, `ZHIPU_BASE_URL` - Zhipu AI (GLM) provider
- `LLM_AGENT_<AGENT>` / `LLM_AGENT_<AGENT>_TEMPERATURE` - Per-agent provider/temperature overrides (e.g. `LLM_AGENT_MUSIC=ollama`)

**Voice tuning** (backend `.env`, all optional):
- `WAKE_WORD_SENSITIVITY` - Porcupine sensitivity
- `STT_LANGUAGE`, `STT_ENERGY_THRESHOLD`, `STT_PAUSE_THRESHOLD` - Speech recognition tuning
- `CONTINUOUS_LISTENING` - Follow-up conversation mode

**MongoDB (also used by backend** for agent memory and Spotify token storage):
- `MONGODB_COLLECTION_TOKENS` - Collection for OAuth tokens (`token_manager.py`, `spotify_user_auth.py`)

**Sentinel-AI-Frontend/.env** (Database):
- `MONGODB_CONNECTION_STRING` - MongoDB Atlas connection string
- `MONGODB_DATABASE`, `MONGODB_COLLECTION_USERS` - Database and collection names

**Sentinel-AI-Frontend/credentials.json** - Google OAuth credentials for Google Meet integration

## Architecture

### Unified Launcher Pattern (launcher.py)

The launcher orchestrates both components with event-based communication:

1. **Main Thread**: Runs PyQt5 frontend (Qt requirement)
2. **Child Thread**: Runs backend voice assistant via `BackendRunner`
3. **Communication**: `EventBus` singleton with thread-safe queues + `QtEventBridge` for instant GUI delivery
4. **Shutdown**: Cooperative via `threading.Event` — backend exits within ~1s

### Event Bus (integration/event_bus.py)

Thread-safe singleton managing bidirectional event communication:

**Event Types** (`EventType` enum):
- Backend lifecycle: `BACKEND_STARTING`, `BACKEND_READY`, `BACKEND_STOPPED`, `BACKEND_ERROR`
- Voice workflow: `LISTENING_FOR_WAKE_WORD`, `WAKE_WORD_DETECTED`, `LISTENING_FOR_COMMAND`, `COMMAND_RECEIVED`, `PROCESSING_COMMAND`, `RESPONSE_GENERATED`
- TTS: `TTS_SPEAKING`, `TTS_FINISHED`
- Conversation: `FOLLOW_UP_DETECTED`, `CONVERSATION_ENDED`
- Logging: `LOG_MESSAGE`
- Frontend → Backend: `SHUTDOWN_REQUEST`

**Queues**:
- `frontend_queue`: Backend → Frontend events
- `backend_queue`: Frontend → Backend events
- `QtEventBridge`: pyqtSignal for zero-latency cross-thread GUI delivery

### Backend Architecture (Sentinel-AI-Backend/)

**Entry Point**: `main.py` → validates `TAVILY_API_KEY` → calls `src/utils/orchestrator.py:run_sentinel_agent()`

**Voice Pipeline** (`src/utils/orchestrator.py`):
1. `WakeWordListener` - Detects "Sentinel" wake word using Porcupine
2. `SpeechRecognitionAgent` - Captures voice command using Google Speech Recognition
3. `route_to_langgraph()` - Routes command to LangGraph multi-agent system
4. `TextToSpeech` - Converts AI responses to speech using ElevenLabs (NEW!)

**Multi-Agent System** (`src/graph/graph_builder.py`):
- **LLM**: Multi-provider via `src/utils/llm_config.py` — Azure OpenAI (default), Ollama (local), OpenAI, and Zhipu AI (GLM). Supports per-agent provider/temperature assignment, automatic fallback, instance caching, and live reload (`reload_llm_config()`). Config loads from env vars or MongoDB (set from the frontend Settings page). See `MULTIPLE_LLM_PROVIDERS_IMPLEMENTATION.md`.
- **Supervisor Agent**: Routes tasks to specialized agents (Browser, Music, Meeting, System, Productivity, Notes, Email, or FINISH)
- **Specialist agents** (declared in `agent_registry.py`): Browser (`browser_tools`), Music (`music_tools`, custom prompt), Meeting (`meeting_tools`), System (`system_tools`), Productivity (`productivity_tools`), Notes (`notes_tools`), Email (`email_tools`)
- **Graph Framework**: LangGraph with ReAct agents using `langgraph.prebuilt.create_react_agent`

**Key Files**:
- `src/utils/wake_word_listener.py` - Porcupine wake word detection
- `src/utils/speech_recognizer.py` - Google Speech Recognition wrapper
- `src/utils/text_to_speech.py` - ElevenLabs TTS integration
- `src/utils/langgraph_router.py` - Routes commands to LangGraph
- `src/utils/agent_memory.py` - Short-term memory service for agent context
- `src/graph/graph_builder.py` - Multi-agent graph (auto-constructed from registry)
- `src/graph/agent_registry.py` - Declarative agent definitions (add new agents here)
- `src/graph/agent_state.py` - Shared state structure for agents
- `src/utils/container.py` - Dependency injection container (ServiceContainer)
- `src/utils/log_config.py` - Centralized logging configuration
- `src/utils/llm_config.py` - Multi-provider LLM config with per-agent temperature
- `src/tools/browser_tools.py` - Enhanced web tools (14 tools: search, weather, news, translation, etc.)
- `src/tools/music_tools.py` - Enhanced Spotify/YouTube tools (25 tools: lyrics, genres, moods)
- `src/tools/meeting_tools.py` - Google Meet and Calendar integration (6 tools)
- `src/tools/system_tools.py` - System control tools (15 tools: volume, brightness, apps)
- `src/tools/productivity_tools.py` - Productivity tools (6 tools: timers, alarms)
- `src/tools/notes_tools.py` - Notes agent tools
- `src/tools/email_tools.py` - Email agent tools
- `src/utils/spotify_user_auth.py`, `src/utils/token_manager.py` - Per-user Spotify OAuth with MongoDB-backed token storage

### Frontend Architecture (Sentinel-AI-Frontend/)

**Entry Point**: `main.py` → Creates `QApplication` → Shows `MainApp` (QStackedWidget)

**Page Flow**:
1. `LoginPage` - User authentication (keyring-based session management)
2. `SignupPage` - User registration
3. `DashboardPage` - Main dashboard with service cards and backend status widget
4. `SettingsPage` (`ui/views/settings_page.py`) - LLM provider configuration UI: primary provider dropdown, global temperature, fallback toggle, per-provider enable/API-key/endpoint/model cards. Persisted to MongoDB via `database/settings_service.py`; the backend reads this config at LLM initialization.
5. `LogsPage` (`ui/views/logs_page.py`) - Live backend log viewer

**Key Components**:
- `auth/keyring_auth.py` - Secure credential storage using system keyring
- `auth/session_manager.py` - Session persistence and validation
- `database/user_service.py` - MongoDB user management
- `database/settings_service.py` - MongoDB-persisted LLM settings (shared with backend)
- `services/meet_service.py` - Google Meet integration (OAuth2, event scheduling)
- `services/spotify_service.py` - Spotify account linking
- `services/token_store.py` - OAuth token storage pattern
- `services/service_manager.py` - Service lifecycle management
- `ui/views/dashboard.py` - Main dashboard view

**Backend Status Badge** (built into dashboard):
- Color-coded status indicator connected via Qt signal/slot
- Zero-latency event delivery via `QtEventBridge` (pyqtSignal)
- Displays wake word detections, commands, responses, errors

### Integration Layer (integration/)

**Purpose**: Connect backend and frontend via event-based communication.

**event_bus.py**:
- Singleton `EventBus` class with thread-safe queues
- `Event` dataclass with type, status, data, error, timestamp
- `QtEventBridge(QObject)` with `pyqtSignal` for instant GUI delivery
- `EventType` enum for all backend/frontend events
- `BackendStatus` enum for UI display

**backend_runner_v2.py**:
- Runs backend in daemon thread with `threading.Event` for graceful shutdown
- Creates `ServiceContainer` and wires `event_bus` + `shutdown_event`
- Passes container to `run_sentinel_agent()` for dependency injection
- `LogStreamHandler` streams Python logging to frontend via EventBus
- `StdoutCapture` catches third-party print() as safety net

## Development Patterns

### Adding New Backend Agents

Adding a new agent requires only two steps:

1. Create a tools file in `Sentinel-AI-Backend/src/tools/` with a tools list:
   ```python
   # src/tools/my_tools.py
   from langchain.tools import tool

   @tool
   def my_tool(query: str) -> str:
       """Tool description."""
       return "result"

   my_tools = [my_tool]
   ```

2. Add one entry to `AGENT_REGISTRY` in `src/graph/agent_registry.py`:
   ```python
   AgentDefinition(
       name="MyAgent",
       description="For tasks involving...",
       tools_module="src.tools.my_tools",
       tools_attr="my_tools",
       priority=80,
   ),
   ```

The graph builder auto-constructs supervisor prompt, nodes, edges, and router from the registry. No changes to `graph_builder.py` needed.

### Adding New Frontend Services

1. Create service module in `Sentinel-AI-Frontend/services/` (e.g., `calendar_service.py`)
2. Add service card to `ui/views/dashboard.py`
3. Use `service_manager.py` for lifecycle management if needed
4. Store OAuth tokens using `token_store.py` pattern

### Shutdown Handling

The launcher ensures graceful shutdown via `threading.Event`:
1. User closes window → `QMainWindow.closeEvent()`
2. Close event calls `launcher.shutdown()`
3. Backend runner calls `shutdown_event.set()`
4. Orchestrator's `_should_run()` returns False, loop exits within ~1s
5. `wake_listener.stop()` and `memory.end_session()` cleanup in `finally:`
6. PyQt event loop exits

## Dependencies

Declared in `pyproject.toml` dependency groups (`backend`, `frontend`, `dev`), locked with `uv.lock`.

**Backend** (group `backend`):
- Core: `langgraph`, `langchain`, `langchain-openai`, `langchain-ollama`, `langsmith`
- Voice: `PyAudio`, `SpeechRecognition`, `pvporcupine` (wake word), `elevenlabs`, `pygame`
- Tools: `spotipy` (Spotify), `playwright` (browser automation), `lyricsgenius`, `pycaw`/`screen-brightness-control`/`pyautogui` (system control)
- Google APIs + `pymongo` (agent memory, tokens)

**Frontend** (group `frontend`):
- UI: `PyQt5`, `QtAwesome`
- Auth: `keyring`, `bcrypt`, `cryptography`
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

## Debugging with LangSmith

LangSmith provides powerful observability and debugging for the LangGraph multi-agent system.

### Setup LangSmith

1. **Get API Key**: Sign up at https://smith.langchain.com and get your API key from Settings
2. **Configure Environment**: Add to `Sentinel-AI-Backend/.env`:
   ```bash
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your_api_key_here
   LANGCHAIN_PROJECT=sentinel-ai-desktop-backend
   LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
   ```
3. **Run Application**: Tracing is automatic when enabled - just run the backend
4. **View Traces**: Visit https://smith.langchain.com to see detailed execution traces

### What LangSmith Shows

- **Agent Routing**: See how the Supervisor routes tasks to Browser/Music/Meeting agents
- **Tool Calls**: Track which tools are called with what parameters
- **LLM Interactions**: View all prompts sent to Azure OpenAI and responses received
- **Execution Time**: Identify performance bottlenecks in the agent pipeline
- **Error Tracking**: Debug failures with full stack traces and context
- **Multi-Turn Conversations**: Trace follow-up questions through the conversation loop

### Debugging Tips

- Each voice command creates a new trace in LangSmith
- Filter traces by agent (Browser, Music, Meeting) to debug specific tools
- Use "Playground" to replay and modify prompts without voice input
- Check token usage to optimize costs
- Export traces to share with team or for documentation

### Disabling Tracing

Set `LANGCHAIN_TRACING_V2=false` in `.env` or comment out the variable to disable tracing.

## Agent Memory System

The backend includes a short-term memory system that allows agents to know what has been done in recent interactions.

### How It Works

**Memory Storage** (`src/utils/agent_memory.py`):
- Uses MongoDB (same instance as frontend) for persistent storage
- Falls back to in-memory storage if MongoDB unavailable
- Auto-expires old memories via TTL index (default: 24 hours)

**Memory Types**:
- `command` - User voice commands
- `agent_action` - Agent invocations with tools used
- `tool_call` - Individual tool calls with inputs/outputs
- `result` - Final responses
- `error` - Errors that occurred

**Session Tracking**:
- Each wake-word conversation gets a unique `session_id`
- Commands and actions within a session are linked
- Sessions end when conversation completes or times out

### Context Injection

Before each agent executes, recent memory is injected into its prompt:

```
[Recent Activity]
• User asked: "play some jazz"
• Music agent used search_and_play_song: Playing jazz playlist on Spotify
• User asked: "something more upbeat"

[Current Request]
play some funk music
```

This allows agents to understand context from previous interactions.

### MongoDB Collection Schema

```javascript
// Collection: agent_memory
{
  "_id": ObjectId,
  "user_id": "user_object_id",
  "session_id": "uuid-string",
  "timestamp": ISODate,
  "type": "command" | "agent_action" | "tool_call" | "result" | "error",
  "agent": "Browser" | "Music" | "Meeting" | "System" | "Productivity",
  "content": {
    // For commands:
    "command": "play some jazz",

    // For agent_action:
    "input": "user request",
    "output": "agent response",
    "tools_used": ["tool1", "tool2"],
    "success": true,
    "duration_ms": 1500
  },
  "expires_at": ISODate  // TTL - auto-deletes after 24h
}
```

### Configuration

Add to `Sentinel-AI-Backend/.env`:
```bash
# Uses same MongoDB as frontend
MONGODB_CONNECTION_STRING=mongodb+srv://...
MONGODB_DATABASE=sentinel_ai_db
```

If not configured, memory falls back to in-memory (non-persistent, clears on restart).

### Using Memory in Code

```python
from src.utils.agent_memory import get_agent_memory, MemoryType

memory = get_agent_memory()

# Start a session
session_id = memory.start_session()

# Store a command
memory.store_command("play some jazz")

# Store agent action
memory.store_agent_action(
    agent="Music",
    input_text="play some jazz",
    output_text="Playing jazz playlist",
    tools_used=["search_and_play_song"],
    success=True,
    duration_ms=1500
)

# Get context for agent
context = memory.get_context_for_agent(agent="Music", minutes=15)

# Get recent memories
recent = memory.get_recent_memories(minutes=30, limit=10)

# End session
memory.end_session()
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

## Technical Roadmap

**The project is being rebuilt per `REBUILD_PLAN.md`** (Tauri 2 + React frontend, async FastAPI `sentinel_core` service, Groq/Cerebras providers, Windows MCP server). The legacy `Sentinel-AI-Backend`/`Sentinel-AI-Frontend`/`integration` code described above is the reference implementation being ported, not the target. Historical design docs live in `docs/`.

See **`docs/ENHANCEMENTS.md`** for the earlier technical audit and enhancement roadmap. It catalogs:
- 8 critical bugs with file paths and line numbers
- 7 security vulnerabilities with suggested fixes
- 12 performance optimizations
- 6 proposed new agents and 20+ new tools
- 8 architecture improvements
- A prioritized 3-phase implementation roadmap (Stability > Performance > Features)

When implementing fixes or new features, consult `ENHANCEMENTS.md` for context on known issues and the recommended approach.

## Code Style Notes

- Backend uses the standard `logging` module, configured centrally in `src/utils/log_config.py` (streamed to the frontend via `LogStreamHandler`)
- Frontend uses PyQt5 signals/slots for event handling
- Integration layer uses dataclasses and type hints
- Environment variables loaded via `python-dotenv`
- Formatting/linting via ruff (`uv run format` / `uv run lint`), typechecking via pyright — see `pyproject.toml`
- `AGENTS.md` at the root holds repo guidelines (structure, commit/PR conventions)
