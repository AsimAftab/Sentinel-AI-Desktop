# src/graph/graph_builder.py
"""
LangGraph Multi-Agent System with Memory Integration.

This module builds the agent graph with:
- Supervisor agent for routing
- Specialized agents (Browser, Music, Meeting, System, Productivity)
- Memory integration for context awareness
"""

import os
import time
from dotenv import load_dotenv

# --- MODIFIED: Swapped Ollama for AzureChatOpenAI
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import StrOutputParser
from langgraph.prebuilt import create_react_agent

from src.graph.agent_state import AgentState
from src.tools.browser_tools import browser_tools
from src.tools.music_tools import music_tools
from src.tools.playwright_music_tools import playwright_music_tools
from src.tools.meeting_tools import meeting_tools
from src.tools.system_tools import system_tools
from src.tools.productivity_tools import productivity_tools
from src.utils.agent_memory import get_agent_memory, MemoryType

try:
    from IPython.display import Image, display
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


# --- MODIFIED: Load environment variables for Azure ---
load_dotenv()

# --- MODIFIED: LLM and Tools setup using Azure OpenAI ---
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0, # Set to 0 for more deterministic agent behavior
)

browser_agent_tools = browser_tools

# Music tools prioritization:
# 1. LOGGED-IN BROWSER tools FIRST - uses user's existing browser (no ads, personalized)
# 2. Spotify tools - for Spotify playback
# 3. Playwright tools - AVOID (opens new browser, not logged in, shows ads)
from src.tools.music_tools import auto_play_youtube_music_song, auto_play_youtube_song, play_music_smart

# Prioritize tools that use user's logged-in browser
priority_music_tools = [
    auto_play_youtube_music_song,  # FIRST - YouTube Music in logged-in browser (BEST!)
    auto_play_youtube_song,        # SECOND - Regular YouTube in logged-in browser (BEST!)
    play_music_smart,              # THIRD - Smart platform selector (tries Spotify first)
]

# Add all other tools EXCEPT Playwright (only use if explicitly needed)
# Playwright opens new browser = not logged in = ads + no personalization
music_agent_tools = priority_music_tools + [
    tool for tool in music_tools if tool not in priority_music_tools
]

# NOTE: Playwright tools excluded by default (not logged in, shows ads)
# Add them back only if user specifically requests automation

meeting_agent_tools = meeting_tools
system_agent_tools = system_tools
productivity_agent_tools = productivity_tools

# --- Supervisor Chain definition (No changes needed here) ---
supervisor_prompt_str = """You are a supervisor in a multi-agent AI system. Your role is to oversee a team of specialized agents and route user requests.
Based on the last user message, you must select the next agent to act from the available list or decide if the task is complete.

Available agents:
- `Browser`: For tasks requiring internet access, web search, weather info, news, translation, currency conversion, word definitions, website status checks, and file downloads.
- `Music`: For music-related tasks including playing songs on Spotify/YouTube/YouTube Music (with auto-play), controlling playback, searching lyrics, creating playlists, mood-based music, genre playlists, and music discovery.
- `Meeting`: For Google Meet and Calendar tasks including creating instant meetings, scheduling meetings, listing upcoming meetings, joining meetings, and cancelling meetings.
- `System`: For system control tasks including adjusting volume, controlling brightness, opening/closing applications, taking screenshots, listing running applications, Bluetooth control (on/off/status/settings), and WiFi control (on/off/status/settings).
- `Productivity`: For productivity tasks including setting timers, setting alarms, listing active timers/alarms, and cancelling timers/alarms.
- `FINISH`: If the user's question has been fully answered and the task is complete.

Analyze the conversation and output *only* the name of the next agent to act.
Your response MUST BE exactly one word: `Browser`, `Music`, `Meeting`, `System`, `Productivity`, or `FINISH`.
"""
supervisor_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", supervisor_prompt_str),
        MessagesPlaceholder(variable_name="messages"),
    ]
)
supervisor_chain = supervisor_prompt | llm | StrOutputParser()

# --- Agent and Graph definitions ---

# Initialize memory service
_memory = get_agent_memory()


