"""Monitors, virtual desktops, window capture, notifications and clipboard history.

Deliberate mechanism choices:
- Multi-monitor layout goes through DisplaySwitch.exe, the first-party tool the
  Win+P flyout drives. Setting modes through ChangeDisplaySettingsEx by hand is
  far easier to get wrong on mixed-DPI setups.
- Virtual desktops use the documented Win+Ctrl+arrow shortcuts rather than
  IVirtualDesktopManager, whose COM interface IDs change with every Windows
  build and would break on update.
- Toast XML is passed via -EncodedCommand (UTF-16LE base64) and XML-escaped, so
  user text is never interpolated into a command line. Same approach as
  sentinel_core/notify.py.

Agent routing note: only the disp_* tools go to the Display agent. `notify` and
`clipboard_history` live here for implementation reasons but, being unprefixed,
are claimed by the System catch-all alongside clipboard_read/clipboard_write —
so they are described in the System agent's description, not Display's.
"""

from __future__ import annotations

import base64
import ctypes
import logging
import subprocess
import tempfile
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Literal
from xml.sax.saxutils import escape

from .server import _enum_visible_windows, mcp

logger = logging.getLogger("sentinel-mcp-windows.display")

WINDOWS_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
DISPLAY_SWITCH = r"C:\Windows\System32\DisplaySwitch.exe"

# DisplaySwitch flags, exactly as the Win+P flyout uses them.
_DISPLAY_MODES = {
    "internal": "/internal",
    "clone": "/clone",
    "duplicate": "/clone",
    "extend": "/extend",
    "external": "/external",
}

_VK = {
    "win": 0x5B,
    "ctrl": 0x11,
    "left": 0x25,
    "right": 0x27,
    "d": 0x44,
    "f4": 0x73,
}
_KEYEVENTF_KEYUP = 0x0002

# Chords for virtual-desktop actions; each is a fixed literal, never user input.
_DESKTOP_CHORDS = {
    "next": ("win", "ctrl", "right"),
    "previous": ("win", "ctrl", "left"),
    "new": ("win", "ctrl", "d"),
    "close": ("win", "ctrl", "f4"),
    "show_desktop": ("win", "d"),
}

_DISPLAY_DEVICE_ACTIVE = 0x1
_ENUM_CURRENT_SETTINGS = -1

# WinRT type accelerators, too long to inline inside the script literal.
_CLIPBOARD_TYPE = (
    "[Windows.ApplicationModel.DataTransfer.Clipboard,"
    "Windows.ApplicationModel,ContentType=WindowsRuntime]"
)
_CLIPBOARD_RESULT_TYPE = (
    "[Windows.ApplicationModel.DataTransfer.ClipboardHistoryItemsResult,"
    "Windows.ApplicationModel,ContentType=WindowsRuntime]"
)


class _DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


class _DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", ctypes.c_long),
        ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


def _active_displays() -> int:
    """Number of attached, active display devices."""
    user32 = ctypes.windll.user32
    count = 0
    index = 0
    while True:
        device = _DISPLAY_DEVICEW()
        device.cb = ctypes.sizeof(_DISPLAY_DEVICEW)
        if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        index += 1
        if device.StateFlags & _DISPLAY_DEVICE_ACTIVE:
            count += 1
    return count


def _tap(*keys: str) -> None:
    """Press keys in order and release them in reverse (a chord)."""
    user32 = ctypes.windll.user32
    codes = [_VK[k] for k in keys]
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, _KEYEVENTF_KEYUP, 0)


