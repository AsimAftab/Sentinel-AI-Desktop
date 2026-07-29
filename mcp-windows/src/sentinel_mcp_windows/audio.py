"""Audio endpoint and per-application volume control.

Three capabilities the master-volume tools in server.py do not cover:
- switching the default playback/recording device (Speakers -> headphones),
- the per-app volume mixer (turn Chrome down without touching everything else),
- the microphone level and mute.

Default-device switching goes through IPolicyConfig, the same undocumented COM
interface the Settings sound page uses. pycaw already ships the interface
definition, so there is no new dependency and no hand-rolled vtable here.

COM is initialized per call via _with_com, like the rest of the server.
"""

from __future__ import annotations

import logging
from ctypes import POINTER, cast

from .server import _with_com, mcp

logger = logging.getLogger("sentinel-mcp-windows.audio")

# CLSID_PolicyConfigClient. Undocumented but stable since Windows 7; this is the
# same object the Sound settings page drives when you pick an output device.
_CLSID_POLICY_CONFIG = "{870af99c-171d-4f9e-af0d-e63df40c2bc9}"

# Console, Multimedia, Communications. Windows shows the first two as "Default
# Device" and the third as "Default Communication Device"; picking a device in
# Settings sets all three, so we do too.
_ROLES = (0, 1, 2)

_KIND_FLOW = {"output": 0, "input": 1}  # EDataFlow.eRender / eCapture
_DEVICE_STATE_ACTIVE = 0x1


def _endpoint_volume(device):
    """IAudioEndpointVolume for a raw IMMDevice (what GetMicrophone returns)."""
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume

    iface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


def _default_id(flow: int) -> str:
    """Device id of the current default endpoint for a data flow, or ""."""
    import comtypes
    from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
    from pycaw.constants import CLSID_MMDeviceEnumerator

    try:
        enumerator = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER
        )
        # eMultimedia is the role users mean by "my speakers".
        return enumerator.GetDefaultAudioEndpoint(flow, 1).GetId()
    except Exception:  # noqa: BLE001 — no default device is a valid state
        return ""


def _active_devices(flow: int) -> list:
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetAllDevices(flow, _DEVICE_STATE_ACTIVE)


def _resolve_device(name: str, devices: list) -> tuple[object | None, str]:
    """Exact match, then unique substring. Mirrors _resolve_start_app's contract."""
    query = name.strip().lower()
    if not query:
        return None, "Error: device name is required."
    named = [(d, (d.FriendlyName or "").lower()) for d in devices]

    for device, friendly in named:
        if friendly == query:
            return device, ""
    matches = [d for d, friendly in named if query in friendly]
    if not matches:
        available = ", ".join(d.FriendlyName for d in devices) or "none"
        return None, f"No audio device matching '{name}'. Available: {available}."
    if len(matches) > 1:
        names = ", ".join(d.FriendlyName for d in matches)
        return None, f"'{name}' matches several devices: {names}. Be more specific."
    return matches[0], ""


def _sessions() -> list[tuple[str, object]]:
    """(process name, session) for every live session.

    Sessions whose process has already exited stay in the enumerator and raise
    psutil.NoSuchProcess on access, so each one is probed defensively.
    """
    from pycaw.pycaw import AudioUtilities

    out: list[tuple[str, object]] = []
    for session in AudioUtilities.GetAllSessions():
        try:
            if session.Process:
                name = session.Process.name()
            else:
                name = session.DisplayName or "System sounds"
        except Exception:  # noqa: BLE001 — dead session, skip it
            continue
        out.append((name, session))
    return out


@mcp.tool()
def audio_devices(kind: str = "output") -> str:
    """List active audio devices and show which is the default.

    kind: "output" (speakers/headphones), "input" (microphones), or "all".
    """
    try:
        kind = kind.strip().lower()
        if kind not in ("output", "input", "all"):
            return "Error: kind must be 'output', 'input', or 'all'."

        def read() -> str:
            groups = ("output", "input") if kind == "all" else (kind,)
            lines: list[str] = []
            for group in groups:
                flow = _KIND_FLOW[group]
                devices = _active_devices(flow)
                default = _default_id(flow)
                label = "Output" if group == "output" else "Input"
                if not devices:
                    lines.append(f"{label}: none found.")
                    continue
                lines.append(f"{label} devices:")
                for device in devices:
                    mark = "  (default)" if device.id == default else ""
                    lines.append(f"- {device.FriendlyName}{mark}")
            return "\n".join(lines)

        return _with_com(read)
    except Exception as e:
        logger.exception("audio_devices failed")
        return f"Error listing audio devices: {e}"


