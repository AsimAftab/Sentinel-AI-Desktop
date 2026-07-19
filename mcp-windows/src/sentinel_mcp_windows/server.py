"""Sentinel MCP Windows server.

FastMCP stdio server exposing Windows system control tools: volume, brightness,
media keys, app launch/close, window management, system info, screenshots,
lock screen, and power actions.

Notes:
- FastMCP handles the MCP protocol; tools here must be plain sync defs.
- Never print to stdout: it corrupts the stdio MCP protocol. All logging goes
  to stderr via the logging module.
- COM is initialized per call (CoInitialize/CoUninitialize) because the MCP
  runtime may invoke tools from different threads.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import psutil
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("sentinel-mcp-windows")

mcp = FastMCP("sentinel-mcp-windows")

# --- Constants ---

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002
SW_RESTORE = 9

MEDIA_KEYS: dict[str, int] = {
    "play_pause": VK_MEDIA_PLAY_PAUSE,
    "next": VK_MEDIA_NEXT_TRACK,
    "previous": VK_MEDIA_PREV_TRACK,
    "stop": VK_MEDIA_STOP,
}

# Processes that must never be terminated.
PROTECTED_PROCESSES = {
    "explorer.exe",
    "csrss.exe",
    "winlogon.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "system",
}

# Allowed characters in app names passed to launch_app.
APP_NAME_RE = re.compile(r"^[\w .+&()-]+$")


# --- Helpers ---


def _get_endpoint_volume():
    """Return the IAudioEndpointVolume interface for the default speakers.

    Caller is responsible for COM initialization.

    Supports both modern pycaw (GetSpeakers returns an AudioDevice with an
    EndpointVolume property) and the older raw-IMMDevice API.
    """
    from pycaw.pycaw import AudioUtilities

    device = AudioUtilities.GetSpeakers()
    endpoint = getattr(device, "EndpointVolume", None)
    if endpoint is not None:
        return endpoint

    # Legacy pycaw: GetSpeakers returns a raw IMMDevice.
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume

    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def _with_com(fn):
    """Run fn with COM initialized on the current thread (per-call init)."""
    import comtypes

    comtypes.CoInitialize()
    try:
        return fn()
    finally:
        comtypes.CoUninitialize()


def _get_start_apps() -> list[dict[str, str]]:
    """Return installed/startable apps as [{"Name": ..., "AppID": ...}, ...]."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Get-StartApps failed: {result.stderr.strip()[:200]}")
    data = json.loads(result.stdout)
    if isinstance(data, dict):
        data = [data]
    return [
        {"Name": str(a.get("Name", "")), "AppID": str(a.get("AppID", ""))}
        for a in data
        if a.get("Name") and a.get("AppID")
    ]


def _resolve_start_app(
    name: str, apps: list[dict[str, str]] | None = None
) -> tuple[dict[str, str] | None, str]:
    """Resolve an app name against Get-StartApps (exact match, then substring).

    Returns (app, "") on a unique match, or (None, error_message) otherwise.
    """
    name = name.strip()
    if not name or not APP_NAME_RE.match(name):
        return None, "Error: app name contains invalid characters."
    if apps is None:
        apps = _get_start_apps()
    lname = name.lower()
    exact = [a for a in apps if a["Name"].lower() == lname]
    matches = exact or [a for a in apps if lname in a["Name"].lower()]
    if not matches:
        return None, f"No app found matching '{name}'. Try list_apps to see options."
    if len(matches) > 1:
        names = ", ".join(a["Name"] for a in matches[:8])
        return None, f"Ambiguous name '{name}'. Did you mean one of: {names}?"
    return matches[0], ""


def _launch_app_id(app_id: str) -> None:
    """Launch an app by its shell AppID via Explorer (same as the Start menu)."""
    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])


def _enum_visible_windows() -> list[tuple[int, str]]:
    """Return (hwnd, title) for all visible windows with non-empty titles."""
    user32 = ctypes.windll.user32
    results: list[tuple[int, str]] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value.strip():
                    results.append((hwnd, buf.value))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return results


# --- Volume tools ---


@mcp.tool()
def get_volume() -> str:
    """Get the current system master volume level and mute state."""
    try:
        def read():
            vol = _get_endpoint_volume()
            level = round(vol.GetMasterVolumeLevelScalar() * 100)
            muted = bool(vol.GetMute())
            return level, muted

        level, muted = _with_com(read)
        return f"Volume: {level}%{' (muted)' if muted else ''}"
    except Exception as e:
        logger.exception("get_volume failed")
        return f"Error getting volume: {e}"


