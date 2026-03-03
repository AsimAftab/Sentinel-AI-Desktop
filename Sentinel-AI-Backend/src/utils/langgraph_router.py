# src/utils/langgraph_router.py
"""
Routes voice commands to the LangGraph multi-agent system.

Uses graph.astream() so async tools (browser HTTP calls) run without
blocking the OS thread. The public route_to_langgraph() function is
synchronous — it spins up an event loop via asyncio.run() and blocks
until the graph produces a final answer, which is fine for the single-
threaded orchestrator context.
"""

import asyncio
from langchain_core.messages import HumanMessage
from src.graph.graph_builder import graph
from src.utils.log_config import get_logger

logger = get_logger("router")


async def _async_route_to_langgraph(command: str, verbose: bool = True) -> str:
    """Async core — streams the graph and collects the final agent response."""
    inputs = {"messages": [HumanMessage(content=command)]}
    last_state = None

    async for step_output in graph.astream(inputs, {"recursion_limit": 10}):
        for node_name, node_result in step_output.items():
            last_state = node_result

            if verbose:
                if node_name == "__end__":
                    logger.info("Graph execution finished.")
                else:
                    logger.debug("Executing node: %s", node_name)
                    last_message = node_result["messages"][-1]
                    logger.debug("Output: %s", last_message)

    if last_state is None:
        return "No response generated."

    # Collect AI messages from agent nodes (stored as tuples by agent_node)
    ai_messages = [
        msg[1] for msg in last_state["messages"] if isinstance(msg, tuple) and msg[0] == "ai"
    ]

    final_answer = (
        ai_messages[-1]
        if ai_messages
        else "The task is complete, but I don't have a specific answer to show."
    )

    if verbose:
        logger.info("Final answer: %s", final_answer)

    return final_answer


def route_to_langgraph(command: str, verbose: bool = True) -> str:
    """
    Synchronous entry point called by the orchestrator.

    Runs the async graph execution in a new event loop so the orchestrator
    thread doesn't need its own running loop.
    """
    if verbose:
        logger.info("Routing command to LangGraph: '%s'", command)

    return asyncio.run(_async_route_to_langgraph(command, verbose))