def create_agent_node(llm, tools, agent_name: str, custom_prompt: str = None):
    """
    Creates a node for a ReAct agent using LangGraph prebuilt agent.

    Includes memory integration:
    - Injects recent context into agent prompt
    - Tracks agent actions and tool usage
    """
    # Create a react agent graph for this specific agent
    if custom_prompt:
        agent_prompt = custom_prompt
    else:
        agent_prompt = f"You are the {agent_name} agent. Use the available tools to help the user."

    agent_graph = create_react_agent(
        llm,
        tools,
        prompt=agent_prompt
    )

    def agent_node(state: AgentState):
        start_time = time.time()

        # Find the last user message
        last_content_message = None
        for message in reversed(state["messages"]):
            if isinstance(message, BaseMessage):
                last_content_message = message
                break

        if last_content_message is None:
            raise ValueError("No valid message found in state for the agent to process.")

        # Get memory context to inject
        memory_context = _memory.get_context_for_agent(
            agent=agent_name,
            include_other_agents=True,
            minutes=15,
            max_entries=5
        )

        # Prepare input with memory context
        input_content = last_content_message.content
        if memory_context:
            # Prepend memory context to help agent understand what's been done
            enhanced_input = f"{memory_context}\n[Current Request]\n{input_content}"
            print(f"--- EXECUTING AGENT: {agent_name} (with memory context) ---")
        else:
            enhanced_input = input_content
            print(f"--- EXECUTING AGENT: {agent_name} ---")

        # Create enhanced message with context
        from langchain_core.messages import HumanMessage
        enhanced_message = HumanMessage(content=enhanced_input)

        # Invoke the agent graph with the enhanced message
        result = agent_graph.invoke({"messages": [enhanced_message]})

        # Extract the final AI message from the result
        final_message = result["messages"][-1]
        output_content = final_message.content

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Extract tools used from the result messages
        tools_used = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)

        # Store agent action in memory
        try:
            _memory.store_agent_action(
                agent=agent_name,
                input_text=input_content[:500],  # Truncate for storage
                output_text=output_content[:500],
                tools_used=tools_used,
                success=True,
                duration_ms=duration_ms
            )
        except Exception as e:
            print(f"⚠️ Failed to store agent memory: {e}")

        return {"messages": [("ai", f"({agent_name} agent): {output_content}")]}

    return agent_node

browser_agent_node = create_agent_node(llm, browser_agent_tools, "Browser")

# Music agent with custom prompt emphasizing logged-in browser tools
music_agent_prompt = """You are the Music agent. Your job is to help users play music and manage playback.

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

music_agent_node = create_agent_node(llm, music_agent_tools, "Music", custom_prompt=music_agent_prompt)

# Meeting agent for Google Meet and Calendar
meeting_agent_node = create_agent_node(llm, meeting_agent_tools, "Meeting")

# System agent for volume, brightness, and application control
system_agent_node = create_agent_node(llm, system_agent_tools, "System")

# Productivity agent for timers and alarms
productivity_agent_node = create_agent_node(llm, productivity_agent_tools, "Productivity")

def supervisor_node(state: AgentState) -> dict:
    """Invokes the supervisor chain and formats the output for the graph."""
    result = supervisor_chain.invoke(state).strip()

    if not result or not result in ["Browser", "Music", "Meeting", "System", "Productivity", "FINISH"]:
        print(f"--- SUPERVISOR: (invalid output '{result}', defaulting to FINISH) ---")
        return {"messages": ["FINISH"]}

    print(f"--- SUPERVISOR: (decided next step is {result}) ---")
    return {"messages": [result]}

workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("Browser", browser_agent_node)
workflow.add_node("Music", music_agent_node)
workflow.add_node("Meeting", meeting_agent_node)
workflow.add_node("System", system_agent_node)
workflow.add_node("Productivity", productivity_agent_node)

def router(state):
    """Routes to the correct agent based on the supervisor's decision."""
    next_agent = state['messages'][-1]
    if "Browser" in next_agent:
        return "Browser"
    elif "Music" in next_agent:
        return "Music"
    elif "Meeting" in next_agent:
        return "Meeting"
    elif "System" in next_agent:
        return "System"
    elif "Productivity" in next_agent:
        return "Productivity"
    else:
        return END

workflow.add_conditional_edges("supervisor", router, {"Browser": "Browser", "Music": "Music", "Meeting": "Meeting", "System": "System", "Productivity": "Productivity", "__end__": END})
workflow.add_edge("Browser", END)
workflow.add_edge("Music", END)
workflow.add_edge("Meeting", END)
workflow.add_edge("System", END)
workflow.add_edge("Productivity", END)
workflow.set_entry_point("supervisor")

graph = workflow.compile()

# Display graph visualization if in IPython/Jupyter
if IPYTHON_AVAILABLE:
    try:
        display(Image(graph.get_graph().draw_mermaid_png()))
    except Exception:
        pass  # Skip visualization if not in notebook environment