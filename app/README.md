# Sentinel AI — Desktop App

Tauri 2 + React + TypeScript client for the Sentinel Core service.

## Development

```bash
npm install
npm run tauri dev     # expects a dev core: uv run --group core python -m sentinel_core
```

- `src/state/store.ts` — zustand store + WebSocket client (connects to `ws://127.0.0.1:8721/ws`, auto-reconnects)
- `src/lib/types.ts` — event schema; keep in sync with `sentinel_core/events.py`
- `src/views/` — Assistant (chat + voice + agent trace), Settings, Connections, Activity Log
- `src/index.css` — the entire theme lives in ~14 design tokens (Graphite & Amber)
- `src-tauri/lib.rs` — spawns the bundled frozen core as a hidden sidecar in packaged builds; dev builds expect the core running separately
- `src-tauri/LICENSE.txt` — terms shown by the NSIS installer

## Production build

See `../packaging/README.md` — freeze the core and MCP server first, then `npm run tauri build`.
