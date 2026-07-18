# sentinel-mcp-windows

A standalone MCP (Model Context Protocol) server exposing Windows system control tools over
stdio. Replaces the legacy pyautogui-based `system_tools.py` with proper Windows APIs:
pycaw (audio), screen-brightness-control, psutil, ctypes/user32, and PIL — no pyautogui,
no hardcoded coordinates, no `shell=True`.

Requires Windows and Python 3.11+.

## Tools

| Tool | Description |
| --- | --- |
| `get_volume` / `set_volume(level)` / `set_mute(muted)` | System master volume (0-100) and mute |
| `get_brightness` / `set_brightness(level)` | Display brightness (0-100) |
| `media_control(action)` | Media keys: `play_pause`, `next`, `previous`, `stop` |
| `list_apps(query)` | List installed/startable apps (Get-StartApps) |
| `launch_app(name)` | Launch an app by name via `shell:AppsFolder` |
| `close_app(name, force)` | Terminate/kill processes by name (critical system processes protected) |
| `list_windows` / `focus_window(title_substring)` | List visible windows; bring one to foreground |
| `system_info` | CPU, RAM, disk C:, battery |
| `take_screenshot` | Capture all screens to a temp PNG, returns path |
| `lock_screen` | Lock the workstation |
| `power_action(action, confirm)` | `sleep` / `shutdown` / `restart` — refuses unless `confirm=true` |

## Usage with Claude Desktop

Add to `claude_desktop_config.json` (Windows:
`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "sentinel-windows": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "C:\\Users\\asima\\Desktop\\Projects\\Agentic AI\\Sentinel-AI-Desktop\\mcp-windows",
        "sentinel-mcp-windows"
      ]
    }
  }
}
```

## Usage with any MCP client

The server speaks MCP over stdio. Launch it with:

```bash
uv run --project <path-to-mcp-windows> sentinel-mcp-windows
```

or, after `pip install .` in this directory, simply:

```bash
sentinel-mcp-windows
```

Point your MCP client's stdio transport at that command.