@mcp.tool()
def set_volume(level: int) -> str:
    """Set the system master volume to a level between 0 and 100."""
    try:
        if not 0 <= level <= 100:
            return "Error: level must be between 0 and 100."

        def write():
            vol = _get_endpoint_volume()
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
            if level > 0:
                vol.SetMute(0, None)

        _with_com(write)
        return f"Volume set to {level}%."
    except Exception as e:
        logger.exception("set_volume failed")
        return f"Error setting volume: {e}"


@mcp.tool()
def set_mute(muted: bool) -> str:
    """Mute (true) or unmute (false) the system master audio."""
    try:
        def _apply() -> bool:
            vol = _get_endpoint_volume()
            if bool(vol.GetMute()) == muted:
                return False
            vol.SetMute(1 if muted else 0, None)
            return True

        changed = _with_com(_apply)
        if not changed:
            return f"Audio is already {'muted' if muted else 'unmuted'} - no change needed."
        return "Audio muted." if muted else "Audio unmuted."
    except Exception as e:
        logger.exception("set_mute failed")
        return f"Error setting mute: {e}"


@mcp.tool()
def adjust_volume(delta: int) -> str:
    """Adjust the master volume by a relative amount (e.g. +10 louder, -10 quieter)."""
    try:
        if not -100 <= delta <= 100:
            return "Error: delta must be between -100 and 100."

        def _apply():
            vol = _get_endpoint_volume()
            current = round(vol.GetMasterVolumeLevelScalar() * 100)
            new = max(0, min(100, current + delta))
            vol.SetMasterVolumeLevelScalar(new / 100, None)
            return current, new

        current, new = _with_com(_apply)
        if current == new:
            return f"Volume unchanged at {current}% (already at the limit)."
        return f"Volume changed from {current}% to {new}%."
    except Exception as e:
        logger.exception("adjust_volume failed")
        return f"Error adjusting volume: {e}"


# --- Brightness tools ---


@mcp.tool()
def get_brightness() -> str:
    """Get the current display brightness level(s)."""
    try:
        import screen_brightness_control as sbc

        levels = sbc.get_brightness()
        if not levels:
            return "No controllable displays found."
        if len(levels) == 1:
            return f"Brightness: {levels[0]}%"
        parts = ", ".join(f"display {i}: {v}%" for i, v in enumerate(levels))
        return f"Brightness: {parts}"
    except Exception as e:
        logger.exception("get_brightness failed")
        return f"Error getting brightness: {e}"


@mcp.tool()
def set_brightness(level: int) -> str:
    """Set display brightness to a level between 0 and 100 (all displays)."""
    try:
        if not 0 <= level <= 100:
            return "Error: level must be between 0 and 100."
        import screen_brightness_control as sbc

        sbc.set_brightness(level)
        return f"Brightness set to {level}%."
    except Exception as e:
        logger.exception("set_brightness failed")
        return f"Error setting brightness: {e}"


# --- Media control ---


@mcp.tool()
def media_control(action: Literal["play_pause", "next", "previous", "stop"]) -> str:
    """Send a media key press: play_pause, next, previous, or stop."""
    try:
        vk = MEDIA_KEYS.get(action)
        if vk is None:
            return f"Error: unknown action '{action}'."
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        return f"Media key '{action}' sent."
    except Exception as e:
        logger.exception("media_control failed")
        return f"Error sending media key: {e}"


# --- App tools ---


@mcp.tool()
def list_apps(query: str = "") -> str:
    """List installed/startable apps, optionally filtered by a case-insensitive query."""
    try:
        apps = _get_start_apps()
        q = query.lower().strip()
        if q:
            apps = [a for a in apps if q in a["Name"].lower()]
        if not apps:
            return f"No apps found matching '{query}'." if query else "No apps found."
        apps = sorted(apps, key=lambda a: a["Name"].lower())[:20]
        return "\n".join(f"{a['Name']} — {a['AppID']}" for a in apps)
    except Exception as e:
        logger.exception("list_apps failed")
        return f"Error listing apps: {e}"


@mcp.tool()
def launch_app(name: str) -> str:
    """Launch an installed app by name (exact match preferred, then substring)."""
    try:
        app, error = _resolve_start_app(name)
        if app is None:
            return error
        _launch_app_id(app["AppID"])
        return f"Launched {app['Name']}."
    except Exception as e:
        logger.exception("launch_app failed")
        return f"Error launching app: {e}"


