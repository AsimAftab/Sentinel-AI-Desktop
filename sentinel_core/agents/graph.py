"""LangGraph v2: typed state, structured-output supervisor, agent handoff loop.

Topology: supervisor → (agent → supervisor)* → respond → END.
The supervisor emits a structured RouteDecision (no string parsing); agents
are ReAct subgraphs from the registry; a dedicated respond node composes the
final user-facing answer and is the node whose tokens stream to the UI
(tagged "final").
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .. import embeddings
from ..llm import LLMManager
from ..store import Store
from .registry import AgentDefinition, load_agents

logger = logging.getLogger(__name__)

MAX_HOPS = 4
AGENT_TIMEOUT_S = 45
# Interactive/long-running agents legitimately exceed the default timeout.
AGENT_TIMEOUTS = {
    "BrowserActions": 150,
    "Documents": 150,
    "Computer": 90,
    "MeetingNotes": 600,  # stopping a long recording transcribes many chunks
    "Coder": 360,
}

# Each ReAct agent is compiled once per candidate model; cap it so startup
# doesn't build a graph per provider. Primary + two fallbacks rides out a
# rate limit even when the first fallback is also throttled.
REACT_FALLBACK_MAX = 3


def _is_transient(exc: BaseException) -> bool:
    """True for errors worth retrying on another model: rate limits (429) and
    transient upstream failures (timeouts, 5xx). Deliberately narrow so real
    bugs (bad schema, auth) surface instead of silently burning fallbacks."""
    name = type(exc).__name__
    transient_names = (
        "RateLimit",
        "APIConnection",
        "APITimeout",
        "InternalServer",
        "ServiceUnavailable",
    )
    if any(k in name for k in transient_names):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    return status in (429, 500, 502, 503, 504)


class RouteDecision(BaseModel):
    """Supervisor routing decision."""

    next_agent: str = Field(description="Name of the agent to hand off to, or FINISH")
    task: str = Field(default="", description="Concise instruction for that agent")
    response: str = Field(
        default="",
        description="When choosing FINISH: the final reply to the user, ready to be "
        "spoken aloud (plain conversational text, no markdown). Empty otherwise.",
    )


class GraphState(MessagesState):
    hops: int
    route: dict  # last RouteDecision as dict


def _now_line() -> str:
    from datetime import datetime

    return f"Current local date-time: {datetime.now().strftime('%A, %B %d %Y, %H:%M:%S')}."


def _supervisor_prompt(agents: list[AgentDefinition], context: str) -> str:
    lines = "\n".join(f"- {a.name}: {a.description}" for a in agents)
    prompt = (
        f"{_now_line()}\n"
        "You are the supervisor of Sentinel, a desktop AI assistant. "
        "Decide which specialist agent should act next, or FINISH when the "
        "user's request has been fully handled.\n\n"
        f"Agents:\n{lines}\n\n"
        "Rules:\n"
        "- Route to exactly one agent per step; multi-part requests may need "
        "several steps before FINISH.\n"
        "- Write 'task' self-contained: resolve pronouns, follow-ups, and likely "
        "speech-to-text misspellings using the conversation (e.g. after "
        "discussing computer scientists, 'What about Rosevalt?' means "
        "'Tell me about a person, probably Roosevelt — user said Rosevalt').\n"
        "- If the request is conversational (greeting, opinion, general "
        "knowledge), choose FINISH immediately.\n"
        "- NEVER invent real-time or external facts. Weather, news, prices, "
        "web lookups, calendar, email, notes, music state, and system state "
        "MUST come from an agent in this conversation — if none has provided "
        "it yet, route to the right agent instead of answering.\n"
        "- Judge capabilities ONLY by the agent list above. Past refusals or "
        "failures in memory are outdated — if a matching agent exists now, "
        "route to it.\n"
        "- If an agent already produced the needed result, choose FINISH. "
        "NEVER dispatch the same request to an agent that just reported "
        "success — that causes duplicate side effects (double timers, "
        "double emails, double playback).\n"
        "- Commands arrive via speech-to-text: if the message looks like a "
        "garbled fragment or mis-transcription (e.g. a few stray words with no "
        "clear intent), choose FINISH and ask the user to repeat — never route "
        "a fragment to an agent.\n"
        "- When you choose FINISH, also write the final reply in 'response': "
        "concise, natural, speakable prose based on the conversation and any "
        "agent results above — no markdown, no bullet lists, no long URLs.\n"
        "- Exception: when an agent returned verbatim structured output the "
        "user asked to see (a directory tree, listing, or file contents), "
        "copy it into 'response' EXACTLY as the agent gave it, character for "
        "character, with only a short intro sentence — altering or inventing "
        "entries is data corruption.\n"
    )
    if context:
        prompt += (
            "\nBackground from earlier activity (may be STALE — never present "
            f"it as current fact; re-fetch via an agent if asked again):\n{context}\n"
        )
    return prompt


def _agent_system_prompt(definition: AgentDefinition, context: str) -> str:
    if definition.name in AGENT_TIMEOUTS:
        budget = (
            "Multi-step tasks are expected — use as many tool calls as the task "
            "genuinely needs, but never repeat a failed approach more than twice."
        )
    else:
        budget = (
            "Budget: at most 3 tool calls per task — never repeat a similar call "
            "hoping for better results."
        )
    base = definition.system_prompt or (
        f"{_now_line()} "
        f"You are the {definition.name} agent of Sentinel, a desktop AI assistant. "
        f"{definition.description} Use your tools to complete the task, then reply "
        "with a concise factual summary of what you did or found. Do not address "
        "the user directly; your output is consumed by a supervisor. "
        f"{budget} If results are ambiguous (e.g. a likely "
        "misspelling), go with your best interpretation and say so instead of "
        "retrying variations. When a tool returns structured output the user "
        "asked to see (directory trees, listings, file contents, tables), "
        "include it VERBATIM in your reply — never abbreviate, paraphrase, or "
        "invent entries."
    )
    if context:
        base += f"\n\n{context}"
    return base


def build_graph(llm: LLMManager, store: Store, extra_agents=None):
    """Build and compile the agent graph from the registry. Called lazily.

    extra_agents: pre-loaded (AgentDefinition, tools) pairs — e.g. MCP-backed
    agents whose tools were loaded asynchronously by the caller.
    """
    loaded = load_agents() + list(extra_agents or [])
    agents = [d for d, _ in loaded]
    valid_targets = {d.name for d in agents} | {"FINISH"}

    # Runtime fallback: a 429 on the primary model transparently retries the
    # next candidate (sibling Groq model first, then other providers).
    # method="function_calling" (not the default json_schema) is the only
    # structured-output mode every fallback model supports — json_schema is
    # gpt-oss-120b-only on Groq, so a fallback would 400 without it.
    router_llm = llm.bound(
        "Supervisor",
        lambda m: m.with_structured_output(RouteDecision, method="function_calling"),
    )
    responder_llm = llm.bound("Responder", lambda m: m.with_config(tags=["final"]))

    def make_prompt(definition: AgentDefinition):
        # Callable prompt: memory context is fetched at invocation time, not baked
        # in at graph-build time.
        def prompt(state) -> list:
            system = _agent_system_prompt(definition, store.context_block())
            return [SystemMessage(system), *state["messages"]]

        return prompt

    # create_react_agent binds tools onto the model, which a fallback runnable
    # can't accept — so build one ReAct agent per candidate model and retry
    # across them on transient errors (see agent_node).
    react_agents = {
        d.name: [
            create_react_agent(model, tools, prompt=make_prompt(d), name=d.name)
            for model in llm.candidates(agent=d.name)[:REACT_FALLBACK_MAX]
        ]
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
            variants = react_agents[name]
            result = None
            last_exc: Exception | None = None
            for idx, variant in enumerate(variants):
                try:
                    # recursion_limit ~ 4 tool rounds; wait_for stops runaway loops
                    # dead — either way the supervisor still gets something to say.
                    result = await asyncio.wait_for(
                        variant.ainvoke(
                            {"messages": inputs},
                            {"recursion_limit": 24 if name in AGENT_TIMEOUTS else 10},
                        ),
                        timeout=AGENT_TIMEOUTS.get(name, AGENT_TIMEOUT_S),
                    )
                    break
                except TimeoutError:
                    logger.warning("Agent %s timed out after %ss", name, AGENT_TIMEOUT_S)
                    return {
                        "messages": [
                            AIMessage(
                                content=f"[{name} agent timed out before finishing the task]",
                                name=name,
                            )
                        ]
                    }
                except Exception as exc:  # noqa: BLE001 — incl. GraphRecursionError
                    last_exc = exc
                    if _is_transient(exc) and idx + 1 < len(variants):
                        logger.warning(
                            "Agent %s hit a transient error on model #%d (%s); trying fallback",
                            name,
                            idx,
                            type(exc).__name__,
                        )
                        continue
                    logger.warning("Agent %s failed: %s", name, exc)
                    return {
                        "messages": [
                            AIMessage(
                                content=f"[{name} agent could not complete the task: "
                                f"{type(exc).__name__}]",
                                name=name,
                            )
                        ]
                    }
            if result is None:  # every variant raised a transient error
                return {
                    "messages": [
                        AIMessage(
                            content=f"[{name} agent could not complete the task: "
                            f"{type(last_exc).__name__ if last_exc else 'unavailable'}]",
                            name=name,
                        )
                    ]
                }
            final = result["messages"][-1]
            summary = final.content if isinstance(final.content, str) else str(final.content)
            memory_id = store.add_memory(
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
            embeddings.index_in_background(store, memory_id, f"{name}: {summary[:500]}")
            return {"messages": [AIMessage(content=summary, name=name)]}

        return agent_node

    async def respond(state: GraphState, config) -> dict:
        # Fast path: the supervisor already composed the reply in its FINISH
        # decision — skip the extra LLM round-trip entirely.
        prewritten = (state.get("route") or {}).get("response", "").strip()
        if prewritten:
            return {"messages": [AIMessage(content=prewritten, name="Sentinel")]}
        final_llm = responder_llm
        system = SystemMessage(
            "You are Sentinel, a friendly desktop AI assistant. Compose the final "
            "reply to the user based on the conversation and any agent results "
            "above. Be concise and natural; this reply may be spoken aloud, so "
            "avoid markdown, bullet lists, and long URLs. If the user's message "
            "looks like a garbled fragment from speech-to-text, just ask them "
            "briefly to repeat."
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
