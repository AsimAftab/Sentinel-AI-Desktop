# sentinel-mcp-windows

A standalone MCP (Model Context Protocol) server exposing **35 Windows control tools** over
stdio. Built on proper Windows APIs: pycaw (audio), the WinRT Radio API (WiFi/Bluetooth),
screen-brightness-control, psutil, ctypes/user32, and PIL — no pyautogui, no hardcoded
coordinates, no `shell=True`.

Requires Windows and Python 3.11+.

## Tools (35)

**Audio & display**
| Tool | Description |
| --- | --- |
| `get_volume` / `set_volume(level)` / `set_mute(muted)` | System master volume (0-100) and mute |
| `get_brightness` / `set_brightness(level)` | Display brightness (0-100) |
| `media_control(action)` | Media keys: `play_pause`, `next`, `previous`, `stop` |
| `set_wallpaper(image_path)` | Set the desktop wallpaper |

**Radios** (WinRT `Windows.Devices.Radios` — the software switch; hardware is never disabled)
| Tool | Description |
| --- | --- |
| `get_radios` | List radios (WiFi, Bluetooth, …) and their on/off state |
| `set_wifi(enabled)` / `set_bluetooth(enabled)` | Toggle the radio on/off |

**Apps, windows & workspaces**
| Tool | Description |
| --- | --- |
| `list_apps(query)` | List installed/startable apps (Get-StartApps) |
| `launch_app(name)` | Launch an app by name via `shell:AppsFolder` |
| `close_app(name, force)` | Terminate processes by name (critical system processes protected) |
| `list_windows` / `focus_window(title_substring)` | List visible windows; bring one to foreground |
| `workspace_list` / `workspace_open(name)` / `workspace_save(...)` / `workspace_delete(name)` | Named app groups ("dev mode") stored in `%LOCALAPPDATA%\SentinelAI\workspaces.json` |

**Files** (read-only + open; no delete/move/write)
| Tool | Description |
| --- | --- |
| `fs_known_folders` | Resolve Desktop/Documents/Downloads/Pictures/Music/Videos |
| `fs_list(path)` / `fs_tree(path, max_depth)` | Directory listing / `tree`-style ASCII tree |
| `fs_find(name_pattern, root, max_results)` | Bounded filename search with noise-dir pruning |
| `fs_open(path)` / `fs_open_folder(path)` | Open with default app / in Explorer |
| `fs_info(path)` / `fs_read_text(path, max_chars)` | File metadata / text preview |

**System**
| Tool | Description |
| --- | --- |
| `system_info` | CPU, RAM, disk C:, battery |
| `take_screenshot` | Capture all screens to a temp PNG, returns path |
| `clipboard_read` / `clipboard_write(text)` | Read/set the clipboard |
| `open_url(url)` | Open an http(s) URL in the default browser |
| `empty_recycle_bin(confirm)` | Refuses unless `confirm=true` |
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