@mcp.tool()
def disp_list() -> str:
    """List connected monitors with resolution, refresh rate and which is primary."""
    try:
        user32 = ctypes.windll.user32
        lines: list[str] = []
        index = 0
        while True:
            device = _DISPLAY_DEVICEW()
            device.cb = ctypes.sizeof(_DISPLAY_DEVICEW)
            if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
                break
            index += 1
            if not device.StateFlags & _DISPLAY_DEVICE_ACTIVE:
                continue

            mode = _DEVMODEW()
            mode.dmSize = ctypes.sizeof(_DEVMODEW)
            detail = ""
            if user32.EnumDisplaySettingsW(
                device.DeviceName, _ENUM_CURRENT_SETTINGS, ctypes.byref(mode)
            ):
                detail = f" — {mode.dmPelsWidth}x{mode.dmPelsHeight} @ {mode.dmDisplayFrequency}Hz"
                if mode.dmPositionX or mode.dmPositionY:
                    detail += f", at ({mode.dmPositionX}, {mode.dmPositionY})"
            primary = " (primary)" if mode.dmPositionX == 0 and mode.dmPositionY == 0 else ""
            lines.append(f"- {device.DeviceString}{detail}{primary}")

        if not lines:
            return "No active displays found."
        header = f"{len(lines)} display{'s' if len(lines) > 1 else ''}:"
        return "\n".join([header, *lines])
    except Exception as e:
        logger.exception("disp_list failed")
        return f"Error listing displays: {e}"


@mcp.tool()
def disp_mode(mode: Literal["internal", "clone", "duplicate", "extend", "external"]) -> str:
    """Set the multi-monitor mode, like the Win+P menu.

    internal = this screen only, clone/duplicate = mirror, extend = span both,
    external = second screen only.

    Refuses the modes that need a second monitor when only one is attached,
    because switching output to a display that is not there leaves a black
    screen the user cannot easily undo.
    """
    try:
        normalized = mode.strip().lower()
        flag = _DISPLAY_MODES.get(normalized)
        if flag is None:
            return f"Error: mode must be one of {', '.join(sorted(_DISPLAY_MODES))}."
        if not Path(DISPLAY_SWITCH).exists():
            return "Error: DisplaySwitch.exe is not available on this system."

        if normalized in ("external", "extend", "clone", "duplicate"):
            attached = _active_displays()
            if attached < 2:
                risk = (
                    " and would blank this screen"
                    if normalized == "external"
                    else " and would change nothing"
                )
                return (
                    f"Only one display is attached, so '{normalized}' needs a second "
                    f"monitor{risk}. Connect one first."
                )

        subprocess.Popen([DISPLAY_SWITCH, flag])
        friendly = {
            "internal": "this screen only",
            "clone": "duplicated",
            "duplicate": "duplicated",
            "extend": "extended across displays",
            "external": "second screen only",
        }[mode.strip().lower()]
        return f"Display mode set to {friendly}."
    except Exception as e:
        logger.exception("disp_mode failed")
        return f"Error setting display mode: {e}"


@mcp.tool()
def disp_virtual_desktop(
    action: Literal["next", "previous", "new", "close", "show_desktop"],
) -> str:
    """Switch, create or close a virtual desktop, or show the desktop.

    close only closes the current virtual desktop; its windows move to the next
    one and nothing is lost.
    """
    try:
        chord = _DESKTOP_CHORDS.get(action.strip().lower())
        if chord is None:
            return f"Error: action must be one of {', '.join(sorted(_DESKTOP_CHORDS))}."
        _tap(*chord)
        described = {
            "next": "Switched to the next virtual desktop.",
            "previous": "Switched to the previous virtual desktop.",
            "new": "Created a new virtual desktop.",
            "close": "Closed the current virtual desktop.",
            "show_desktop": "Showing the desktop.",
        }[action.strip().lower()]
        return described
    except Exception as e:
        logger.exception("disp_virtual_desktop failed")
        return f"Error controlling virtual desktops: {e}"


