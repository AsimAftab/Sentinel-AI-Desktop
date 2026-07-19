# Repository Guidelines

## Project Structure

- `sentinel_core/` — async Python service (FastAPI + LangGraph): LLM providers, agents/tools, voice pipeline, SQLite storage.
- `app/` — Tauri 2 + React + TypeScript desktop app (WebSocket/REST client of the core).
- `mcp-windows/` — standalone Windows system-control MCP server (own uv project).
- `packaging/` — PyInstaller specs and installer build steps (`packaging/README.md`).
- `docs/` — historical design docs from the pre-rebuild prototype.

## Build, Test, and Development Commands

- `uv run --group core python -m sentinel_core` — run the core service (port 8721).
- `cd app && npm run tauri dev` — run the desktop app against a dev core.
- `uv run lint` / `uv run format` / `uv run typecheck` — ruff check, ruff format, pyright.
- `cd app && npm run build` — typecheck + build the frontend.
- Installer: follow `packaging/README.md` (freeze core, freeze MCP exe, `npm run tauri build`).

No formal test suite: verify against the running service (`/health`, `/chat`, WebSocket events).

## Coding Style

- Python 3.11+, ruff line length 100, rules E/F/I/B; ruff is the sole formatter; pyright for types.
- Agent tools return short human-readable strings and never raise or leak tracebacks.
- Secrets go to the Windows Credential Manager (`sentinel_core.config.set_secret`) — never into tracked files.
- TypeScript: keep core event types in `app/src/lib/types.ts` in sync with `sentinel_core/events.py`.

## Commit & PR Conventions

- Feature branches + PRs to `main`.
- Verify new dependencies with a live capability test before building on them; verify features end-to-end against the running service before merging.
- Imperative commit subjects with a short body of concrete changes.
- No AI attribution (no Co-Authored-By bots, no generated-with footers).
