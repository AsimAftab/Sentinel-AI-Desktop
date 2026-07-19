"""Bluetooth paired-device listing and connect, via the Win32 Bluetooth APIs.

BluetoothFindFirstDevice/BluetoothFindNextDevice enumerate paired devices;
BluetoothSetServiceState toggles the audio/handsfree service on a device,
which triggers the same connect flow as the Settings "Connect" button.
Pairing NEW devices is out of scope (needs a user-interactive ceremony).
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

from .server import mcp

logger = logging.getLogger("sentinel-mcp-windows.bluetooth")


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        (n, wintypes.WORD)
        for n in (
            "wYear",
            "wMonth",
            "wDayOfWeek",
            "wDay",
            "wHour",
            "wMinute",
            "wSecond",
            "wMilliseconds",
        )
    ]


class _BT_ADDR(ctypes.Structure):
    _fields_ = [("ullLong", ctypes.c_ulonglong)]


class _DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("Address", _BT_ADDR),
        ("ulClassofDevice", wintypes.ULONG),
        ("fConnected", wintypes.BOOL),
        ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", _SYSTEMTIME),
        ("stLastUsed", _SYSTEMTIME),
        ("szName", ctypes.c_wchar * 248),
    ]


class _SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("fReturnAuthenticated", wintypes.BOOL),
        ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL),
        ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wintypes.HANDLE),
    ]


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(data1: int) -> _GUID:
    """Bluetooth base-UUID service GUID: {data1:08x}-0000-1000-8000-00805F9B34FB."""
    return _GUID(
        data1, 0x0000, 0x1000, (ctypes.c_ubyte * 8)(0x80, 0x00, 0x00, 0x80, 0x5F, 0x9B, 0x34, 0xFB)
    )


_AUDIO_SINK = 0x110B  # A2DP (headphones/speakers)
_HANDSFREE = 0x111E  # HFP (mic/calls)

_SERVICE_DISABLE = 0x00
_SERVICE_ENABLE = 0x01


def _api() -> ctypes.WinDLL:
    bt = ctypes.windll.BluetoothAPIs
    bt.BluetoothFindFirstDevice.restype = ctypes.c_void_p
    bt.BluetoothFindNextDevice.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    bt.BluetoothFindDeviceClose.argtypes = [ctypes.c_void_p]
    bt.BluetoothSetServiceState.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    return bt


def _paired_devices() -> list[_DEVICE_INFO]:
    """All paired (authenticated/remembered) devices. Raises OSError if BT is off."""
    bt = _api()
    params = _SEARCH_PARAMS()
    params.dwSize = ctypes.sizeof(params)
    params.fReturnAuthenticated = True
    params.fReturnRemembered = True
    params.fReturnConnected = True
    devices: list[_DEVICE_INFO] = []
    info = _DEVICE_INFO()
    info.dwSize = ctypes.sizeof(info)
    handle = bt.BluetoothFindFirstDevice(ctypes.byref(params), ctypes.byref(info))
    if not handle:
        return devices
    try:
        while True:
            devices.append(info)
            info = _DEVICE_INFO()
            info.dwSize = ctypes.sizeof(info)
            if not bt.BluetoothFindNextDevice(handle, ctypes.byref(info)):
                break
    finally:
        bt.BluetoothFindDeviceClose(handle)
    return devices


def _find_device(name: str) -> tuple[_DEVICE_INFO | None, str]:
    """Resolve a device by case-insensitive substring (exact match preferred)."""
    target = name.strip().lower()
    if not target:
        return None, "Error: empty device name."
    devices = _paired_devices()
    if not devices:
        return None, "No paired Bluetooth devices found (is Bluetooth on?)."
    exact = [d for d in devices if d.szName.lower() == target]
    matches = exact or [d for d in devices if target in d.szName.lower()]
    if not matches:
        names = ", ".join(d.szName for d in devices[:8])
        return None, f"No paired device matching '{name}'. Paired devices: {names}"
    if len(matches) > 1:
        names = ", ".join(d.szName for d in matches[:8])
        return None, f"Ambiguous name '{name}'. Did you mean one of: {names}?"
    return matches[0], ""


def _set_audio_services(device: _DEVICE_INFO, enable: bool) -> list[str]:
    """Toggle the A2DP + HFP services; returns per-service error notes (empty = ok)."""
    bt = _api()
    flag = _SERVICE_ENABLE if enable else _SERVICE_DISABLE
    errors: list[str] = []
    for svc in (_AUDIO_SINK, _HANDSFREE):
        guid = _guid(svc)
        rc = bt.BluetoothSetServiceState(None, ctypes.byref(device), ctypes.byref(guid), flag)
        if rc != 0:
            errors.append(f"service {svc:#06x}: error {rc}")
    return errors


@mcp.tool()
def bluetooth_devices() -> str:
    """List paired Bluetooth devices and whether each is currently connected."""
    try:
        devices = _paired_devices()
        if not devices:
            return "No paired Bluetooth devices found (is Bluetooth on?)."
        lines = []
        for d in sorted(devices, key=lambda d: (not d.fConnected, d.szName.lower())):
            state = "connected" if d.fConnected else "not connected"
            lines.append(f"{d.szName} — {state}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("bluetooth_devices failed")
        return f"Error listing Bluetooth devices: {e}"


@mcp.tool()
def bluetooth_connect(name: str) -> str:
    """Connect to an already-paired Bluetooth device by name (e.g. headphones or
    a speaker). The device must be powered on and in range. Cannot pair new devices."""
    try:
        device, error = _find_device(name)
        if device is None:
            return error
        if device.fConnected:
            return f"{device.szName} is already connected - no change needed."
        # Toggling the audio services off->on triggers the same connect flow
        # as the Settings "Connect" button.
        _set_audio_services(device, enable=False)
        errors = _set_audio_services(device, enable=True)
        if len(errors) == 2:
            if all("error 1060" in e for e in errors):
                # ERROR_SERVICE_DOES_NOT_EXIST: not an audio sink (e.g. a phone).
                return (
                    f"{device.szName} does not support audio connect - this works "
                    f"for headphones and speakers, not phones."
                )
            return f"Could not connect to {device.szName}: " + "; ".join(errors)
        # Poll for the connection to come up (device may be off/out of range).
        for _ in range(10):
            time.sleep(1)
            fresh, _err = _find_device(device.szName)
            if fresh is not None and fresh.fConnected:
                return f"Connected to {fresh.szName}."
        return (
            f"Sent connect request to {device.szName}, but it did not connect "
            f"within 10s - make sure the device is powered on and in range."
        )
    except Exception as e:
        logger.exception("bluetooth_connect failed")
        return f"Error connecting Bluetooth device: {e}"


@mcp.tool()
def bluetooth_disconnect(name: str) -> str:
    """Disconnect a connected Bluetooth audio device by name (stays paired)."""
    try:
        device, error = _find_device(name)
        if device is None:
            return error
        if not device.fConnected:
            return f"{device.szName} is not connected - no change needed."
        _set_audio_services(device, enable=False)
        for _ in range(5):
            time.sleep(1)
            fresh, _err = _find_device(device.szName)
            if fresh is not None and not fresh.fConnected:
                # Re-enable the services so auto-connect and the next
                # bluetooth_connect keep working; this does not reconnect
                # a device the user just disconnected in most cases, but
                # connect() force-toggles anyway.
                return f"Disconnected {device.szName}."
        return f"Sent disconnect to {device.szName}, but it still shows connected."
    except Exception as e:
        logger.exception("bluetooth_disconnect failed")
        return f"Error disconnecting Bluetooth device: {e}"