@mcp.tool()
def close_app(name: str, force: bool = False) -> str:
    """Close all processes matching a name (with or without .exe). force=true kills instead
    of terminating. Critical system processes are protected and refused."""
    try:
        target = name.strip().lower()
        if not target:
            return "Error: empty process name."
        if not target.endswith(".exe"):
            candidates = {target, target + ".exe"}
        else:
            candidates = {target, target.removesuffix(".exe")}

        if candidates & PROTECTED_PROCESSES:
            return f"Refused: '{name}' is a protected system process."

        closed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname in candidates:
                    if pname in PROTECTED_PROCESSES:
                        continue
                    if force:
                        proc.kill()
                    else:
                        proc.terminate()
                    closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if closed == 0:
            return f"No running process found matching '{name}'."
        verb = "Killed" if force else "Terminated"
        return f"{verb} {closed} process(es) matching '{name}'."
    except Exception as e:
        logger.exception("close_app failed")
        return f"Error closing app: {e}"


# --- Window tools ---


@mcp.tool()
def list_windows() -> str:
    """List the titles of all visible top-level windows."""
    try:
        windows = _enum_visible_windows()
        if not windows:
            return "No visible windows found."
        return "\n".join(title for _, title in windows)
    except Exception as e:
        logger.exception("list_windows failed")
        return f"Error listing windows: {e}"


@mcp.tool()
def focus_window(title_substring: str) -> str:
    """Bring the first visible window whose title contains the given substring to the
    foreground (case-insensitive)."""
    try:
        sub = title_substring.strip().lower()
        if not sub:
            return "Error: empty title substring."
        for hwnd, title in _enum_visible_windows():
            if sub in title.lower():
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, SW_RESTORE)
                # Windows refuses SetForegroundWindow from background processes
                # (foreground lock). A synthetic Alt press lifts the restriction;
                # without it this "succeeded" while doing nothing.
                VK_MENU = 0x12
                user32.keybd_event(VK_MENU, 0, 0, 0)
                ok = user32.SetForegroundWindow(hwnd)
                user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
                if not ok:
                    return f"Found '{title}' but Windows refused to bring it forward."
                return f"Focused window: {title}"
        return f"No visible window found containing '{title_substring}'."
    except Exception as e:
        logger.exception("focus_window failed")
        return f"Error focusing window: {e}"


@mcp.tool()
def window_control(
    title_substring: str, action: Literal["minimize", "maximize", "restore"]
) -> str:
    """Minimize, maximize, or restore the first visible window whose title contains
    the given substring (case-insensitive)."""
    SW_MINIMIZE, SW_MAXIMIZE = 6, 3
    show = {"minimize": SW_MINIMIZE, "maximize": SW_MAXIMIZE, "restore": SW_RESTORE}
    try:
        sub = title_substring.strip().lower()
        if not sub:
            return "Error: empty title substring."
        for hwnd, title in _enum_visible_windows():
            if sub in title.lower():
                ctypes.windll.user32.ShowWindow(hwnd, show[action])
                return f"{action.capitalize()}d window: {title}"
        return f"No visible window found containing '{title_substring}'."
    except Exception as e:
        logger.exception("window_control failed")
        return f"Error controlling window: {e}"


# --- System info ---


@mcp.tool()
def system_info() -> str:
    """Get a summary of CPU, RAM, disk (C:), and battery status."""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        lines = [
            f"CPU: {cpu}%",
            f"RAM: {mem.used / 1024**3:.1f} / {mem.total / 1024**3:.1f} GB "
            f"({mem.percent}%)",
            f"Disk C:: {disk.used / 1024**3:.1f} / {disk.total / 1024**3:.1f} GB "
            f"({disk.percent}%)",
        ]
        battery = psutil.sensors_battery()
        if battery is not None:
            state = "plugged in" if battery.power_plugged else "on battery"
            lines.append(f"Battery: {round(battery.percent)}% ({state})")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("system_info failed")
        return f"Error getting system info: {e}"


# --- Screenshot ---