@mcp.tool()
def audio_set_device(name: str, kind: str = "output") -> str:
    """Switch the default audio device, e.g. from speakers to headphones.

    name is matched case-insensitively against the device's friendly name;
    a partial name works as long as it is unambiguous.
    kind: "output" (default) or "input".
    """
    try:
        kind = kind.strip().lower()
        if kind not in ("output", "input"):
            return "Error: kind must be 'output' or 'input'."

        def apply() -> str:
            import comtypes
            from comtypes import GUID
            from pycaw.api.policyconfig import IPolicyConfig

            flow = _KIND_FLOW[kind]
            devices = _active_devices(flow)
            if not devices:
                return f"No active {kind} devices found."
            device, error = _resolve_device(name, devices)
            if error:
                return error
            assert device is not None

            if device.id == _default_id(flow):
                return f"{device.FriendlyName} is already the default {kind} device."

            policy = comtypes.CoCreateInstance(
                GUID(_CLSID_POLICY_CONFIG), IPolicyConfig, comtypes.CLSCTX_ALL
            )
            for role in _ROLES:
                policy.SetDefaultEndpoint(device.id, role)

            if _default_id(flow) != device.id:
                return f"Windows did not accept the switch to {device.FriendlyName}."
            return f"Default {kind} device is now {device.FriendlyName}."

        return _with_com(apply)
    except Exception as e:
        logger.exception("audio_set_device failed")
        return f"Error switching audio device: {e}"


@mcp.tool()
def audio_apps() -> str:
    """List apps currently playing audio, with each one's volume and mute state."""
    try:

        def read() -> str:
            rows: dict[str, tuple[int, bool]] = {}
            for name, session in _sessions():
                volume = session.SimpleAudioVolume
                rows[name] = (
                    round(volume.GetMasterVolume() * 100),
                    bool(volume.GetMute()),
                )
            if not rows:
                return "No apps are using audio right now."
            lines = ["Apps using audio:"]
            for name in sorted(rows, key=str.lower):
                level, muted = rows[name]
                lines.append(f"- {name}: {level}%{' (muted)' if muted else ''}")
            return "\n".join(lines)

        return _with_com(read)
    except Exception as e:
        logger.exception("audio_apps failed")
        return f"Error listing app audio: {e}"


@mcp.tool()
def audio_set_app_volume(app: str, level: int | None = None, muted: bool | None = None) -> str:
    """Set one app's volume and/or mute it, without changing system volume.

    app is matched against the process name (e.g. "chrome", "spotify").
    level: 0-100. muted: true/false. Pass at least one of them.
    """
    try:
        if level is None and muted is None:
            return "Error: pass level, muted, or both."
        if level is not None and not 0 <= level <= 100:
            return "Error: level must be between 0 and 100."

        query = app.strip().lower()
        if not query:
            return "Error: app name is required."

        def apply() -> str:
            sessions = _sessions()
            # An app can own several sessions (one per audio stream); set all of
            # them or the change appears to do nothing.
            matched = [(n, s) for n, s in sessions if query in n.lower()]
            if not matched:
                names = ", ".join(sorted({n for n, _ in sessions}, key=str.lower)) or "none"
                return f"No app matching '{app}' is using audio. Currently playing: {names}."

            for _, session in matched:
                volume = session.SimpleAudioVolume
                if level is not None:
                    volume.SetMasterVolume(level / 100.0, None)
                if muted is not None:
                    volume.SetMute(1 if muted else 0, None)

            name = matched[0][0]
            parts = []
            if level is not None:
                parts.append(f"volume {level}%")
            if muted is not None:
                parts.append("muted" if muted else "unmuted")
            return f"{name}: {', '.join(parts)}."

        return _with_com(apply)
    except Exception as e:
        logger.exception("audio_set_app_volume failed")
        return f"Error setting app volume: {e}"


@mcp.tool()
def audio_mic() -> str:
    """Report the default microphone's level and whether it is muted."""
    try:

        def read() -> str:
            from pycaw.pycaw import AudioUtilities

            volume = _endpoint_volume(AudioUtilities.GetMicrophone())
            level = round(volume.GetMasterVolumeLevelScalar() * 100)
            muted = bool(volume.GetMute())
            return f"Microphone is at {level}% and is {'muted' if muted else 'not muted'}."

        return _with_com(read)
    except Exception as e:
        logger.exception("audio_mic failed")
        return f"Error reading microphone: {e}"


@mcp.tool()
def audio_set_mic(level: int | None = None, muted: bool | None = None) -> str:
    """Set the default microphone's level and/or mute it.

    level: 0-100. muted: true/false. Pass at least one of them.

    Warning: muting the default microphone also silences Sentinel's own wake
    word, so a spoken "unmute my mic" will not be heard afterwards - it has to
    be undone from the app window or Windows sound settings. Say so when muting.
    """
    try:
        if level is None and muted is None:
            return "Error: pass level, muted, or both."
        if level is not None and not 0 <= level <= 100:
            return "Error: level must be between 0 and 100."

        def apply() -> str:
            from pycaw.pycaw import AudioUtilities

            volume = _endpoint_volume(AudioUtilities.GetMicrophone())
            if level is not None:
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            if muted is not None:
                if bool(volume.GetMute()) == muted:
                    state = "muted" if muted else "unmuted"
                    if level is None:
                        return f"Microphone is already {state} - no change needed."
                else:
                    volume.SetMute(1 if muted else 0, None)

            parts = []
            if level is not None:
                parts.append(f"level {level}%")
            if muted is not None:
                parts.append("muted" if muted else "unmuted")
            note = ""
            if muted:
                note = " Voice commands will not be heard until it is unmuted from the app."
            return f"Microphone: {', '.join(parts)}.{note}"

        return _with_com(apply)
    except Exception as e:
        logger.exception("audio_set_mic failed")
        return f"Error setting microphone: {e}"
