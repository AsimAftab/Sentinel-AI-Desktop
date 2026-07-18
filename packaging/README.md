# Building the Sentinel AI installer

Three artifacts, built in order:

## 1. Frozen core service (PyInstaller, onedir)

```bash
cd packaging
uv run --group core --group package pyinstaller sentinel-core.spec --noconfirm
# → packaging/dist/sentinel-core/ (~260 MB)
```

## 2. Frozen Windows MCP server (single exe)

```bash
cd mcp-windows
uv run --with pyinstaller pyinstaller --onefile --name sentinel-mcp-windows --console \
  --collect-data screen_brightness_control src/sentinel_mcp_windows/server.py \
  --distpath dist --noconfirm
# → mcp-windows/dist/sentinel-mcp-windows.exe (~25 MB)
```

## 3. Desktop app + NSIS installer (Tauri)

```bash
# Assemble: the MCP exe sits next to the core exe; the whole folder becomes a Tauri resource
cp mcp-windows/dist/sentinel-mcp-windows.exe packaging/dist/sentinel-core/
mkdir -p app/src-tauri/binaries
cp -r packaging/dist/sentinel-core app/src-tauri/binaries/

cd app && npm run tauri build
# → app/src-tauri/target/release/bundle/nsis/Sentinel AI_<version>_x64-setup.exe
```

## Runtime layout (installed)

- The Tauri shell spawns `resources/binaries/sentinel-core/sentinel-core.exe`
  hidden on launch and kills it when the window closes (`app/src-tauri/src/lib.rs`).
- The core finds `sentinel-mcp-windows.exe` as a sibling of its own exe
  (`sentinel_core/agents/registry.py:_windows_mcp_command`), or via the
  `SENTINEL_MCP_WINDOWS_EXE` env override.
- Config/secrets: Windows Credential Manager (service `sentinel-ai`) +
  optional `.env` in `%LOCALAPPDATA%\SentinelAI\` or next to the core exe.
- All data (SQLite, wake-word models, tokens) lives in `%LOCALAPPDATA%\SentinelAI\`.

## Not yet wired (needs accounts/keys)

- **Auto-update**: Tauri updater plugin needs a signing keypair and a release
  feed (GitHub Releases works). Add once the repo has a public release home.
- **Crash reporting**: Sentry SDK in core + app needs a DSN.
