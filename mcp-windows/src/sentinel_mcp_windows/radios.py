"""WiFi/Bluetooth soft toggles via the WinRT Windows.Devices.Radios.Radio API.

SAFETY: These tools NEVER disable hardware or adapters. No netsh interface
disable, no pnputil, no device-manager operations. Only the software radio
switch is used — the exact same mechanism as the Windows quick-settings tiles.

WinRT projection only works from Windows PowerShell 5.1 (not pwsh 7), so the
scripts below are always run with the full path to powershell.exe.
"""

from __future__ import annotations

import logging
import subprocess

from .server import mcp

logger = logging.getLogger("sentinel-mcp-windows.radios")

WINDOWS_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

# Standard Await/AsTask pattern for consuming WinRT IAsyncOperation from PS 5.1.
_WINRT_PRELUDE = """\
$ErrorActionPreference = 'Stop'
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
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
$access = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) `
  ([Windows.Devices.Radios.RadioAccessStatus])
if ($access -ne 'Allowed') { Write-Output "ACCESS_DENIED|$access"; exit 0 }
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) `
  ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
"""

_GET_SCRIPT = _WINRT_PRELUDE + """\
if ($radios.Count -eq 0) { Write-Output 'NO_RADIOS'; exit 0 }
foreach ($r in $radios) { Write-Output ("RADIO|{0}|{1}|{2}" -f $r.Kind, $r.State, $r.Name) }
"""

# Set script body. {kind} and {state} are ONLY ever filled from the fixed
# literal mappings below — never from user input. This is .format()-ed on its
# own and then prepended with the prelude at call time: the prelude's literal
# PowerShell braces are single, so formatting it would raise KeyError.
_SET_SCRIPT_BODY = """\
$target = @($radios | Where-Object {{ $_.Kind -eq '{kind}' }})
if ($target.Count -eq 0) {{ Write-Output 'NOT_FOUND'; exit 0 }}
foreach ($r in $target) {{
  if ("$($r.State)" -eq '{state}') {{
    Write-Output ("ALREADY|{{0}}|{{1}}" -f $r.State, $r.Name)
    continue
  }}
  $res = Await ($r.SetStateAsync('{state}')) ([Windows.Devices.Radios.RadioAccessStatus])
  Write-Output ("RESULT|{{0}}|{{1}}|{{2}}" -f $res, $r.State, $r.Name)
}}
"""

# Fixed literal mappings — the only values ever interpolated into the script.
_RADIO_KINDS = {"wifi": "WiFi", "bluetooth": "Bluetooth"}
_RADIO_STATES = {True: "On", False: "Off"}

_ACCESS_DENIED_MSG = (
    "Radio access denied by Windows ({status}). Check Settings > Privacy & "
    "security > Radios, and that this app is allowed to control radios."
)


def _run_radio_script(script: str) -> list[str]:
    """Run a WinRT radio script in Windows PowerShell 5.1, return output lines.

    Raises RuntimeError with a short message on failure.
    """
    result = subprocess.run(
        [WINDOWS_POWERSHELL, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell failed: {result.stderr.strip()[:200]}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _set_radio(kind_key: str, enabled: bool) -> str:
    """Turn a radio kind on/off via the software radio switch and report the result."""
    kind = _RADIO_KINDS[kind_key]  # fixed literal, never user input
    state = _RADIO_STATES[enabled]
    script = _WINRT_PRELUDE + _SET_SCRIPT_BODY.format(kind=kind, state=state)
    lines = _run_radio_script(script)

    for line in lines:
        if line.startswith("ACCESS_DENIED|"):
            return _ACCESS_DENIED_MSG.format(status=line.split("|", 1)[1])
    if "NOT_FOUND" in lines:
        return f"No {kind} radio found on this system."

    results = [line for line in lines if line.startswith(("RESULT|", "ALREADY|"))]
    if not results:
        return f"Error: unexpected output while setting {kind} radio."

    reports: list[str] = []
    for line in results:
        parts = line.split("|")
        if parts[0] == "ALREADY":
            state, name = parts[1], parts[2] if len(parts) > 2 else kind
            reports.append(f"{name} is already {state} - no change needed.")
            continue
        status, new_state = parts[1], parts[2]
        name = parts[3] if len(parts) > 3 else kind
        if status != "Allowed":
            reports.append(f"{name}: change refused ({status}).")
        else:
            reports.append(f"{name} is now {new_state}.")
    return " ".join(reports)


@mcp.tool()
def get_radios() -> str:
    """List all software radios (WiFi, Bluetooth, etc.) and their current on/off state."""
    try:
        lines = _run_radio_script(_GET_SCRIPT)
        for line in lines:
            if line.startswith("ACCESS_DENIED|"):
                return _ACCESS_DENIED_MSG.format(status=line.split("|", 1)[1])
        if "NO_RADIOS" in lines:
            return "No software radios found on this system."
        radios = [line for line in lines if line.startswith("RADIO|")]
        if not radios:
            return "Error: unexpected output while listing radios."
        out = []
        for line in radios:
            _, kind, state, name = (line.split("|", 3) + ["", "", ""])[:4]
            out.append(f"{kind} ({name}): {state}")
        return "\n".join(out)
    except Exception as e:
        logger.exception("get_radios failed")
        return f"Error listing radios: {e}"


@mcp.tool()
def set_wifi(enabled: bool) -> str:
    """Turn WiFi on (true) or off (false) using the software radio switch.

    Same mechanism as the Windows quick-settings WiFi tile; never touches the adapter.
    """
    try:
        return _set_radio("wifi", enabled)
    except Exception as e:
        logger.exception("set_wifi failed")
        return f"Error setting WiFi radio: {e}"


@mcp.tool()
def set_bluetooth(enabled: bool) -> str:
    """Turn Bluetooth on (true) or off (false) using the software radio switch.

    Same mechanism as the Windows quick-settings Bluetooth tile; never touches the adapter.
    """
    try:
        return _set_radio("bluetooth", enabled)
    except Exception as e:
        logger.exception("set_bluetooth failed")
        return f"Error setting Bluetooth radio: {e}"