@mcp.tool()
def take_screenshot() -> str:
    """Capture all screens to a PNG in the temp directory and return the file path."""
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab(all_screens=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{tempfile.gettempdir()}\\sentinel_screenshot_{timestamp}.png"
        img.save(path, "PNG")
        return f"Screenshot saved to {path}"
    except Exception as e:
        logger.exception("take_screenshot failed")
        return f"Error taking screenshot: {e}"


# --- Lock / power ---


@mcp.tool()
def lock_screen() -> str:
    """Lock the Windows workstation immediately."""
    try:
        if not ctypes.windll.user32.LockWorkStation():
            return "Error: LockWorkStation call failed."
        return "Workstation locked."
    except Exception as e:
        logger.exception("lock_screen failed")
        return f"Error locking screen: {e}"


@mcp.tool()
def power_action(
    action: Literal["sleep", "shutdown", "restart"], confirm: bool = False
) -> str:
    """Sleep, shut down, or restart the computer. Requires confirm=true to execute.
    Shutdown/restart have a 5-second delay."""
    try:
        if not confirm:
            return f"Pass confirm=true to actually {action}."
        if action == "sleep":
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], timeout=10
            )
            return "Sleeping the computer."
        if action == "shutdown":
            subprocess.run(["shutdown", "/s", "/t", "5"], timeout=10)
            return "Shutting down in 5 seconds."
        if action == "restart":
            subprocess.run(["shutdown", "/r", "/t", "5"], timeout=10)
            return "Restarting in 5 seconds."
        return f"Error: unknown action '{action}'."
    except Exception as e:
        logger.exception("power_action failed")
        return f"Error performing power action: {e}"


# --- Clipboard ---


@mcp.tool()
def clipboard_read() -> str:
    """Read the current text content of the clipboard."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return f"Error reading clipboard: {result.stderr.strip()[:200]}"
        text = result.stdout
        if not text.strip():
            return "Clipboard is empty (or contains non-text content)."
        if len(text) > 8000:
            return f"{text[:8000]}\n…[truncated: clipboard has {len(text)} characters]"
        return text
    except Exception as e:
        logger.exception("clipboard_read failed")
        return f"Error reading clipboard: {e}"


@mcp.tool()
def clipboard_write(text: str) -> str:
    """Copy the given text to the clipboard."""
    try:
        # Text is passed via stdin — never interpolated into the command string.
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Set-Clipboard -Value ([Console]::In.ReadToEnd())",
            ],
            input=text,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return f"Error writing clipboard: {result.stderr.strip()[:200]}"
        return f"Copied {len(text)} characters to the clipboard."
    except Exception as e:
        logger.exception("clipboard_write failed")
        return f"Error writing clipboard: {e}"


# --- URL / wallpaper / recycle bin ---


@mcp.tool()
def open_url(url: str) -> str:
    """Open an http/https URL in the default browser."""
    try:
        url = url.strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return "Error: only http:// and https:// URLs are allowed."
        os.startfile(url)  # noqa: S606 - opens in default browser
        return f"Opened {url} in the default browser."
    except Exception as e:
        logger.exception("open_url failed")
        return f"Error opening URL: {e}"


@mcp.tool()
def set_wallpaper(image_path: str) -> str:
    """Set the desktop wallpaper to a local jpg/jpeg/png/bmp image."""
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE_SENDCHANGE = 3
    try:
        path = Path(os.path.expandvars(os.path.expanduser(image_path.strip()))).absolute()
        if not path.is_file():
            return f"Error: image file does not exist: {path}"
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
            return "Error: wallpaper must be a .jpg, .jpeg, .png, or .bmp file."
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(path), SPIF_UPDATEINIFILE_SENDCHANGE
        )
        if not ok:
            return "Error: SystemParametersInfoW call failed."
        return f"Wallpaper set to {path.name}."
    except Exception as e:
        logger.exception("set_wallpaper failed")
        return f"Error setting wallpaper: {e}"


@mcp.tool()
def empty_recycle_bin(confirm: bool = False) -> str:
    """Empty the Recycle Bin. Requires confirm=true to execute."""
    SHERB_NOCONFIRMATION_NOSOUND = 0x1 | 0x4
    ALREADY_EMPTY_RESULTS = {-2147418113, 0x8000FFFF, -2147024894, 0x80070002}
    try:
        if not confirm:
            return "Pass confirm=true to actually empty the Recycle Bin."
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, SHERB_NOCONFIRMATION_NOSOUND
        )
        if result == 0:
            return "Recycle Bin emptied."
        if result in ALREADY_EMPTY_RESULTS:
            return "Recycle Bin is already empty."
        return f"Error: SHEmptyRecycleBinW returned HRESULT {result:#010x}."
    except Exception as e:
        logger.exception("empty_recycle_bin failed")
        return f"Error emptying Recycle Bin: {e}"


# --- Tool modules ---

# Imported for their @mcp.tool() registrations (they import `mcp` from this module).
from . import files, night_light, radios, theme, workspaces  # noqa: E402,F401


def main() -> None:
    """Entry point: run the FastMCP server over stdio."""
    logger.info("Starting sentinel-mcp-windows stdio server")
    mcp.run()


if __name__ == "__main__":
    main()
