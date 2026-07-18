"""Music tools — Spotify Web API via spotipy.

Ported from the Spotify half of the legacy music_tools.py. All YouTube
scraping, webbrowser hacks, and lyrics tools were dropped. Auth uses
SpotifyOAuth with the token cached under the app data dir. Errors are returned
as short strings, never tracebacks.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from langchain_core.tools import tool

from sentinel_core.config import data_dir, get_secret

logger = logging.getLogger(__name__)

SCOPES = "user-read-playback-state user-modify-playback-state"

_client_lock = threading.Lock()
_client: Any = None


def _spotify():
    """Return a cached spotipy client (lazy — never created at import time)."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        client_id = get_secret("SPOTIPY_CLIENT_ID")
        client_secret = get_secret("SPOTIPY_CLIENT_SECRET")
        redirect_uri = get_secret("SPOTIPY_REDIRECT_URI")
        if not (client_id and client_secret and redirect_uri):
            raise ValueError(
                "Spotify is not configured. Set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, "
                "and SPOTIPY_REDIRECT_URI (create an app at "
                "https://developer.spotify.com/dashboard)."
            )
        _client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=SCOPES,
                cache_path=str(data_dir() / "spotify_token.json"),
            )
        )
        return _client


def _err(action: str, exc: Exception) -> str:
    """Short human-readable error string; full details go to the log only."""
    from spotipy.exceptions import SpotifyException

    logger.error("Music tool failed (%s): %s", action, exc, exc_info=True)
    if isinstance(exc, ValueError):  # setup instructions from _spotify()
        return str(exc)
    if isinstance(exc, SpotifyException):
        msg = str(exc.msg or "")
        if "PREMIUM_REQUIRED" in msg or exc.reason == "PREMIUM_REQUIRED":
            return "This playback control requires a Spotify Premium subscription."
        if "NO_ACTIVE_DEVICE" in msg or exc.reason == "NO_ACTIVE_DEVICE" or exc.http_status == 404:
            return (
                "No active Spotify device. Open Spotify on a device, or use list_devices "
                "and play_on_device to pick one."
            )
        return f"Spotify error while trying to {action} (HTTP {exc.http_status})."
    return f"Could not {action}: {type(exc).__name__}: {exc}"


def _describe_devices(devices: list[dict]) -> str:
    lines = []
    for d in devices:
        flags = " (active)" if d.get("is_active") else ""
        lines.append(f"- {d.get('name', '?')} [{d.get('type', '?')}]{flags}")
    return "\n".join(lines)


def _pick_device(sp: Any) -> tuple[str | None, str]:
    """Choose a playback device id.

    Order: the active device, else a device of type "Computer". If neither
    exists, return (None, message listing the devices) instead of blindly
    playing on an arbitrary device (legacy wrong-device bug).
    """
    devices = (sp.devices() or {}).get("devices", [])
    if not devices:
        return None, (
            "No Spotify devices found. Open the Spotify app on your computer or "
            "phone, then try again."
        )
    for d in devices:
        if d.get("is_active"):
            return d["id"], ""
    for d in devices:
        if d.get("type") == "Computer":
            return d["id"], f" (started on this computer: {d.get('name', '?')})"
    return None, (
        "No active Spotify device and no computer device available. "
        "Available devices:\n"
        f"{_describe_devices(devices)}\n"
        "Use play_on_device with one of these names, or start Spotify where you want playback."
    )


def _now_playing(sp: Any) -> str:
    playback = sp.current_playback()
    item = (playback or {}).get("item")
    if not item:
        return ""
    return f"'{item['name']}' by {item['artists'][0]['name']}"


@tool
def search_and_play(query: str, item_type: str = "track") -> str:
    """Search Spotify and start playback of the best match.

    Args:
        query: What to play, e.g. "Bohemian Rhapsody Queen" or "lofi beats playlist".
        item_type: One of "track" (a song), "artist", "album", or "playlist".
    """
    try:
        item_type = {"song": "track"}.get(item_type.lower().strip(), item_type.lower().strip())
        if item_type not in ("track", "artist", "album", "playlist"):
            return "item_type must be one of: track, artist, album, playlist."
        if not query.strip():
            return "A search query is required."
        sp = _spotify()
        device_id, note = _pick_device(sp)
        if device_id is None:
            return note
        results = sp.search(q=query, type=item_type, limit=1)
        items = [i for i in results[item_type + "s"]["items"] if i]
        if not items:
            return f"No {item_type} found on Spotify for '{query}'."
        item = items[0]
        name = item["name"]
        if item_type == "track":
            sp.start_playback(device_id=device_id, uris=[item["uri"]])
            played = f"'{name}' by {item['artists'][0]['name']}"
        else:
            sp.start_playback(device_id=device_id, context_uri=item["uri"])
            played = f"{item_type} '{name}'"
        return f"Now playing {played}.{note}"
    except Exception as exc:
        return _err("play music", exc)


