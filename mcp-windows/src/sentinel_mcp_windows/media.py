"""Universal now-playing and transport control via WinRT GlobalSystemMediaTransportControls.

This is the same session data Windows shows on the media flyout and the lock
screen, so it covers any player that registers with the OS: Spotify, YouTube
Music in a browser tab, VLC, Edge video, Groove. No API key, no OAuth, and no
Premium subscription - unlike the Spotify Web API agent, which needs all three
and can only see Spotify.

media_control in server.py stays as the fallback: it injects media keys blindly
at whichever app holds media focus, which still works for the rare player that
registers no session here. The tools below name the app they act on.

WinRT projection only works from Windows PowerShell 5.1, so the scripts run with
the full path to powershell.exe, exactly like radios.py.

SAFETY: user-supplied text (the app filter) is passed through an environment
variable, never interpolated into the script. Only fixed literals from the
_ACTIONS mapping below are ever formatted in.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess

from .server import mcp

logger = logging.getLogger("sentinel-mcp-windows.media")

WINDOWS_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

_TIMEOUT_S = 45

# WinRT type accelerators, too long for one line; assembled here so the scripts
# below stay under the line limit.
_MGR_TYPE = (
    "[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,"
    "Windows.Media,ContentType=WindowsRuntime]"
)
_PROP_TYPE = (
    "[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties,"
    "Windows.Media,ContentType=WindowsRuntime]"
)

# Standard Await/AsTask pattern for consuming WinRT IAsyncOperation from PS 5.1.
# Never .format() this: its PowerShell braces are single, so formatting raises.
_PRELUDE = (
    """\
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
$mgrType = """
    + _MGR_TYPE
    + """
$mgr = Await ($mgrType::RequestAsync()) ($mgrType)
$sessions = @($mgr.GetSessions())
"""
)

_GET_SCRIPT = (
    _PRELUDE
    + "$propType = "
    + _PROP_TYPE
    + """
$current = $mgr.GetCurrentSession()
$out = @()
foreach ($s in $sessions) {
  $title = ''; $artist = ''; $album = ''
  try {
    $p = Await ($s.TryGetMediaPropertiesAsync()) ($propType)
    $title = $p.Title; $artist = $p.Artist; $album = $p.AlbumTitle
  } catch { }
  $status = ''
  try { $status = "$($s.GetPlaybackInfo().PlaybackStatus)" } catch { }
  $out += [ordered]@{
    app = "$($s.SourceAppUserModelId)"
    status = $status
    title = "$title"
    artist = "$artist"
    album = "$album"
    current = ($current -ne $null -and $s.SourceAppUserModelId -eq $current.SourceAppUserModelId)
  }
}
ConvertTo-Json -InputObject @{ sessions = $out } -Depth 4 -Compress
"""
)

# {method} is filled ONLY from the fixed _ACTIONS mapping - never user input.
# The target app arrives via $env:SENTINEL_MEDIA_TARGET so no user text is
# interpolated. Doubled braces survive .format().
_CONTROL_BODY = """\
$target = $env:SENTINEL_MEDIA_TARGET
if ([string]::IsNullOrEmpty($target)) {{
  $s = $mgr.GetCurrentSession()
  if ($s -eq $null) {{ Write-Output 'NONE'; exit 0 }}
}} else {{
  $s = $null
  foreach ($c in $sessions) {{
    if ("$($c.SourceAppUserModelId)" -eq $target) {{ $s = $c; break }}
  }}
  if ($s -eq $null) {{ Write-Output 'NOTARGET'; exit 0 }}
}}
$ok = Await ($s.{method}()) ([System.Boolean])
Write-Output ("RESULT|{{0}}|{{1}}" -f $ok, $s.SourceAppUserModelId)
"""

# Fixed literals: the only values ever formatted into the script.
_ACTIONS = {
    "play": "TryPlayAsync",
    "pause": "TryPauseAsync",
    "toggle": "TryTogglePlayPauseAsync",
    "next": "TrySkipNextAsync",
    "previous": "TrySkipPreviousAsync",
    "stop": "TryStopAsync",
}


def _run(script: str, target: str | None = None) -> list[str]:
    """Run a WinRT script in PS 5.1. The app filter travels via the environment."""
    env = os.environ.copy()
    env["SENTINEL_MEDIA_TARGET"] = target or ""
    result = subprocess.run(
        [WINDOWS_POWERSHELL, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT_S,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell failed: {(result.stderr or '').strip()[:200]}")
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def _read_sessions() -> list[dict]:
    """Current media sessions, newest-first is not guaranteed; order is the OS's."""
    lines = _run(_GET_SCRIPT)
    if not lines:
        return []
    data = json.loads("".join(lines))
    sessions = data.get("sessions") or []
    # PowerShell collapses a single-element array into an object.
    if isinstance(sessions, dict):
        sessions = [sessions]
    return sessions


