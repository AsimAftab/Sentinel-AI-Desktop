# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sentinel AI is a voice-activated desktop AI assistant for Windows:

- **`sentinel_core/`** — async Python service (FastAPI + LangGraph): multi-provider LLM agents, voice pipeline, SQLite storage. The single backend for everything.
- **`app/`** — Tauri 2 + React + TypeScript desktop app. Talks to the core over WebSocket (event stream) + REST (settings/control). In production it spawns the frozen core as a hidden sidecar.
- **`mcp-windows/`** — standalone MCP server (`sentinel-mcp-windows`) exposing Windows system control on real OS APIs; consumed by the core as the System agent, also usable from Claude Desktop.
- **`packaging/`** — PyInstaller specs + build docs for the NSIS installer (see `packaging/README.md` for the 3-step build).

History: this replaced a PyQt5/monolith prototype (see `REBUILD_PLAN.md` and `docs/` for the audit and old design docs).

## Commands

```bash
# Core service (dev)
uv run --group core python -m sentinel_core        # serves 127.0.0.1:8721

# Desktop app (dev; expects a dev core running)
cd app && npm run tauri dev

# Quality
uv run lint        # ruff check .
uv run format      # ruff format . (sole formatter)
uv run typecheck   # pyright

# Installer build — see packaging/README.md (freeze core, freeze MCP exe, tauri build)
```

There is no formal test suite. Verify by driving the running service: `curl http://127.0.0.1:8721/health`, `POST /chat {"text": ...}`, or a WebSocket client for streaming/voice events.

## Architecture

### Core (`sentinel_core/`)

