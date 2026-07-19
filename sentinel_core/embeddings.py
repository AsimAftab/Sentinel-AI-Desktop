"""Local text embeddings (fastembed / bge-small, ONNX on CPU, fully offline
after the one-time model download). Used for semantic memory recall."""

from __future__ import annotations

import asyncio
import logging
import threading

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding

            logger.info("Loading embedding model %s (first run downloads ~130MB)", MODEL_NAME)
            _model = TextEmbedding(MODEL_NAME)
        return _model


def embed(text: str) -> list[float]:
    """Blocking embed of one string."""
    return list(next(iter(_get_model().embed([text]))))


async def embed_async(text: str) -> list[float]:
    return await asyncio.to_thread(embed, text)


def index_in_background(store, memory_id: int, text: str) -> None:
    """Fire-and-forget: embed text and index it for the given memory row.
    Never blocks the caller; silently no-ops outside an event loop."""

    async def _run() -> None:
        try:
            store.index_memory(memory_id, await embed_async(text))
        except Exception:  # noqa: BLE001
            logger.debug("Background memory indexing failed", exc_info=True)

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass


def warmup() -> None:
    """Load the model off the critical path (call via to_thread at startup)."""
    try:
        _get_model()
        logger.info("Embedding model ready")
    except Exception:  # noqa: BLE001 — memory degrades to recency-only
        logger.exception("Embedding model failed to load; semantic memory disabled")
