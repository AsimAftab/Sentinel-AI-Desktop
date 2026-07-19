"""Long-term memory tools: remember facts forever, recall by meaning, forget.

Backed by the SQLite store's sqlite-vec index; relevant memories are also
injected into every turn automatically — these tools are for explicit asks.
"""

from __future__ import annotations

import logging
from datetime import datetime

from langchain_core.tools import tool

from .. import embeddings
from ..store import Store

logger = logging.getLogger(__name__)

_store: Store | None = None


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


@tool
async def remember_fact(fact: str) -> str:
    """Permanently remember a fact or preference the user stated.

    Args:
        fact: self-contained statement, e.g. "The user's sister is called
            Sara" or "The user prefers window seats on flights".
    """
    store = _get_store()
    memory_id = store.add_memory("preference", {"text": fact}, ttl_hours=None)
    try:
        store.index_memory(memory_id, await embeddings.embed_async(fact))
    except Exception:  # noqa: BLE001 — stored either way, just not searchable by meaning
        logger.exception("Embedding failed for remembered fact")
    return f"Remembered: {fact}"


@tool
async def recall_memories(query: str, limit: int = 5) -> str:
    """Search everything Sentinel remembers (facts, past requests, results)
    by meaning, not just keywords.

    Args:
        query: what to look for, e.g. "user's seat preference" or
            "what did we discuss about Roosevelt".
        limit: max results.
    """
    store = _get_store()
    try:
        results = store.semantic_search(await embeddings.embed_async(query), limit=limit)
    except Exception:  # noqa: BLE001
        logger.exception("Semantic recall failed")
        return "Memory search is unavailable right now."
    if not results:
        return "Nothing relevant found in memory."
    lines = []
    for item in results:
        when = datetime.fromtimestamp(item["created_at"]).strftime("%b %d %H:%M")
        lines.append(f"[{when}] {store._memory_line(item)[2:]}")
    return "\n".join(lines)


@tool
async def forget_memory(description: str) -> str:
    """Delete a remembered fact that matches the description.

    Args:
        description: what to forget, e.g. "my seat preference".
    """
    store = _get_store()
    try:
        results = store.semantic_search(
            await embeddings.embed_async(description), limit=3, max_distance=0.7
        )
    except Exception:  # noqa: BLE001
        return "Memory search is unavailable right now."
    facts = [r for r in results if r["kind"] == "preference"]
    if not facts:
        return "No matching remembered fact found."
    target = facts[0]
    store.delete_memory(target["id"])
    return f"Forgot: {target['content'].get('text', '')}"


TOOLS = [remember_fact, recall_memories, forget_memory]
