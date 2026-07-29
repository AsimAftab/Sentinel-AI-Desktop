# sentinel-mcp-windows

A standalone MCP (Model Context Protocol) server exposing **63 Windows control tools** over
stdio. Built on proper Windows APIs: pycaw + `IPolicyConfig` (audio), the WinRT Radio and
MediaTransportControls APIs, Win32 `BluetoothAPIs.dll`, screen-brightness-control, psutil,
ctypes/user32, and PIL — no pyautogui, no hardcoded coordinates, no `shell=True`.

Requires Windows and Python 3.11+.

## Tools (63)

**Audio**
| Tool | Description |
| --- | --- |
| `get_volume` / `set_volume(level)` / `set_mute(muted)` | System master volume (0-100) and mute |
| `adjust_volume(delta)` | Relative volume change (e.g. `-10`), clamped to 0-100 |
| `media_control(action)` | Media keys: `play_pause`, `next`, `previous`, `stop` — blind fallback for players with no media session |
| `audio_devices(kind)` | List active output/input devices, marking the default |
| `audio_set_device(name, kind)` | Switch the default playback/recording device (`IPolicyConfig`) |
| `audio_apps` | Apps currently using audio, with volume and mute state |
| `audio_set_app_volume(app, level, muted)` | Per-app mixer — change one app without touching system volume |
| `audio_mic` / `audio_set_mic(level, muted)` | Microphone level and mute |

**Now playing** (WinRT `GlobalSystemMediaTransportControls` — every player, no API key)
| Tool | Description |
| --- | --- |
| `audio_now_playing` | Title/artist/album/status for each media session (Spotify, YouTube Music in a browser, VLC, …) |
| `audio_media(action, app)` | `play`/`pause`/`toggle`/`next`/`previous`/`stop` aimed at a named player |

**Display & desktop**
| Tool | Description |
| --- | --- |
| `get_brightness` / `set_brightness(level)` | Display brightness (0-100) |
| `get_theme` / `set_theme(mode)` | Windows dark/light theme |
| `get_night_light` / `set_night_light(enabled)` | Night light (blue-light reduction) |
| `set_wallpaper(image_path)` | Set the desktop wallpaper |
| `disp_list` | Monitors with resolution, refresh rate and position |
| `disp_mode(mode)` | Win+P modes via `DisplaySwitch.exe`; refuses second-screen modes when only one monitor is attached |
| `disp_virtual_desktop(action)` | next/previous/new/close desktop, or show desktop |
| `disp_screenshot_window(title_substring)` | Capture one window instead of the whole screen |
| `notify(title, message)` | Windows toast notification |
| `clipboard_history(limit)` | Recent Win+V entries — returns whatever was copied, so treat as sensitive |

**Radios** (WinRT `Windows.Devices.Radios` — the software switch; hardware is never disabled)
| Tool | Description |
| --- | --- |
| `get_radios` | List radios (WiFi, Bluetooth, …) and their on/off state |
| `set_wifi(enabled)` / `set_bluetooth(enabled)` | Toggle the radio on/off |

**Bluetooth devices** (Win32 `BluetoothAPIs.dll`; pairing new devices is out of scope)
| Tool | Description |
| --- | --- |
| `bluetooth_devices` | List paired devices and their connected state |
| `bluetooth_connect(name)` / `bluetooth_disconnect(name)` | Connect/disconnect a paired audio device (A2DP/HFP) |

**Apps, windows & workspaces**
| Tool | Description |
| --- | --- |
| `list_apps(query)` | List installed/startable apps (Get-StartApps) |
| `launch_app(name)` | Launch an app by name via `shell:AppsFolder` |
| `close_app(name, force)` | Terminate processes by name (critical system processes protected) |
| `list_windows` / `focus_window(title_substring)` | List visible windows; bring one to foreground |
| `window_control(title_substring, action)` | `minimize` / `maximize` / `restore` a window |
| `workspace_list` / `workspace_open(name)` / `workspace_save(...)` / `workspace_delete(name)` | Named app groups ("dev mode") stored in `%LOCALAPPDATA%\SentinelAI\workspaces.json` |

**Files — reading**
| Tool | Description |
| --- | --- |
| `fs_known_folders` | Resolve Desktop/Documents/Downloads/Pictures/Music/Videos |
| `fs_list(path)` / `fs_tree(path, max_depth)` | Directory listing / `tree`-style ASCII tree |
| `fs_find(name_pattern, root, max_results)` | Bounded filename search with noise-dir pruning |
| `fs_open(path)` / `fs_open_folder(path)` | Open with default app / in Explorer |
| `fs_info(path)` / `fs_read_text(path, max_chars)` | File metadata / text preview |

**Files — organising.** Every target must resolve inside the user profile; system and program
directories are refused; nothing is overwritten without an explicit flag; and delete means the
Recycle Bin, never `os.remove`.

| Tool | Description |
| --- | --- |
| `fs_new_folder(path)` | Create a folder and any missing parents |
| `fs_rename(path, new_name)` | Rename in place — refuses path separators so it can't become a move |
| `fs_copy(source, destination, overwrite)` | Copy a file or folder; refuses to replace unless `overwrite=true` |
| `fs_move(source, destination, overwrite)` | Move a file or folder; same overwrite rule |
| `fs_delete(path, confirm)` | `SHFileOperationW` + `FOF_ALLOWUNDO` → Recycle Bin, recoverable; refuses unless `confirm=true` |

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

## Freezing to a single exe

Always point PyInstaller at `mcp_entry.py`, **never** at `src/sentinel_mcp_windows/server.py`.
Freezing `server.py` directly collapses the package, so the `from . import ...` at the
bottom of the module raises `ImportError: attempted relative import with no known parent
package` and the exe dies on startup — taking every tool with it.

```bash
uv run --with pyinstaller pyinstaller --onefile --name sentinel-mcp-windows --console \
  --paths src --collect-submodules sentinel_mcp_windows \
  --collect-data screen_brightness_control mcp_entry.py --distpath dist --noconfirm

# Verify the frozen exe actually serves tools (real MCP handshake + tools/list):
python ../packaging/smoke_mcp.py dist/sentinel-mcp-windows.exe
```