def _describe(session: dict) -> str:
    title = (session.get("title") or "").strip()
    artist = (session.get("artist") or "").strip()
    app = (session.get("app") or "unknown app").strip()
    status = (session.get("status") or "").strip() or "Unknown"
    what = f"{title} by {artist}" if title and artist else (title or "Unknown track")
    return f"{what} - {status} in {app}"


def _match(sessions: list[dict], app: str) -> tuple[dict | None, str]:
    """Resolve an app filter against session ids. Matching happens here, in
    Python, so the query never reaches PowerShell."""
    query = app.strip().lower()
    exact = [s for s in sessions if (s.get("app") or "").lower() == query]
    if exact:
        return exact[0], ""
    partial = [s for s in sessions if query in (s.get("app") or "").lower()]
    if not partial:
        names = ", ".join(s.get("app") or "?" for s in sessions) or "none"
        return None, f"No media session for '{app}'. Currently playing: {names}."
    if len(partial) > 1:
        names = ", ".join(s.get("app") or "?" for s in partial)
        return None, f"'{app}' matches several players: {names}. Be more specific."
    return partial[0], ""


@mcp.tool()
def audio_now_playing() -> str:
    """Report what is currently playing, in any media player.

    Covers Spotify, YouTube Music or any video in a browser, VLC and anything
    else that registers with Windows - use this rather than guessing, and
    prefer it over the Spotify tools when the user just asks what is playing.
    """
    try:
        sessions = _read_sessions()
        if not sessions:
            return "Nothing is playing right now."
        if len(sessions) == 1:
            return _describe(sessions[0])
        lines = ["Media sessions:"]
        for session in sessions:
            mark = "  (current)" if session.get("current") else ""
            lines.append(f"- {_describe(session)}{mark}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("audio_now_playing failed")
        return f"Error reading media sessions: {e}"


@mcp.tool()
def audio_media(action: str, app: str = "") -> str:
    """Control playback in a specific media player.

    action: "play", "pause", "toggle", "next", "previous", or "stop".
    app: which player to control (e.g. "chrome", "spotify"). Leave empty to
    control whatever Windows considers the current media session.

    Works for any player, including YouTube Music in a browser, and does not
    need Spotify Premium.
    """
    try:
        key = action.strip().lower()
        method = _ACTIONS.get(key)
        if method is None:
            return f"Error: action must be one of {', '.join(sorted(_ACTIONS))}."

        target: str | None = None
        if app.strip():
            sessions = _read_sessions()
            if not sessions:
                return "Nothing is playing right now."
            session, error = _match(sessions, app)
            if error:
                return error
            assert session is not None
            target = session.get("app") or ""

        lines = _run(_PRELUDE + _CONTROL_BODY.format(method=method), target)
        if "NONE" in lines:
            return "Nothing is playing right now."
        if "NOTARGET" in lines:
            return f"No media session for '{app}' anymore - it may have just closed."

        for line in lines:
            if line.startswith("RESULT|"):
                _, ok, source = (line.split("|", 2) + ["", ""])[:3]
                if ok.strip().lower() in ("true", "1"):
                    return f"{key.capitalize()} sent to {source}."
                return f"{source} refused the {key} command."
        return f"Error: unexpected output while sending {key}."
    except Exception as e:
        logger.exception("audio_media failed")
        return f"Error controlling playback: {e}"