@tool
def pause_music() -> str:
    """Pause the current Spotify playback."""
    try:
        sp = _spotify()
        playback = sp.current_playback()
        if not playback or not playback.get("is_playing"):
            return "Nothing is currently playing on Spotify."
        sp.pause_playback()
        track = _now_playing(sp)
        return f"Paused {track}." if track else "Playback paused."
    except Exception as exc:
        return _err("pause music", exc)


@tool
def resume_music() -> str:
    """Resume paused Spotify playback."""
    try:
        sp = _spotify()
        playback = sp.current_playback()
        if playback and playback.get("is_playing"):
            track = _now_playing(sp)
            return f"Music is already playing: {track}." if track else "Music is already playing."
        if playback and playback.get("device"):
            sp.start_playback()
            return "Playback resumed."
        device_id, note = _pick_device(sp)
        if device_id is None:
            return note
        sp.start_playback(device_id=device_id)
        return f"Playback resumed.{note}"
    except Exception as exc:
        return _err("resume music", exc)


@tool
def next_track() -> str:
    """Skip to the next track in the Spotify queue."""
    try:
        sp = _spotify()
        sp.next_track()
        track = _now_playing(sp)
        return f"Skipped to {track}." if track else "Skipped to the next track."
    except Exception as exc:
        return _err("skip to the next track", exc)


@tool
def previous_track() -> str:
    """Go back to the previous track in the Spotify queue."""
    try:
        sp = _spotify()
        sp.previous_track()
        track = _now_playing(sp)
        return f"Went back to {track}." if track else "Went back to the previous track."
    except Exception as exc:
        return _err("go to the previous track", exc)


@tool
def set_volume(volume_percent: int) -> str:
    """Set the Spotify playback volume (requires Premium).

    Args:
        volume_percent: Volume level from 0 to 100.
    """
    try:
        if not 0 <= volume_percent <= 100:
            return "Volume must be between 0 and 100."
        sp = _spotify()
        device_id, note = _pick_device(sp)
        if device_id is None:
            return note
        sp.volume(volume_percent, device_id=device_id)
        return f"Volume set to {volume_percent}%.{note}"
    except Exception as exc:
        return _err("set the volume", exc)


@tool
def current_track() -> str:
    """Get the currently playing Spotify track with album and progress."""
    try:
        sp = _spotify()
        playback = sp.current_playback()
        if not playback or not playback.get("item"):
            return "Nothing is playing on Spotify right now."
        item = playback["item"]
        progress = playback.get("progress_ms") or 0
        duration = item.get("duration_ms") or 0
        state = "Playing" if playback.get("is_playing") else "Paused"
        return (
            f"{state}: '{item['name']}' by {item['artists'][0]['name']} "
            f"from '{item['album']['name']}' "
            f"({progress // 60000}:{progress % 60000 // 1000:02d} / "
            f"{duration // 60000}:{duration % 60000 // 1000:02d})"
        )
    except Exception as exc:
        return _err("get the current track", exc)


@tool
def list_devices() -> str:
    """List the user's available Spotify devices (name, type, active state)."""
    try:
        devices = (_spotify().devices() or {}).get("devices", [])
        if not devices:
            return (
                "No Spotify devices found. Open the Spotify app on your computer or "
                "phone, then try again."
            )
        return f"Spotify devices:\n{_describe_devices(devices)}"
    except Exception as exc:
        return _err("list devices", exc)


@tool
def play_on_device(device_name: str) -> str:
    """Transfer Spotify playback to a specific device by name.

    Args:
        device_name: Device name as shown by list_devices (case-insensitive,
            partial match allowed).
    """
    try:
        if not device_name.strip():
            return "A device name is required. Use list_devices to see options."
        sp = _spotify()
        devices = (sp.devices() or {}).get("devices", [])
        if not devices:
            return "No Spotify devices found. Open the Spotify app somewhere first."
        wanted = device_name.strip().lower()
        match = next(
            (d for d in devices if d.get("name", "").lower() == wanted),
            None,
        ) or next((d for d in devices if wanted in d.get("name", "").lower()), None)
        if not match:
            return (
                f"No device matching '{device_name}'. Available devices:\n"
                f"{_describe_devices(devices)}"
            )
        sp.transfer_playback(match["id"], force_play=True)
        return f"Playback transferred to '{match.get('name', device_name)}'."
    except Exception as exc:
        return _err("transfer playback", exc)


TOOLS = [
    search_and_play,
    pause_music,
    resume_music,
    next_track,
    previous_track,
    set_volume,
    current_track,
    list_devices,
    play_on_device,
]
