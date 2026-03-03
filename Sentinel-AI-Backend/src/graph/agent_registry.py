"""
Declarative agent registry — adding a new agent is a single entry here.

Each AgentDefinition describes one specialist agent. The graph builder
iterates over AGENT_REGISTRY to construct nodes, edges, supervisor prompt,
and the router function automatically.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, List


@dataclass
class AgentDefinition:
    """Metadata for one specialist agent in the multi-agent graph."""

    name: str  # Node name in the graph (e.g. "Browser")
    description: str  # One-line description used in the supervisor prompt
    tools_module: str  # Dotted import path (e.g. "src.tools.browser_tools")
    tools_attr: str  # Attribute name that holds the tools list
    custom_prompt: Optional[str] = None  # If set, overrides default agent prompt
    tool_overrides: Optional[Callable] = None  # Post-process tools list (e.g. reorder)
    priority: int = 50  # Lower = listed first in supervisor prompt


def _music_tool_overrides(tools_list):
    """
    Reorder music tools so logged-in-browser tools come first.
    Matches the priority logic that was previously hard-coded in graph_builder.py.
    """
    from src.tools.music_tools import (
        auto_play_youtube_music_song,
        auto_play_youtube_song,
        play_music_smart,
    )

    priority_tools = [auto_play_youtube_music_song, auto_play_youtube_song, play_music_smart]
    return priority_tools + [t for t in tools_list if t not in priority_tools]


# --- Music agent custom prompt (was previously in graph_builder.py) ---
_MUSIC_PROMPT = """You are the Music agent. Your job is to help users play music and manage playback.

CRITICAL: ALWAYS use tools that open in the user's LOGGED-IN browser!
This ensures no ads, personalized recommendations, and access to their library.

TOOL PRIORITY (ALWAYS use these first):
1. YouTube Music requests → auto_play_youtube_music_song (opens in logged-in browser)
2. Regular YouTube requests → auto_play_youtube_song (opens in logged-in browser)
3. Spotify requests → search_and_play_song (uses user's Spotify account)
4. Smart selection → play_music_smart (tries Spotify first, then YouTube Music)

PLATFORM SELECTION RULES:
- "YouTube Music" or "YT Music" → auto_play_youtube_music_song
- "YouTube" (regular) → auto_play_youtube_song
- "Spotify" → search_and_play_song
- No platform specified → Try Spotify first (if connected), else YouTube Music

IMPORTANT:
- NEVER use Playwright tools (they open NEW browser = not logged in = ADS!)
- ALWAYS use auto_play_youtube_music_song for YouTube Music (logged-in browser)
- ALWAYS use auto_play_youtube_song for regular YouTube (logged-in browser)
- These tools find the direct video link and open it in the user's existing browser"""


# -----------------------------------------------------------------------
# THE REGISTRY — add new agents here
# -----------------------------------------------------------------------

AGENT_REGISTRY: List[AgentDefinition] = [
    AgentDefinition(
        name="Browser",
        description=(
            "For tasks requiring internet access, web search, weather info, news, "
            "translation, currency conversion, word definitions, website status checks, "
            "and file downloads."
        ),
        tools_module="src.tools.browser_tools",
        tools_attr="browser_tools",
        priority=10,
    ),
    AgentDefinition(
        name="Music",
        description=(
            "For music-related tasks including playing songs on Spotify/YouTube/YouTube Music "
            "(with auto-play), controlling playback, searching lyrics, creating playlists, "
            "mood-based music, genre playlists, and music discovery."
        ),
        tools_module="src.tools.music_tools",
        tools_attr="music_tools",
        custom_prompt=_MUSIC_PROMPT,
        tool_overrides=_music_tool_overrides,
        priority=20,
    ),
    AgentDefinition(
        name="Meeting",
        description=(
            "For Google Meet and Calendar tasks including creating instant meetings, "
            "scheduling meetings, listing upcoming meetings, joining meetings, "
            "and cancelling meetings."
        ),
        tools_module="src.tools.meeting_tools",
        tools_attr="meeting_tools",
        priority=30,
    ),
    AgentDefinition(
        name="System",
        description=(
            "For system control tasks including adjusting volume, controlling brightness, "
            "opening/closing applications, taking screenshots, listing running applications, "
            "Bluetooth control (on/off/status/settings), and WiFi control (on/off/status/settings)."
        ),
        tools_module="src.tools.system_tools",
        tools_attr="system_tools",
        priority=40,
    ),
    AgentDefinition(
        name="Productivity",
        description=(
            "For productivity tasks including setting timers, setting alarms, listing active "
            "timers/alarms, cancelling timers/alarms, Pomodoro sessions, and focus mode."
        ),
        tools_module="src.tools.productivity_tools",
        tools_attr="productivity_tools",
        priority=50,
    ),
    AgentDefinition(
        name="Notes",
        description=(
            "For note-taking and knowledge management tasks including creating notes, "
            "searching notes, listing notes, reading notes, updating notes, and deleting notes."
        ),
        tools_module="src.tools.notes_tools",
        tools_attr="notes_tools",
        priority=60,
    ),
    AgentDefinition(
        name="Email",
        description=(
            "For Gmail tasks including listing emails, searching emails, reading emails, "
            "sending emails, replying to emails, drafting emails, trashing emails, "
            "and getting inbox summaries."
        ),
        tools_module="src.tools.email_tools",
        tools_attr="email_tools",
        priority=70,
    ),
]