- `config.py` — layered settings: env (+ `.env` at repo root or `%LOCALAPPDATA%\SentinelAI\`) + SQLite overrides merged via `apply_overrides`. Secrets via `get_secret`: env first, then Windows Credential Manager (service `sentinel-ai`). All user data lives in `%LOCALAPPDATA%\SentinelAI\` (`data_dir()`).
- `llm.py` — `LLMManager`: providers groq/cerebras/azure/openai/ollama/zhipu via a factory registry (OpenAI-compatible ones share one factory with `base_url`). Per-agent provider/temperature, instance caching, ordered fallback, hot reload. The Responder agent rides `FAST_MODELS`; the Supervisor deliberately does not (routing quality).
- `agents/registry.py` — declarative `AGENT_REGISTRY` (python tool modules; ~13 agents: Browser, Music, Meeting, Email, Notes, Productivity, Documents, Memory, Screen, Computer, MeetingNotes, Coder, Messenger) + `MCP_AGENT_REGISTRY` (MCP servers: BrowserActions via `npx @playwright/mcp --browser msedge`; Files + System split from `sentinel-mcp-windows` by `tool_prefixes` — one spawned process, multiple agents). **Adding an agent = one entry here** + a tools module exposing `TOOLS`. Import/spawn failures skip the agent with a warning; the service always boots.
- `agents/graph.py` — LangGraph: supervisor (structured `RouteDecision` output; loop supervisor → agent → supervisor → respond). Guards: `MAX_HOPS`, per-agent timeouts (`AGENT_TIMEOUTS` for long-running agents like Coder/MeetingNotes, 45s default), recursion limits, tool budgets (3 for API agents, open-but-no-thrash for interactive ones). Supervisor rules learned the hard way: never invent live data; judge capabilities only from the live agent list (not remembered refusals); never re-dispatch after success (duplicates side effects); pass structured tool output (trees/listings) through VERBATIM. Prompts carry the current local date-time.
- `service.py` — `ChatService.run_turn`: history from SQLite, translates `astream_events` into typed events, writes + background-embeds memory, injects semantically relevant older memories per turn (`_relevant_context`). Owns the persistent MCP client sessions; `invoke_mcp_tool()` lets REST endpoints call MCP tools without an LLM (GUI workspace launch).
- `store.py` — SQLite (WAL) at `data_dir()/sentinel.db`: settings overrides, sessions/messages, TTL agent memory, notes, reminders, routines, document chunks; sqlite-vec virtual tables (`memory_vec`, `doc_vec`, 384-dim, graceful degrade if the extension fails). Memory context is shared across sessions by design — **it will echo recent test results**; clear the `memory` table for clean A/B tests.
- `embeddings.py` — local fastembed bge-small (warmup at startup, first run downloads ~130MB); `notify.py` — WinRT toasts via PowerShell 5.1 `-EncodedCommand`; `workspaces.py` — JSON shared with the MCP server.
- `app.py` — FastAPI: `/health`, `/settings` (+ live reload), `/secrets` (keyring write), `/voice/*`, `/chat`, `/workspaces` CRUD + open, `/system/apps`, WS `/ws`. `Hub` broadcasts to all sockets. The lifespan runs the reminder/routine scheduler loop (fires toasts + spoken alerts; routines run their prompt through the full graph). CORS must include dev (`localhost:1420`) **and installed** (`http://tauri.localhost`) origins.
- `voice/` — `pipeline.py`: openWakeWord (custom models auto-detected from `data_dir()/wakeword-models/` — e.g. `sentinel.onnx` — else pretrained "Hey Jarvis"; `WAKEWORD_MODEL` env overrides) → chime → silero-VAD-endpointed capture (`vad.py`; energy fallback) → Groq Whisper over a persistent client → graph → sentence-chunked ElevenLabs PCM streaming with barge-in. `CONTINUOUS_LISTENING` defaults off (ambient speech became commands). Latency logged per turn.
- `events.py` — the typed event schema; mirrored in `app/src/lib/types.ts`. Keep them in sync.

### App (`app/src/`)

- `state/store.ts` — zustand store + WebSocket client (auto-reconnect); translates core events into chat messages, streaming text, agent trace, voice state.
- `views/` — Home (chat + voice + trace), Workspaces (app picker + launch), Settings (system-settings-style rows; keys POST to `/secrets`), Connections, Logs (raw event feed).
- Theme = ~14 design tokens in `index.css` (Graphite & Amber). `components/ui.tsx` holds the primitives (Button/Input/Toggle/SettingRow...).
- `src-tauri/lib.rs` — spawns `resources/binaries/sentinel-core/sentinel-core.exe` hidden if bundled (kills it on window close); dev builds skip it. `LICENSE.txt` is the installer's terms page.

### MCP server (`mcp-windows/`)

FastMCP stdio server, 35 tools (audio/display, WinRT radio toggles — never adapter-disable —, apps/windows/workspaces, `fs_*` read-only file navigation, clipboard/wallpaper/recycle-bin/system). Rules: per-call COM init, list-args subprocess only (never `shell=True`), user text via stdin or `-EncodedCommand` (no interpolation), protected-process denylist for close_app, `confirm=True` gates on destructive actions, log to stderr only (stdout is the protocol). The core resolves the exe: `SENTINEL_MCP_WINDOWS_EXE` env → frozen sibling exe → `uv run --project mcp-windows` in dev.

## Gotchas

- **Code changes need a core restart** — `/settings/reload` rebuilds the graph but from already-imported modules.
- **Frozen vs dev paths**: anything touching `sys.frozen`, `data_dir()`, or exe-relative lookups behaves differently in the packaged build; test with the frozen exe before shipping (`packaging/README.md`).
- **CORS**: REST failures from the app while WebSocket works = missing origin in `sentinel_core/app.py`.
- **Voice testing needs a human at the mic**; STT/TTS have no-mic smoke paths (synthesize a wav via pyttsx3 → `stt.transcribe`).
- Picovoice/Porcupine is dead (free tier ended 2026-06-30) — do not reintroduce it.

## Conventions

- Python: ruff (line 100, E/F/I/B), formatter is ruff, pyright for types. Tools never raise — they return short error strings (no tracebacks in LLM-visible output).
- Never write secrets to files; use the keyring (`config.set_secret`) or `%LOCALAPPDATA%\SentinelAI\.env`.
- No AI attribution in commits or PR bodies.
- Work lands via feature branches + PRs to `main`.
- New capability workflow: verify each dependency is actually capable with a live test BEFORE building on it; verify features end-to-end through the running service before merging.
- Releases: bump versions (`tauri.conf.json`, `Cargo.toml`, `package.json`, `sentinel_core/__init__.py`), push a `v*` tag — CI builds the signed installer and a draft GitHub Release with the updater feed; the maintainer publishes.
