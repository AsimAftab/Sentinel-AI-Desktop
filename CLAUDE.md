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
- `agents/registry.py` — declarative `AGENT_REGISTRY` (python tool modules) + `MCP_AGENT_REGISTRY` (MCP servers). **Adding an agent = one entry here** + a tools module exposing `TOOLS`. Import failures skip the agent with a warning; the service always boots.
- `agents/graph.py` — LangGraph: supervisor (structured `RouteDecision` output; loop supervisor → agent → supervisor → respond). Guards: `MAX_HOPS`, 45s per-agent timeout, recursion limit, 3-tool budget in prompts. The supervisor composes the final reply in its FINISH decision (fast path); the `respond` node LLM (tagged `"final"`, streams tokens) is the fallback. Anti-hallucination rule: live data must come from an agent tool call.
- `service.py` — `ChatService.run_turn`: history from SQLite, translates `astream_events` into typed events, writes memory. Owns the persistent MCP client sessions (spawn once, `aclose` on shutdown). Graph is built lazily/async and rebuilt on settings reload.
- `store.py` — SQLite (WAL) at `data_dir()/sentinel.db`: settings overrides, sessions/messages, TTL agent memory, notes. Memory context (`context_block`) is shared across sessions by design — beware of it echoing recent test results when verifying behavior (clear the `memory` table for clean tests).
- `app.py` — FastAPI: `/health`, `/settings` (+ live reload), `/secrets` (keyring write), `/voice/start|stop|status`, `/chat`, WS `/ws`. `Hub` broadcasts voice events to all sockets. CORS must include dev (`localhost:1420`) **and installed** (`http://tauri.localhost`) origins.
- `voice/` — `pipeline.py` orchestrates: openWakeWord ("Hey Jarvis"; `WAKEWORD_MODEL` env for a custom .onnx) → chime → energy-endpointed capture → Groq Whisper (`whisper-large-v3-turbo`) → graph → sentence-chunked ElevenLabs PCM streaming with barge-in (wake word during playback cancels speech). `CONTINUOUS_LISTENING` defaults off (ambient speech became commands).
- `events.py` — the typed event schema; mirrored in `app/src/lib/types.ts`. Keep them in sync.

### App (`app/src/`)

- `state/store.ts` — zustand store + WebSocket client (auto-reconnect); translates core events into chat messages, streaming text, agent trace, voice state.
- `views/` — Home (chat + voice + trace), Settings (system-settings-style rows; keys POST to `/secrets`), Connections, Logs (raw event feed).
- Theme = ~14 design tokens in `index.css` (Graphite & Amber). `components/ui.tsx` holds the primitives (Button/Input/Toggle/SettingRow...).
- `src-tauri/lib.rs` — spawns `resources/binaries/sentinel-core/sentinel-core.exe` hidden if bundled (kills it on window close); dev builds skip it. `LICENSE.txt` is the installer's terms page.

### MCP server (`mcp-windows/`)

FastMCP stdio server, 15 tools. Rules: per-call COM init, list-args subprocess only (never `shell=True`), protected-process denylist for close_app, `confirm=True` gate on power actions, log to stderr only (stdout is the protocol). The core resolves the exe: `SENTINEL_MCP_WINDOWS_EXE` env → frozen sibling exe → `uv run --project mcp-windows` in dev.

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
- Work lands via feature branches + PRs to `main` (user merges).
