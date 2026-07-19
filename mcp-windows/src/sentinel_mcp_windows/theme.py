"""Windows dark/light theme toggle via the Personalize registry values.

Same mechanism Settings > Personalization > Colors uses: the two DWORDs
AppsUseLightTheme / SystemUsesLightTheme, followed by a WM_SETTINGCHANGE
broadcast ("ImmersiveColorSet") so running apps repaint immediately.
"""

from __future__ import annotations

import ctypes
import logging
import winreg

from .server import mcp

logger = logging.getLogger("sentinel-mcp-windows.theme")

_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002


def _read_theme() -> tuple[int, int]:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
        apps, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        system, _ = winreg.QueryValueEx(k, "SystemUsesLightTheme")
    return int(apps), int(system)


def _broadcast_change() -> None:
    """Tell running apps the theme changed so they repaint without a restart."""
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "ImmersiveColorSet",
        SMTO_ABORTIFHUNG,
        2000,
        ctypes.byref(ctypes.c_ulong()),
    )


@mcp.tool()
def get_theme() -> str:
    """Report whether Windows is using dark or light theme (apps and system)."""
    try:
        apps, system = _read_theme()
        app_mode = "light" if apps else "dark"
        sys_mode = "light" if system else "dark"
        if app_mode == sys_mode:
            return f"Windows theme is {app_mode} mode."
        return f"Apps use {app_mode} mode; system (taskbar/Start) uses {sys_mode} mode."
    except Exception as e:
        logger.exception("get_theme failed")
        return f"Error reading theme: {e}"


@mcp.tool()
def set_theme(mode: str) -> str:
    """Switch Windows between dark and light theme. mode: "dark" or "light"."""
    try:
        mode = mode.strip().lower()
        if mode not in ("dark", "light"):
            return "Error: mode must be 'dark' or 'light'."
        want = 1 if mode == "light" else 0
        apps, system = _read_theme()
        if apps == want and system == want:
            return f"Windows is already in {mode} mode - no change needed."
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "AppsUseLightTheme", 0, winreg.REG_DWORD, want)
            winreg.SetValueEx(k, "SystemUsesLightTheme", 0, winreg.REG_DWORD, want)
        _broadcast_change()
        return f"Windows theme is now {mode} mode."
    except Exception as e:
        logger.exception("set_theme failed")
        return f"Error setting theme: {e}"
