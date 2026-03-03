# src/graph/graph_builder.py
"""
LangGraph Multi-Agent System with Memory Integration.

Auto-constructs the agent graph from AGENT_REGISTRY — adding a new agent
requires only a single entry in agent_registry.py (no changes here).
"""

import asyncio
import importlib
import os
import time
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langchain_core.output_parsers import StrOutputParser
from langgraph.prebuilt import create_react_agent

from src.graph.agent_state import AgentState
from src.graph.agent_registry import AGENT_REGISTRY
from src.utils.agent_memory import get_agent_memory
from src.utils.llm_config import get_llm_config
from src.utils.log_config import get_logger

logger = get_logger("graph")

AGENT_TIMEOUT_SECONDS = 30  # Max time any single agent may run
AGENT_MAX_RETRIES = 2  # Max retries per agent on timeout

# Short-TTL cache so all agent nodes in one graph invocation share one MongoDB query
_memory_ctx_cache: dict = {}  # {"ts": float, "ctx": str}
_MEMORY_CTX_TTL = 2.0  # seconds — covers the full multi-agent graph execution

try:
    from IPython.display import Image, display

    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False


# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------
load_dotenv()

# Optional LLM response cache
if os.getenv("LLM_CACHE_ENABLED", "false").lower() == "true":
    from langchain_core.globals import set_llm_cache
    from langchain_core.caches import InMemoryCache
    set_llm_cache(InMemoryCache())
    logger.info("LLM response caching enabled (InMemoryCache)")

llm_config = get_llm_config()
logger.info("LLM Config: %s", llm_config.get_config_summary())

supervisor_llm = llm_config.get_llm_for_agent("Supervisor")
supervisor_provider = (
    llm_config.config["agent_assignments"].get("Supervisor")
    or llm_config.config["primary_provider"]
)
logger.info("Supervisor using: %s", llm_config.get_provider_name(supervisor_provider))


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------
_sorted_agents = sorted(AGENT_REGISTRY, key=lambda a: a.priority)
_agent_names = [a.name for a in _sorted_agents]


def _load_tools(agent_def):
    """Dynamically import and return a tools list for an AgentDefinition."""
    module = importlib.import_module(agent_def.tools_module)
    tools = getattr(module, agent_def.tools_attr)
    if agent_def.tool_overrides:
        tools = agent_def.tool_overrides(tools)
    return tools


def _build_supervisor_prompt() -> str:
    """Generate the supervisor system prompt from the registry."""
    lines = [
        "You are a supervisor in a multi-agent AI system. Your role is to oversee a "
        "team of specialized agents and route user requests.",
        "Based on the last user message, you must select the next agent to act from "
        "the available list or decide if the task is complete.",
        "",
        "Available agents:",
    ]
    for agent_def in _sorted_agents:
        lines.append(f"- `{agent_def.name}`: {agent_def.description}")
    lines.append("- `FINISH`: If the user's question has been fully answered and the task is complete.")
    lines.append("")
    lines.append("Analyze the conversation and output *only* the name of the next agent to act.")
    valid_names = ", ".join(f"`{n}`" for n in _agent_names)
    lines.append(f"Your response MUST BE exactly one word: {valid_names}, or `FINISH`.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Supervisor chain
# ---------------------------------------------------------------------------
supervisor_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _build_supervisor_prompt()),
        MessagesPlaceholder(variable_name="messages"),
    ]
)
supervisor_chain = supervisor_prompt | supervisor_llm | StrOutputParser()


# ---------------------------------------------------------------------------
# Memory-aware agent node factory
# ---------------------------------------------------------------------------
_memory = get_agent_memory()


def _get_cached_memory_context() -> str:
    """Return recent memory context, querying MongoDB at most once per 2-second window."""
    now = time.time()
    if _memory_ctx_cache and now - _memory_ctx_cache.get("ts", 0) < _MEMORY_CTX_TTL:
        return _memory_ctx_cache["ctx"]
    ctx = _memory.get_context_for_agent(include_other_agents=True, minutes=15, max_entries=5)
    _memory_ctx_cache["ts"] = now
    _memory_ctx_cache["ctx"] = ctx
    return ctx


