"""Smoke-test a frozen sentinel-mcp-windows.exe over the real MCP stdio protocol.

Guards the freeze bug that has shipped silently before: pointing PyInstaller at
``server.py`` instead of ``mcp_entry.py`` collapses the package, so
``from . import bluetooth, files, ...`` raises at startup and every Windows tool
disappears. The exe still launches, so only an actual tools/list call catches it.

Usage: python packaging/smoke_mcp.py path/to/sentinel-mcp-windows.exe

Exits non-zero with the server's stderr attached if the handshake fails, the
tool list is empty, or an expected tool group is missing.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading

PROTOCOL_VERSION = "2024-11-05"
TIMEOUT_S = 60

# One representative tool per registration path. Anything imported at the bottom
# of server.py lands in a separate module, which is exactly what the freeze bug
# breaks -- so each side module needs its own sentinel here.
EXPECTED_TOOLS = {
    "get_volume": "server.py",
    "audio_devices": "audio.py",
    "audio_now_playing": "media.py",
    "disp_list": "display.py",
    "fs_list": "files.py",
    "get_radios": "radios.py",
    "workspace_list": "workspaces.py",
    "get_theme": "theme.py",
    "get_night_light": "night_light.py",
    "bluetooth_devices": "bluetooth.py",
}


def _reader(stream, q: queue.Queue) -> None:
    for line in stream:
        q.put(line)
    q.put(None)


def _read_message(q: queue.Queue, want_id: int, stderr: list[str]) -> dict:
    """Read lines until a JSON-RPC response with the given id arrives."""
    while True:
        try:
            line = q.get(timeout=TIMEOUT_S)
        except queue.Empty:
            _die(f"timed out after {TIMEOUT_S}s waiting for response id={want_id}", stderr)
        if line is None:
            _die(f"server closed stdout while waiting for response id={want_id}", stderr)
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # stdout must carry protocol only; stray prints are themselves a bug.
            _die(f"non-JSON on stdout (stdout is the MCP channel): {line[:200]}", stderr)
        if msg.get("id") == want_id:
            return msg


def _die(reason: str, stderr: list[str]) -> None:
    print(f"FAIL: {reason}", file=sys.stderr)
    if stderr:
        print("--- server stderr ---", file=sys.stderr)
        print("".join(stderr[-40:]), file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: smoke_mcp.py path/to/sentinel-mcp-windows.exe")
    exe = sys.argv[1]

    proc = subprocess.Popen(
        [exe],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    assert proc.stdin and proc.stdout and proc.stderr

    out_q: queue.Queue = queue.Queue()
    err_lines: list[str] = []
    threading.Thread(target=_reader, args=(proc.stdout, out_q), daemon=True).start()
    threading.Thread(
        target=lambda: err_lines.extend(proc.stderr),
        daemon=True,  # type: ignore[arg-type]
    ).start()

    def send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")  # type: ignore[union-attr]
        proc.stdin.flush()  # type: ignore[union-attr]

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "sentinel-smoke", "version": "1.0"},
                },
            }
        )
        init = _read_message(out_q, 1, err_lines)
        if "error" in init:
            _die(f"initialize failed: {init['error']}", err_lines)
        server_name = init.get("result", {}).get("serverInfo", {}).get("name", "?")

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = _read_message(out_q, 2, err_lines)
        if "error" in listed:
            _die(f"tools/list failed: {listed['error']}", err_lines)

        names = {t["name"] for t in listed.get("result", {}).get("tools", [])}
        if not names:
            _die("server exposed zero tools", err_lines)

        missing = {n: mod for n, mod in EXPECTED_TOOLS.items() if n not in names}
        if missing:
            mods = ", ".join(sorted(set(missing.values())))
            _die(
                f"missing {len(missing)} expected tools ({', '.join(sorted(missing))}) "
                f"-- module(s) not registered: {mods}. This is the mcp_entry.py freeze bug.",
                err_lines,
            )

        print(f"OK: {server_name} exposed {len(names)} tools; all module sentinels present.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
