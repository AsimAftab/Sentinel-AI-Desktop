"""ChatService — runs a conversation turn through the graph and emits typed events.

This is the single seam between transport (WebSocket/REST) and the agent
graph: it owns history reconstruction, memory writes, event translation from
LangGraph's astream_events, and lazy graph (re)building.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack

from langchain_core.messages import AIMessage, HumanMessage

from .agents.graph import build_graph
from .config import Settings
from .events import Event, EventType
from .llm import LLMManager
from .store import Store

logger = logging.getLogger(__name__)

Emit = Callable[[Event], Awaitable[None]]

HISTORY_LIMIT = 20


class ChatService:
    def __init__(self, settings: Settings, store: Store):
        self.store = store
        self.llm = LLMManager(settings)
        self._graph = None
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_agents: list | None = None

    async def reload(self, settings: Settings) -> None:
        self.llm.reload(settings)
        self._graph = None  # rebuilt lazily with the new providers

    async def aclose(self) -> None:
        if self._mcp_stack is not None:
            try:
                await self._mcp_stack.aclose()
            except Exception:  # noqa: BLE001 — dying MCP subprocesses at shutdown
                logger.debug("MCP stack close failed", exc_info=True)
            self._mcp_stack = None
            self._mcp_agents = None

    async def _load_mcp_agents(self) -> list:
        """Spawn registered MCP servers once and wrap their tools as agents."""
        if self._mcp_agents is not None:
            return self._mcp_agents
        from .agents.registry import MCP_AGENT_REGISTRY, AgentDefinition

        loaded = []
        self._mcp_stack = self._mcp_stack or AsyncExitStack()
        for definition in MCP_AGENT_REGISTRY:
            try:
                from langchain_mcp_adapters.client import MultiServerMCPClient
                from langchain_mcp_adapters.tools import load_mcp_tools

                client = MultiServerMCPClient(
                    {
                        definition.server_name: {
                            "command": definition.command,
                            "args": list(definition.args),
                            "transport": "stdio",
                        }
                    }
                )
                session = await self._mcp_stack.enter_async_context(
                    client.session(definition.server_name)
                )
                tools = await load_mcp_tools(session)
                loaded.append(
                    (
                        AgentDefinition(name=definition.name, description=definition.description),
                        tools,
                    )
                )
                logger.info("MCP agent %s ready (%d tools)", definition.name, len(tools))
            except Exception as exc:  # noqa: BLE001 — missing server must not sink the service
                logger.warning("Skipping MCP agent %s: %s", definition.name, exc)
        self._mcp_agents = loaded
        return loaded

    async def _ensure_graph(self):
        if self._graph is None:
            self._graph = build_graph(self.llm, self.store, await self._load_mcp_agents())
        return self._graph

    def _history(self, session_id: str) -> list:
        messages = []
        for row in self.store.get_messages(session_id, limit=HISTORY_LIMIT):
            if row["role"] == "user":
                messages.append(HumanMessage(content=row["content"]))
            elif row["role"] == "assistant":
                messages.append(AIMessage(content=row["content"], name="Sentinel"))
        return messages

    async def run_turn(self, session_id: str, text: str, emit: Emit) -> str:
        turn_id = uuid.uuid4().hex[:12]

        def event(type_: EventType, agent: str | None = None, **data) -> Event:
            return Event(type=type_, session_id=session_id, turn_id=turn_id, agent=agent, data=data)

        await emit(event(EventType.TURN_STARTED, text=text))
        history = self._history(session_id)
        self.store.add_message(session_id, "user", text, turn_id=turn_id)
        self.store.add_memory("command", {"command": text}, session_id=session_id)

        inputs = {"messages": [*history, HumanMessage(content=text)], "hops": 0, "route": {}}
        final_text = ""
        # Our agent node and the ReAct subgraph inside it share a name; count
        # nesting depth so each agent run emits exactly one started/finished pair.
        depth: dict[str, int] = {}
        try:
            graph = await self._ensure_graph()
            async for ev in graph.astream_events(inputs, version="v2"):
                kind = ev["event"]
                name = ev.get("name", "")
                if kind == "on_chain_end" and name == "supervisor":
                    route = (ev["data"].get("output") or {}).get("route") or {}
                    if route:
                        await emit(event(EventType.ROUTING, **route))
                elif kind == "on_chain_start" and name in self._agent_names():
                    depth[name] = depth.get(name, 0) + 1
                    if depth[name] == 1:
                        await emit(event(EventType.AGENT_STARTED, agent=name))
                elif kind == "on_chain_end" and name in self._agent_names():
                    depth[name] = depth.get(name, 1) - 1
                    if depth[name] == 0:
                        await emit(event(EventType.AGENT_FINISHED, agent=name))
                elif kind == "on_tool_start":
                    await emit(
                        event(
                            EventType.TOOL_STARTED,
                            agent=name,
                            tool=name,
                            input=str(ev["data"].get("input", ""))[:300],
                        )
                    )
                elif kind == "on_tool_end":
                    await emit(
                        event(
                            EventType.TOOL_FINISHED,
                            tool=name,
                            output=str(ev["data"].get("output", ""))[:300],
                        )
                    )
                elif kind == "on_chat_model_stream" and "final" in ev.get("tags", []):
                    chunk = ev["data"]["chunk"]
                    token = chunk.content if isinstance(chunk.content, str) else ""
                    if token:
                        final_text += token
                        await emit(event(EventType.TOKEN, text=token))
                elif kind == "on_chain_end" and name == "respond" and not final_text:
                    # Supervisor fast path: reply was prewritten, no tokens streamed.
                    messages = (ev["data"].get("output") or {}).get("messages") or []
                    if messages:
                        final_text = messages[-1].content
        except Exception as exc:  # noqa: BLE001 — a turn failure must not kill the socket
            logger.exception("Turn %s failed", turn_id)
            self.store.add_memory("error", {"error": str(exc)}, session_id=session_id)
            await emit(event(EventType.ERROR, message=str(exc)))
            await emit(event(EventType.TURN_FINISHED, ok=False))
            return ""

        if not final_text:
            final_text = "I wasn't able to produce a response for that."
        self.store.add_message(session_id, "assistant", final_text, turn_id=turn_id)
        self.store.add_memory("result", {"response": final_text[:500]}, session_id=session_id)
        await emit(event(EventType.RESPONSE, text=final_text))
        await emit(event(EventType.TURN_FINISHED, ok=True))
        return final_text

    def _agent_names(self) -> set[str]:
        from .agents.registry import AGENT_REGISTRY, MCP_AGENT_REGISTRY

        return {d.name for d in AGENT_REGISTRY} | {d.name for d in MCP_AGENT_REGISTRY}
