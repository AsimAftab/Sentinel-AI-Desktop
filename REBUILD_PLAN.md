# Sentinel AI — Product-Ready Rebuild Plan

Date: 2026-07-18. Based on a full audit of the backend (~9,500 LOC), frontend (~2,600 LOC of PyQt5 views), and integration layer, plus research on Groq/Cerebras capabilities and the Windows MCP ecosystem.

---

## Part 1 — Honest Assessment of the Current Codebase

### What the project is today
A capable **single-user, single-process Windows voice-assistant prototype**. It proved the feature set (voice → supervisor → 7 agents → ~106 tools), but the spine is not product-grade:

| Area | Verdict |
|---|---|
| `llm_config.py` (multi-provider LLM) | **Keep** — best asset in the repo. Adding Groq/Cerebras is ~15 lines each |
| `agent_registry.py` (declarative agents) | **Keep the pattern** — registry-driven graph construction is genuinely good |
| API-based tools (browser, email, meeting, notes) | **Keep** — real integrations, refactor error handling |
| `agent_memory.py` (TTL memory schema) | **Keep the schema** — replace file-based identity, add semantic recall |
| Voice leaf classes (wake word / STT / TTS) | **Keep classes**, discard the orchestration loop |
| `token_store.py` (Fernet + keyring) | **Keep** — strongest frontend module |
| Auth primitives (bcrypt, rate limiting) | **Keep logic**, wrong architecture around it |
| The synchronous voice loop (`orchestrator.py`) | **Rewrite** — strictly serial, 3–8s per turn, no streaming/VAD/barge-in, `asyncio.run()` per command |
| LangGraph state + supervisor routing | **Rewrite** — bare-string substring routing, tuple/str/BaseMessage soup, star-only topology (no agent chaining), no token streaming, module-level globals |
| `system_tools.py` (1,370 LOC) | **Rewrite** — pyautogui Tab-press sequences, hardcoded screen coordinates, `shell=True` injection surface. Demo-ware |
| `playwright_music_tools.py` | **Delete** — the music agent's own prompt tells the LLM never to use it |
| YouTube scraping in `music_tools.py` | **Rewrite** — brittle HTML scraping; keep the spotipy half |
| All PyQt5 views | **Discard** — 2,600+ lines of imperative UI, split-brain styling (QSS + inline f-strings), fixed pixel sizing. Keep only the color palette as design reference |
| Integration layer | **Half is dead code** — `communication.py`, `backend_runner.py`, `frontend_enhancer.py`, `status_widget.py`, `logs_page.py` (~660+ lines) are orphaned. The live path is in-process daemon threads with no isolation: a native-lib crash kills the whole GUI |
| `src/agents/agent_node.py` | **Delete** — broken self-import, dead API |

### Product-readiness showstoppers
1. **Client talks directly to MongoDB Atlas.** Any shipped build carries the cluster connection string on the user's disk → every user has read/write to every other user's data. Needs an API in front of the DB, or a local-first data model.
2. **Auth is local-machine-only.** Password-of-record lives in the OS keyring; an account created on one machine can't log in on another. It's a single-device system masquerading as a cloud app.
3. **Zero distribution story.** No PyInstaller spec, no installer, no auto-update, no crash reporting. `setup_launcher.py` is a dev bootstrap (~4 GB, 20–60 min pip install).
4. **No process isolation.** Backend runs as a daemon thread in the GUI process, swaps `sys.stdout` globally, calls `os.chdir` — restart-after-crash is unreliable by design.
5. **Settings require restart.** The Settings UI writes Mongo *and* rewrites the backend `.env` by string matching; there is no live-reload signal to the running backend.
6. **Latency.** Cloud Google STT (no streaming, no VAD) + blocking ElevenLabs TTS + serial loop = seconds of dead air per turn.

**Conclusion: don't refactor incrementally. Harvest ~30% and rebuild the spine.** The orchestrator and graph state are load-bearing wrong — cheaper to replace than fix.

---

## Part 2 — Target Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Tauri 2 Desktop App (React + TypeScript + Tailwind + shadcn)│
│  - Chat/voice UI with streaming tokens & live agent trace    │
│  - Settings, service connections, logs                       │
│  - Native installer (MSI/NSIS) + auto-updater (Tauri plugin) │
└───────────────┬──────────────────────────────────────────────┘
                │  WebSocket (events, streaming)  +  REST (CRUD)
