"""Night Light toggle via the CloudStore registry state blob.

Windows has no public API for Night Light; Settings and the quick-settings
tile write a binary blob under CloudStore. The encoding (stable across
Win10 1903+ and Win11) is:

- byte 18 is the state flag: 0x13 = off, 0x15 = on
- the ON blob additionally contains bytes 10 00 inserted at offset 23
  (just before the inner "D0 0A" header)
- bytes 10..14 hold a varint timestamp that must be bumped so the
  CloudStore listener picks up the change

Only this software toggle is used — never gamma/color-profile hacks.
"""

from __future__ import annotations

import logging
import winreg

from .server import mcp

logger = logging.getLogger("sentinel-mcp-windows.night_light")

_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current"
    r"\default$windows.data.bluelightreduction.bluelightreductionstate"
    r"\windows.data.bluelightreduction.bluelightreductionstate"
)

_OFF, _ON = 0x13, 0x15


def _read_blob() -> bytes:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
        data, kind = winreg.QueryValueEx(k, "Data")
    if kind != winreg.REG_BINARY or len(data) < 25:
        raise RuntimeError("unexpected night light registry value")
    return bytes(data)


def _write_blob(blob: bytes) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Data", 0, winreg.REG_BINARY, blob)


def _bump_timestamp(blob: bytearray) -> None:
    for i in range(10, 15):
        if blob[i] != 0xFF:
            blob[i] += 1
            return
        blob[i] = 0x00


@mcp.tool()
def get_night_light() -> str:
    """Report whether Night Light (blue light reduction) is currently on or off."""
    try:
        flag = _read_blob()[18]
        if flag == _ON:
            return "Night light is On."
        if flag == _OFF:
            return "Night light is Off."
        return f"Night light state unrecognized (flag {flag:#04x})."
    except FileNotFoundError:
        return "Night light has never been configured on this system."
    except Exception as e:
        logger.exception("get_night_light failed")
        return f"Error reading night light state: {e}"


@mcp.tool()
def set_night_light(enabled: bool) -> str:
    """Turn Night Light (warm screen tint / blue light reduction) on (true) or off (false)."""
    try:
        blob = bytearray(_read_blob())
        flag = blob[18]
        if flag not in (_ON, _OFF):
            return f"Error: unrecognized night light state (flag {flag:#04x}); not touching it."
        if (flag == _ON) == enabled:
            return f"Night light is already {'On' if enabled else 'Off'}."
        if enabled:
            blob[18] = _ON
            blob[23:23] = b"\x10\x00"
        else:
            blob[18] = _OFF
            del blob[23:25]
        _bump_timestamp(blob)
        _write_blob(bytes(blob))
        # Read back to confirm Windows kept the change.
        new_flag = _read_blob()[18]
        state = "On" if new_flag == _ON else "Off"
        return f"Night light is now {state}."
    except FileNotFoundError:
        return "Night light was never configured here (open Settings > Display once)."
    except Exception as e:
        logger.exception("set_night_light failed")
        return f"Error setting night light: {e}"