@mcp.tool()
def disp_screenshot_window(title_substring: str) -> str:
    """Screenshot a single window by title, instead of the whole screen."""
    try:
        query = title_substring.strip().lower()
        if not query:
            return "Error: a window title substring is required."
        matches = [(h, t) for h, t in _enum_visible_windows() if query in t.lower()]
        if not matches:
            return f"No visible window matching '{title_substring}'."

        hwnd, title = matches[0]
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return f"Could not read the bounds of '{title}'."
        box = (rect.left, rect.top, rect.right, rect.bottom)
        if box[2] <= box[0] or box[3] <= box[1]:
            return f"'{title}' has no visible area to capture (it may be minimized)."

        from PIL import ImageGrab

        image = ImageGrab.grab(bbox=box, all_screens=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(tempfile.gettempdir()) / f"sentinel_window_{stamp}.png"
        image.save(path)
        return f"Saved a screenshot of '{title}' to {path}"
    except Exception as e:
        logger.exception("disp_screenshot_window failed")
        return f"Error capturing window: {e}"


@mcp.tool()
def notify(title: str, message: str) -> str:
    """Show a Windows toast notification."""
    try:
        if not title.strip() and not message.strip():
            return "Error: a title or message is required."
        xml = (
            '<toast><visual><binding template="ToastGeneric">'
            f"<text>{escape(title[:80])}</text><text>{escape(message[:200])}</text>"
            "</binding></visual></toast>"
        )
        script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications,"
            " ContentType = WindowsRuntime] | Out-Null\n"
            "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument,"
            " ContentType = WindowsRuntime] | Out-Null\n"
            "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
            f"$xml.LoadXml(@'\n{xml}\n'@)\n"
            "$toast = New-Object Windows.UI.Notifications.ToastNotification $xml\n"
            "[Windows.UI.Notifications.ToastNotificationManager]"
            "::CreateToastNotifier('Sentinel AI').Show($toast)\n"
        )
        encoded = base64.b64encode(script.encode("utf-16-le")).decode()
        result = subprocess.run(
            [WINDOWS_POWERSHELL, "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return f"Could not show the notification: {(result.stderr or '').strip()[:150]}"
        return "Notification shown."
    except Exception as e:
        logger.exception("notify failed")
        return f"Error showing notification: {e}"


@mcp.tool()
def clipboard_history(limit: int = 10) -> str:
    """List recent clipboard entries (the Win+V history), newest first.

    Only call this when the user actually asks about their clipboard. Whatever
    they last copied — passwords, tokens, connection strings — is returned
    verbatim and becomes part of the conversation, so do not call it
    speculatively or to "check" something.

    Returns a hint if clipboard history is turned off in Windows settings.
    """
    try:
        limit = max(1, min(int(limit), 25))
        # Assembled rather than inlined: the WinRT type accelerators are longer
        # than the line limit. Ends with `exit 0` because a caught error inside
        # the loop otherwise leaves PowerShell exiting non-zero with no stderr.
        script = (
            """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
  Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
Function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$cb = """
            + _CLIPBOARD_TYPE
            + """
$rt = """
            + _CLIPBOARD_RESULT_TYPE
            + """
$res = Await ($cb::GetHistoryItemsAsync()) ($rt)
Write-Output "STATUS|$($res.Status)"
foreach ($item in $res.Items) {
  $text = ''
  try { $text = Await ($item.Content.GetTextAsync()) ([System.String]) } catch { }
  if ($text) { Write-Output ("ITEM|" + ($text -replace '\\r?\\n', ' ')) }
}
exit 0
"""
        )
        result = subprocess.run(
            [WINDOWS_POWERSHELL, "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error reading clipboard history: {(result.stderr or '').strip()[:150]}"

        lines = [ln.strip() for ln in (result.stdout or "").splitlines() if ln.strip()]
        status = next((ln.split("|", 1)[1] for ln in lines if ln.startswith("STATUS|")), "")
        items = [ln.split("|", 1)[1] for ln in lines if ln.startswith("ITEM|")]

        if status and status != "Success":
            if status == "AccessDenied":
                return (
                    "Clipboard history is turned off. Enable it in Settings > System > "
                    "Clipboard (or press Win+V) and try again."
                )
            return f"Clipboard history unavailable ({status})."
        if not items:
            return "Clipboard history is empty."

        shown = items[:limit]
        out = [f"Clipboard history ({len(shown)} of {len(items)}):"]
        for i, text in enumerate(shown, 1):
            out.append(f"{i}. {text[:150]}")
        return "\n".join(out)
    except Exception as e:
        logger.exception("clipboard_history failed")
        return f"Error reading clipboard history: {e}"