┌───────────────▼──────────────────────────────────────────────┐
│  Sentinel Core — Python 3.12 sidecar (FastAPI, fully async)  │
│  - Voice pipeline v2: wake word → VAD → Groq Whisper STT     │
│    → agent graph → streaming TTS, with barge-in              │
│  - LangGraph v2: structured-output supervisor, typed state,  │
│    agent-to-agent handoff, token streaming                   │
│  - LLM providers: Groq, Cerebras, Azure, OpenAI, Ollama,     │
│    Zhipu — per-agent assignment + fallback (ported)          │
│  - Memory: session + semantic (SQLite + sqlite-vec)          │
│  - MCP client (langchain-mcp-adapters)                       │
└───────┬──────────────────────────────┬───────────────────────┘
        │ MCP (stdio)                  │ HTTPS
┌───────▼───────────────┐   ┌──────────▼───────────────────────┐
│  Sentinel Windows MCP │   │  External APIs: Groq, Cerebras,  │
│  server (our own):    │   │  Spotify, Google (Meet/Gmail/    │
│  volume, brightness,  │   │  Calendar), Tavily, ElevenLabs   │
│  apps, power, window  │   └──────────────────────────────────┘
│  mgmt via real OS APIs│
└───────────────────────┘
```

### Key decisions and rationale

**1. GUI: Tauri 2 + React/TypeScript (replaces PyQt5).**
- Professional UI is dramatically easier with the web ecosystem (Tailwind, shadcn/ui, Framer Motion) than hand-built QSS.
- Tauri gives small binaries, a first-party **sidecar** mechanism for bundling the Python backend, native MSI/NSIS installers, and a built-in **auto-updater** — the entire missing distribution story.
- The Tauri-2 + PyInstaller-sidecar + FastAPI pattern is well-established with production templates.
- Nothing in the current PyQt5 code is worth porting; only the slate/blue visual language survives as a reference.

**2. Backend becomes a separate process with a real API boundary.**
- FastAPI on `localhost`, WebSocket for the event stream (replaces EventBus queues), REST for settings/history.
- Fixes process isolation (backend crash ≠ GUI crash), enables live settings reload (POST /settings → `reload_llm_config()`), and makes the core reusable headless (CLI, tray-only mode, future mobile).

**3. LLM stack: Groq + Cerebras first-class.**
- Both are OpenAI-compatible with tool calling — they slot into the existing `llm_config.py` pattern exactly like the Zhipu provider (custom `base_url` on `ChatOpenAI`).
- Suggested defaults: **Supervisor → Cerebras or Groq `gpt-oss-120b`** (routing needs speed above all); **specialist agents → Groq `llama-4-scout` / `gpt-oss-20b`**; keep Azure/OpenAI/Ollama/Zhipu as configured alternates. Note Groq has deprecated its Llama-3.x chat models in favor of `gpt-oss-*`.
- **Groq also solves STT**: `whisper-large-v3-turbo` at ~216× real-time replaces blocking Google STT — the single biggest latency win available.
- TTS: ElevenLabs (quality) with Groq TTS (Orpheus/PlayAI, speed) and pyttsx3 (offline) as fallbacks.

**4. Voice pipeline v2 (async, streaming, interruptible).**
- Keep Porcupine wake word (works, already licensed) — optionally add openWakeWord as a keyless fallback.
- Add **VAD** (silero-vad) for end-of-speech detection instead of fixed pause thresholds.
- Stream: mic → VAD-chunked audio → Groq Whisper → graph (tokens stream to UI as they generate) → sentence-chunked TTS that starts speaking before the full response exists.
- **Barge-in**: wake-word/VAD listener stays live during TTS playback; user speech interrupts it.

**5. Agent graph v2 (modern LangGraph).**
- Supervisor uses **structured output / tool-calling handoffs** (`langgraph-supervisor` or `Command`-based), not bare-string substring matching.
- Typed `MessagesState` — no more tuple/str/BaseMessage soup.
- Supervisor-loop topology so multi-step, cross-domain commands work ("find a good jazz album and schedule a listening break at 5pm").
- Keep the **declarative agent registry** pattern; kill import-time global graph/LLM construction (build lazily, injectable, per-request config).
- Native `astream` token/event streaming wired straight to the WebSocket → UI shows live agent trace.

**6. Windows control via our own MCP server ("Sentinel Windows MCP").**
- Existing servers (mukul975/mcp-windows-automation ~80 tools, AutoIt- and RobotJS-based ones, Microsoft's Windows ODR direction) prove the space but are automation-hack-based, just like our current `system_tools.py`.
- We build a **clean, typed MCP server on real OS APIs** — pycaw (volume), screen-brightness-control, psutil (processes), winsdk/UI Automation + `AppsFolder` shell APIs (app launch, window management, media keys, power) — no pyautogui coordinates, no `shell=True`, no Tab-press counting.
- Ship it as a standalone open-source package (stdio MCP): usable by Claude Desktop and any MCP client, not just Sentinel. Sentinel consumes it via `langchain-mcp-adapters`, replacing `system_tools.py` entirely. Music/productivity tools can follow the same MCP shape later.

**7. Data & auth: local-first.**
- Replace client→Atlas with **SQLite (+ sqlite-vec for semantic memory) on the user's machine**. A desktop assistant's history, notes, timers, and settings are personal data — local storage removes the shipped-DB-credentials showstopper, the account system, and the Atlas dependency in one move.
- Keep `token_store.py`'s Fernet+keyring design for OAuth tokens; keep keyring for LLM API keys (never plaintext `.env` written by the UI).
- Login/signup pages are dropped. If cloud accounts/sync are wanted later, that's a thin hosted API (FastAPI + Postgres) added in front — the local-first design doesn't block it.
- Memory upgrades: inject user/session identity (no `user_context.json` file reads), add embedding-based recall alongside the existing recency window.

---

## Part 3 — Roadmap

### Phase 0 — Clean the yard (½ day)
Delete: `integration/communication.py`, `backend_runner.py`, `frontend_enhancer.py`, `status_widget.py`, `logs_page.py`, `src/agents/agent_node.py`, `playwright_music_tools.py`, stray `=1.2.0` file, checked-in `user_context.json`. Consolidate the ~13 root markdown docs.

### Phase 1 — Sentinel Core service (the new spine)
- New `core/` package: FastAPI app, WebSocket event stream, typed event schema (port the `EventType` concept).
- Port `llm_config.py`; add **Groq + Cerebras** providers; keys via keyring; live `reload` endpoint.
- Rebuild the graph: registry pattern + `langgraph-supervisor`/`Command` handoffs, typed state, streaming.
- Port API tools (browser, email, meeting, notes, Spotify half of music) onto async httpx with clean error surfaces (no tracebacks in tool output).
- SQLite storage: settings, history, memory (+ TTL), sqlite-vec semantic recall.
- Exit criteria: text chat with full agent capabilities works end-to-end over WebSocket, tokens streaming — no voice, no GUI yet.

### Phase 2 — Voice pipeline v2
- Async pipeline: Porcupine wake word → silero-vad segmentation → Groq Whisper STT → graph → sentence-streamed TTS with barge-in.
- Runs inside Core; all voice states are WebSocket events.
- Exit criteria: wake-to-first-spoken-word under ~1.5s for simple commands.

### Phase 3 — Tauri desktop app
- Tauri 2 + React + TS + Tailwind + shadcn/ui. Views: Home (chat + voice orb + live agent trace), Connections (Spotify/Google OAuth), Settings (providers, per-agent model assignment, voice tuning — live reload), Logs. System-tray mode.
- Exit criteria: full product loop with professional UI, no console windows.

### Phase 4 — Sentinel Windows MCP server
- Standalone repo/package: typed tools for volume, brightness, app launch/close, window management, media control, power, screenshots, notifications — real OS APIs only.
- Core consumes it via MCP; delete `system_tools.py`.
- Exit criteria: works in Sentinel *and* in Claude Desktop as a generic Windows MCP server.

### Phase 5 — Ship it
- PyInstaller-frozen Core as Tauri sidecar; Tauri bundler → MSI/NSIS installer; Tauri updater for auto-update; crash reporting (Sentry) in both processes; first-run onboarding (API keys, mic permission, wake-word test).

### Suggested repo layout
```
sentinel/
  core/            # Python: FastAPI service, graph, voice, tools, storage
  app/             # Tauri 2 + React frontend
  mcp-windows/     # Sentinel Windows MCP server (publishable standalone)
  docs/
```

---

## Part 4 — Sources
- Groq tool use: https://console.groq.com/docs/tool-use · Models: https://console.groq.com/docs/models
- Groq STT (Whisper v3 / v3-turbo): https://console.groq.com/docs/speech-to-text · TTS: https://console.groq.com/docs/text-to-speech
- Cerebras tool calling / models (OpenAI-compatible): https://tokenmix.ai/blog/cerebras-api-key-access-speed-tests-2026
- Windows MCP landscape: https://github.com/mukul975/mcp-windows-automation · https://github.com/mario-andreschak/mcp-windows-desktop-automation · https://learn.microsoft.com/en-us/windows/ai/mcp/overview
- Tauri 2 sidecar pattern: https://v2.tauri.app/develop/sidecar/ · https://github.com/dieharders/example-tauri-v2-python-server-sidecar · https://aiechoes.substack.com/p/building-production-ready-desktop
