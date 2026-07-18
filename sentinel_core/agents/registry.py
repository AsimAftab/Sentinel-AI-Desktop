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
    """An agent whose tools come from an MCP server (spawned once, kept alive)."""

    name: str
    description: str
    server_name: str
    command: str
    args: tuple[str, ...]


MCP_AGENT_REGISTRY: list[MCPAgentDefinition] = [
    MCPAgentDefinition(
        name="System",
        description="Windows system control: volume, brightness, media playback, "
        "launching and closing apps, window focus, screenshots, system info, "
        "lock screen and power actions.",
        server_name="windows",
        command="uv",
        args=("run", "--project", str(REPO_ROOT / "mcp-windows"), "sentinel-mcp-windows"),
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
        description="Personal notes: create, list, search, update, delete notes.",
        tools_module="sentinel_core.tools.notes",
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
