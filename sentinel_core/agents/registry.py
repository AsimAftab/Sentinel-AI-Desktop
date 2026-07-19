"""Declarative agent registry (ported pattern from the legacy backend).

Adding an agent = one AgentDefinition entry + a tools module exposing TOOLS.
The graph builder constructs supervisor prompt, nodes, and routing from this
list. Agents whose tools module fails to import are skipped with a warning so
the service still boots while integrations are being ported.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    description: str
    tools_module: str = ""
    tools_attr: str = "TOOLS"
    system_prompt: str | None = None


@dataclass(frozen=True)
class MCPAgentDefinition:
    """An agent whose tools come from an MCP server (spawned once, kept alive).

    tool_prefixes: claim only tools whose names start with one of these;
    None = catch-all for the server's tools no other agent claimed.
    """

    name: str
    description: str
    server_name: str
    command: str
    args: tuple[str, ...]
    tool_prefixes: tuple[str, ...] | None = None


def _windows_mcp_command() -> tuple[str, tuple[str, ...]]:
    """Dev: run from source via uv. Packaged: sibling frozen exe (or env override)."""
    import os
    import sys

    override = os.environ.get("SENTINEL_MCP_WINDOWS_EXE")
    if override:
        return override, ()
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).parent / "sentinel-mcp-windows.exe"
        return str(exe), ()
    return "uv", ("run", "--project", str(REPO_ROOT / "mcp-windows"), "sentinel-mcp-windows")


_mcp_cmd, _mcp_args = _windows_mcp_command()

MCP_AGENT_REGISTRY: list[MCPAgentDefinition] = [
    MCPAgentDefinition(
        name="BrowserActions",
        description="Drives a real browser window (Edge) to interact with "
        "websites: open pages, click, type, fill forms, multi-step tasks on "
        "specific sites. Slower than Browser — use only when the task needs "
        "actual page interaction, not just information.",
        server_name="playwright",
        command="npx",
        args=("-y", "@playwright/mcp@latest", "--browser", "msedge"),
    ),
    MCPAgentDefinition(
        name="Files",
        description="File navigation on this PC: list folders, show directory "
        "trees, find files by name, open files or folders, read text files, "
        "resolve Downloads/Documents/Desktop and other user folders.",
        server_name="windows",
        command=_mcp_cmd,
        args=_mcp_args,
        tool_prefixes=("fs_",),
    ),
    MCPAgentDefinition(
        name="System",
        description="Windows system control: volume, brightness, night light, "
        "dark/light theme, WiFi and Bluetooth toggles, media playback, "
        "launching and closing apps, minimizing/maximizing windows, "
        "workspaces (named app groups like 'dev mode'), window focus, "
        "clipboard, wallpaper, screenshots, system info, recycle bin, lock "
        "screen and power actions.",
        server_name="windows",
        command=_mcp_cmd,
        args=_mcp_args,
    ),
]


AGENT_REGISTRY: list[AgentDefinition] = [
    AgentDefinition(
        name="Browser",
        description="Web search, weather, news, translation, and reading web pages.",
        tools_module="sentinel_core.tools.browser",
    ),
    AgentDefinition(
        name="Music",
        description="Spotify playback and music discovery: play/pause/skip, playlists, "
        "search songs and artists, current track.",
        tools_module="sentinel_core.tools.music",
    ),
    AgentDefinition(
        name="Meeting",
        description="Google Meet and Calendar: create, schedule, list, join, cancel meetings.",
        tools_module="sentinel_core.tools.meeting",
    ),
    AgentDefinition(
        name="Email",
        description="Gmail: read, search, summarize, draft and send email.",
        tools_module="sentinel_core.tools.email",
    ),
    AgentDefinition(
        name="Notes",
        description="Notepad-style documents the user explicitly writes and "
        "manages: create, list, search, update, delete notes. NOT for "
        "'remember that…' facts about the user — those go to Memory.",
        tools_module="sentinel_core.tools.notes",
    ),
    AgentDefinition(
        name="Productivity",
        description="Reminders, timers, alarms, and recurring routines: set a "
        "reminder or countdown timer, or schedule a routine (e.g. a 9am daily "
        "briefing) that runs a prompt through Sentinel and announces the "
        "result; list or cancel any of them.",
        tools_module="sentinel_core.tools.productivity",
    ),
    AgentDefinition(
        name="Documents",
        description="Question-answering over the user's own documents (PDF, "
        "Word, text, markdown): index folders, then search their content by "
        "meaning and answer with passages citing the source files.",
        tools_module="sentinel_core.tools.documents",
    ),
    AgentDefinition(
        name="Computer",
        description="Operates application windows via accessibility (never "
        "blind clicks): list a window's buttons and fields, click a button "
        "by name, type into a field, minimize/maximize/close windows. Use "
        "when the user asks to operate an app's interface directly.",
        tools_module="sentinel_core.tools.ui_control",
    ),
    AgentDefinition(
        name="MeetingNotes",
        description="Record and transcribe meetings or any audio playing on "
        "this computer: start recording system audio, check status, stop to "
        "get a transcript saved to a file (then summarize it).",
        tools_module="sentinel_core.tools.meeting_notes",
    ),
    AgentDefinition(
        name="Coder",
        description="Software engineering on the user's local code projects "
        "via Claude Code: answer questions about a codebase, or make code "
        "changes in a given project folder (may take minutes).",
        tools_module="sentinel_core.tools.coder",
    ),
    AgentDefinition(
        name="Messenger",
        description="Telegram messaging through the user's bot: send a "
        "message to the user's phone, read recent incoming messages, or "
        "explain setup if unconfigured.",
        tools_module="sentinel_core.tools.telegram",
    ),
    AgentDefinition(
        name="Memory",
        description="Long-term memory: permanently remember facts or "
        "preferences the user asks to remember, recall past conversations "
        "and stored facts by meaning, forget stored facts on request.",
        tools_module="sentinel_core.tools.memory",
    ),
    AgentDefinition(
        name="Screen",
        description="Sees the user's screen: describe what is currently "
        "visible, read and explain error messages or dialogs, summarize "
        "on-screen content, answer questions about it.",
        tools_module="sentinel_core.tools.screen",
    ),
    # System & Productivity agents return in Phase 4 via the Sentinel Windows
    # MCP server (replacing the legacy pyautogui-based system_tools).
]


def load_agents() -> list[tuple[AgentDefinition, list]]:
    """Resolve registry entries to (definition, tools) pairs, skipping failures."""
    loaded = []
    for definition in AGENT_REGISTRY:
        try:
            module = importlib.import_module(definition.tools_module)
            tools = getattr(module, definition.tools_attr)
            if tools:
                loaded.append((definition, list(tools)))
            else:
                logger.warning("Agent %s has an empty tools list; skipping", definition.name)
        except Exception as exc:  # noqa: BLE001 — a broken integration must not sink the service
            logger.warning("Skipping agent %s (tools import failed: %s)", definition.name, exc)
    return loaded
