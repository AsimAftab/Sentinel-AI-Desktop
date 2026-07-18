"""LangGraph v2: typed state, structured-output supervisor, agent handoff loop.

Topology: supervisor → (agent → supervisor)* → respond → END.
The supervisor emits a structured RouteDecision (no string parsing); agents
are ReAct subgraphs from the registry; a dedicated respond node composes the
final user-facing answer and is the node whose tokens stream to the UI
(tagged "final").
"""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from ..llm import LLMManager
from ..store import Store
from .registry import AgentDefinition, load_agents

logger = logging.getLogger(__name__)

MAX_HOPS = 4


class RouteDecision(BaseModel):
    """Supervisor routing decision."""

    next_agent: str = Field(description="Name of the agent to hand off to, or FINISH")
    task: str = Field(default="", description="Concise instruction for that agent")


class GraphState(MessagesState):
    hops: int
    route: dict  # last RouteDecision as dict


def _supervisor_prompt(agents: list[AgentDefinition], context: str) -> str:
    lines = "\n".join(f"- {a.name}: {a.description}" for a in agents)
    prompt = (
        "You are the supervisor of Sentinel, a desktop AI assistant. "
        "Decide which specialist agent should act next, or FINISH when the "
        "user's request has been fully handled.\n\n"
        f"Agents:\n{lines}\n\n"
        "Rules:\n"
        "- Route to exactly one agent per step; multi-part requests may need "
        "several steps before FINISH.\n"
        "- If the request is conversational (greeting, opinion, question you "
        "can answer directly), choose FINISH immediately.\n"
        "- If an agent already produced the needed result, choose FINISH.\n"
    )
    if context:
        prompt += f"\n{context}\n"
    return prompt


def _agent_system_prompt(definition: AgentDefinition, context: str) -> str:
    base = definition.system_prompt or (
        f"You are the {definition.name} agent of Sentinel, a desktop AI assistant. "
        f"{definition.description} Use your tools to complete the task, then reply "
        "with a concise factual summary of what you did or found. Do not address "
        "the user directly; your output is consumed by a supervisor."
    )
    if context:
        base += f"\n\n{context}"
    return base


def build_graph(llm: LLMManager, store: Store):
    """Build and compile the agent graph from the registry. Called lazily."""
    loaded = load_agents()
    agents = [d for d, _ in loaded]
    valid_targets = {d.name for d in agents} | {"FINISH"}

    router_llm = llm.get(agent="Supervisor").with_structured_output(RouteDecision)

    def make_prompt(definition: AgentDefinition):
        # Callable prompt: memory context is fetched at invocation time, not baked
        # in at graph-build time.
        def prompt(state) -> list:
            system = _agent_system_prompt(definition, store.context_block())
            return [SystemMessage(system), *state["messages"]]

        return prompt

    react_agents = {
        d.name: create_react_agent(
            llm.get(agent=d.name),
            tools,
            prompt=make_prompt(d),
            name=d.name,
        )
        for d, tools in loaded
    }

    async def supervisor(state: GraphState) -> dict:
        if state.get("hops", 0) >= MAX_HOPS:
            return {"route": {"next_agent": "FINISH", "task": ""}}
        messages = [
            SystemMessage(_supervisor_prompt(agents, store.context_block())),
            *state["messages"],
        ]
        decision = await router_llm.ainvoke(messages)
        if decision.next_agent not in valid_targets:
            logger.warning("Supervisor chose unknown agent %r; finishing", decision.next_agent)
            decision.next_agent = "FINISH"
        return {"route": decision.model_dump(), "hops": state.get("hops", 0) + 1}

    def route_next(state: GraphState) -> str:
        return state["route"]["next_agent"]

    def make_agent_node(name: str):
        async def agent_node(state: GraphState) -> dict:
            task = state["route"].get("task") or ""
            inputs = list(state["messages"])
            if task:
                inputs.append(AIMessage(content=f"[Supervisor → {name}] {task}", name="Supervisor"))
            result = await react_agents[name].ainvoke({"messages": inputs})
            final = result["messages"][-1]
            summary = final.content if isinstance(final.content, str) else str(final.content)
            store.add_memory(
                "agent_action",
                {
                    "input": task,
                    "output": summary[:500],
                    "tools_used": sorted(
                        {m.name for m in result["messages"] if m.type == "tool" and m.name}
                    ),
                },
                agent=name,
            )
            return {"messages": [AIMessage(content=summary, name=name)]}

        return agent_node

    async def respond(state: GraphState, config) -> dict:
        final_llm = llm.get(agent="Responder").with_config(tags=["final"])
        system = SystemMessage(
            "You are Sentinel, a friendly desktop AI assistant. Compose the final "
            "reply to the user based on the conversation and any agent results "
            "above. Be concise and natural; this reply may be spoken aloud, so "
            "avoid markdown, bullet lists, and long URLs."
        )
        answer = await final_llm.ainvoke([system, *state["messages"]], config)
        return {"messages": [AIMessage(content=answer.content, name="Sentinel")]}

    builder = StateGraph(GraphState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("respond", respond)
    for name in react_agents:
        builder.add_node(name, make_agent_node(name))
        builder.add_edge(name, "supervisor")

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_next,
        {**{name: name for name in react_agents}, "FINISH": "respond"},
    )
    builder.add_edge("respond", END)
    return builder.compile()