def create_agent_node(llm, tools, agent_name: str, custom_prompt: str = None):
    """Creates a ReAct agent node with memory integration."""
    prompt = custom_prompt or f"You are the {agent_name} agent. Use the available tools to help the user."
    agent_graph = create_react_agent(llm, tools, prompt=prompt)

    async def agent_node(state: AgentState):
        start_time = time.time()

        last_content_message = None
        for message in reversed(state["messages"]):
            if isinstance(message, BaseMessage):
                last_content_message = message
                break

        if last_content_message is None:
            raise ValueError("No valid message found in state for the agent to process.")

        memory_context = await asyncio.to_thread(_get_cached_memory_context)

        input_content = last_content_message.content
        if memory_context:
            enhanced_input = f"{memory_context}\n[Current Request]\n{input_content}"
            logger.debug("Executing agent: %s (with memory context)", agent_name)
        else:
            enhanced_input = input_content
            logger.debug("Executing agent: %s", agent_name)

        enhanced_message = HumanMessage(content=enhanced_input)

        max_attempts = AGENT_MAX_RETRIES + 1
        result = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = await asyncio.wait_for(
                    agent_graph.ainvoke({"messages": [enhanced_message]}),
                    timeout=AGENT_TIMEOUT_SECONDS,
                )
                break  # Success — exit retry loop
            except asyncio.TimeoutError:
                if attempt < max_attempts:
                    logger.warning(
                        "%s agent timed out (attempt %d/%d), retrying...",
                        agent_name, attempt, max_attempts,
                    )
                    await asyncio.sleep(1.0 * attempt)
                else:
                    logger.warning(
                        "%s agent timed out after %ds (attempt %d/%d, giving up)",
                        agent_name, AGENT_TIMEOUT_SECONDS, attempt, max_attempts,
                    )
                    return {
                        "messages": [
                            (
                                "ai",
                                f"({agent_name} agent): Sorry, the request timed out after "
                                f"{AGENT_TIMEOUT_SECONDS} seconds. Please try again.",
                            )
                        ]
                    }

        final_message = result["messages"][-1]
        output_content = final_message.content
        duration_ms = int((time.time() - start_time) * 1000)

        tools_used = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = (
                        tool_call.get("name")
                        if isinstance(tool_call, dict)
                        else getattr(tool_call, "name", None)
                    )
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)

        try:
            await asyncio.to_thread(
                _memory.store_agent_action,
                agent=agent_name,
                input_text=input_content[:500],
                output_text=output_content[:500],
                tools_used=tools_used,
                success=True,
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.warning("Failed to store agent memory: %s", e)

        logger.info(
            "agent_metrics | agent=%s | duration_ms=%d | tools_used=%s | success=True",
            agent_name, duration_ms, ",".join(tools_used) if tools_used else "none",
        )

        return {"messages": [("ai", f"({agent_name} agent): {output_content}")]}

    return agent_node


# ---------------------------------------------------------------------------
# Supervisor node
# ---------------------------------------------------------------------------
_valid_outputs = set(_agent_names) | {"FINISH"}


def supervisor_node(state: AgentState) -> dict:
    """Invokes the supervisor chain and formats the output for the graph."""
    result = supervisor_chain.invoke(state).strip()

    if not result or result not in _valid_outputs:
        logger.debug("Supervisor: invalid output '%s', defaulting to FINISH", result)
        return {"messages": ["FINISH"]}

    logger.debug("Supervisor: decided next step is %s", result)
    return {"messages": [result]}


# ---------------------------------------------------------------------------
# Build graph from registry
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)

# Create and add agent nodes from registry
for agent_def in _sorted_agents:
    agent_llm = llm_config.get_llm_for_agent(agent_def.name)
    agent_tools = _load_tools(agent_def)
    node_fn = create_agent_node(agent_llm, agent_tools, agent_def.name, agent_def.custom_prompt)
    workflow.add_node(agent_def.name, node_fn)


def router(state):
    """Routes to the correct agent based on the supervisor's decision."""
    last_msg = state["messages"][-1]

    if isinstance(last_msg, tuple):
        next_agent = last_msg[1] if len(last_msg) > 1 else ""
    elif isinstance(last_msg, BaseMessage):
        next_agent = last_msg.content
    else:
        next_agent = str(last_msg)

    for name in _agent_names:
        if name in next_agent:
            return name
    return END


# Build conditional edges map: {agent_name: agent_name, "__end__": END}
_conditional_map = {name: name for name in _agent_names}
_conditional_map["__end__"] = END

workflow.add_conditional_edges("supervisor", router, _conditional_map)

for agent_def in _sorted_agents:
    workflow.add_edge(agent_def.name, END)

workflow.set_entry_point("supervisor")

graph = workflow.compile()

# Display graph visualization if in IPython/Jupyter
if IPYTHON_AVAILABLE:
    try:
        display(Image(graph.get_graph().draw_mermaid_png()))
    except Exception:
        pass
