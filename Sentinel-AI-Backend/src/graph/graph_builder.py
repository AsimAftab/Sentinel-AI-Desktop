# # src/graph/graph_builder.py

# # Ensure this import is at the top
# from langchain_core.messages import BaseMessage

# from langchain_ollama import ChatOllama
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langgraph.graph import StateGraph, END
# from langchain_core.output_parsers import StrOutputParser
# from langchain.agents import AgentExecutor, create_react_agent
# from langchain import hub

# from src.graph.agent_state import AgentState
# from src.tools.browser_tools import browser_tools
# from src.tools.music_tools import music_tools # <--- MODIFIED: Import new music tools


# # --- LLM and Tools setup ---
# llm = ChatOllama(model="llama3")
# browser_agent_tools = browser_tools
# music_agent_tools = music_tools # <--- MODIFIED: Define music tools list


# # --- Supervisor Chain definition ---
# # <--- MODIFIED: Updated the supervisor prompt to include the Music agent
# supervisor_prompt_str = """You are a supervisor in a multi-agent AI system. Your role is to oversee a team of specialized agents and route user requests.
# Based on the last user message, you must select the next agent to act from the available list or decide if the task is complete.

# Available agents:
# - `Browser`: For tasks that require accessing the internet, searching for information, or scraping websites.
# - `Music`: For tasks related to searching for and playing songs on Spotify.
# - `FINISH`: If the user's question has been fully answered and the task is complete.

# Analyze the conversation and output *only* the name of the next agent to act.
# Your response MUST BE exactly one word: `Browser`, `Music`, or `FINISH`.
# """
# supervisor_prompt = ChatPromptTemplate.from_messages(
#     [
#         ("system", supervisor_prompt_str),
#         MessagesPlaceholder(variable_name="messages"),
#     ]
# )

# supervisor_chain = supervisor_prompt | llm | StrOutputParser()


# # ==================================================================
# # CORRECTED AGENT NODE FUNCTION
# # This is the corrected function that finds the right message.
# # ==================================================================
# react_prompt = hub.pull("hwchase17/react")

# def create_agent_node(llm, tools, agent_name: str):
#     """
#     Creates a node for a ReAct agent. This has been updated to find the
#     correct input message for the agent.
#     """
#     agent = create_react_agent(llm, tools, react_prompt)
#     executor = AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True)

#     def agent_node(state: AgentState):
#         # Search backwards through the messages to find the last message that is
#         # a HumanMessage or AIMessage, not the supervisor's plain string output.
#         last_content_message = None
#         for message in reversed(state["messages"]):
#             if isinstance(message, BaseMessage):
#                 last_content_message = message
#                 break

#         if last_content_message is None:
#             raise ValueError("No valid message found in state for the agent to process.")

#         # Invoke the agent with the correct content
#         print(f"--- EXECUTING AGENT: {agent_name} ---")
#         result = executor.invoke({"input": last_content_message.content})
        
#         return {"messages": [("ai", f"({agent_name} agent): {result['output']}")]}

#     return agent_node

# # --- Create Agent Nodes ---
# browser_agent_node = create_agent_node(llm, browser_agent_tools, "Browser")
# music_agent_node = create_agent_node(llm, music_agent_tools, "Music") # <--- MODIFIED: Create music agent node
# # ==================================================================


# def supervisor_node(state: AgentState) -> dict:
#     """Invokes the supervisor chain and formats the output for the graph."""
#     # Get the supervisor's decision and clean it up
#     result = supervisor_chain.invoke(state).strip()

#     # THE FIX: If the supervisor gives an empty response, we assume it's finished.
#     if not result or not result in ["Browser", "Music", "FINISH"]: # <--- MODIFIED: More robust check
#         print(f"--- SUPERVISOR: (invalid output '{result}', defaulting to FINISH) ---")
#         return {"messages": ["FINISH"]}
    
#     print(f"--- SUPERVISOR: (decided next step is {result}) ---")
#     return {"messages": [result]}


# # --- Build the Graph ---
# workflow = StateGraph(AgentState)

# workflow.add_node("supervisor", supervisor_node)
# workflow.add_node("Browser", browser_agent_node)
# workflow.add_node("Music", music_agent_node) # <--- MODIFIED: Add the Music node to the graph

# def router(state):
#     """Routes to the correct agent based on the supervisor's decision.""" # <--- MODIFIED: Docstring and logic
#     next_agent = state['messages'][-1]
#     if "Browser" in next_agent:
#         return "Browser"
#     elif "Music" in next_agent: # <--- MODIFIED: Add routing for Music agent
#         return "Music"
#     else:
#         return END

# # <--- MODIFIED: Add "Music" to the conditional edges mapping
# workflow.add_conditional_edges("supervisor", router, {"Browser": "Browser", "Music": "Music", "__end__": END})

# workflow.add_edge("Browser", END)
# workflow.add_edge("Music", END) # <--- MODIFIED: Add edge from Music back to supervisor

# workflow.set_entry_point("supervisor")
# graph = workflow.compile()

# src/graph/graph_builder.py

# Ensure this import is at the top
# src/graph/graph_builder.py

import os
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
from IPython.display import Image, display


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
# Prioritize existing-browser tools first, then Playwright, then other tools
# This ensures the agent uses the user's existing browser when possible
from src.tools.music_tools import auto_play_youtube_song, play_music_smart

# Reorder to prioritize existing browser usage
priority_music_tools = [
    auto_play_youtube_song,  # FIRST - uses existing browser
    play_music_smart,        # SECOND - smart fallback
]

# Then add Playwright tools for when we need full automation
music_agent_tools = priority_music_tools + playwright_music_tools + [
    tool for tool in music_tools if tool not in priority_music_tools
]

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
- `System`: For system control tasks including adjusting volume, controlling brightness, opening/closing applications, taking screenshots, and listing running applications.
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
def create_agent_node(llm, tools, agent_name: str, custom_prompt: str = None):
    """Creates a node for a ReAct agent using LangGraph prebuilt agent."""
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
        # Find the last user message
        last_content_message = None
        for message in reversed(state["messages"]):
            if isinstance(message, BaseMessage):
                last_content_message = message
                break

        if last_content_message is None:
            raise ValueError("No valid message found in state for the agent to process.")

        print(f"--- EXECUTING AGENT: {agent_name} ---")

        # Invoke the agent graph with the message
        result = agent_graph.invoke({"messages": [last_content_message]})

        # Extract the final AI message from the result
        final_message = result["messages"][-1]

        return {"messages": [("ai", f"({agent_name} agent): {final_message.content}")]}

    return agent_node

browser_agent_node = create_agent_node(llm, browser_agent_tools, "Browser")

# Music agent with custom prompt emphasizing auto-play tools
music_agent_prompt = """You are the Music agent. Your job is to help users play music and manage playback.

IMPORTANT: For YouTube music playback, PRIORITIZE these tools in order:
1. BEST: auto_play_youtube_song - Uses existing browser, finds direct video link, auto-plays
2. Alternative: playwright_play_youtube - Opens new browser window with automation
3. AVOID: play_on_youtube (deprecated - only opens search page)

For YouTube Music specifically:
1. BEST: auto_play_youtube_song - Works great for YT Music too
2. Alternative: playwright_play_youtube_music - New browser automation

For Spotify: use search_and_play_song

Always prefer tools that use the user's existing browser over creating new instances."""

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
display(Image(graph.get_graph().draw_mermaid_png()))