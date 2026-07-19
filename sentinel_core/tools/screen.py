"""Screen awareness: screenshot the primary display and analyze it with a
vision model (Groq qwen3.6-27b — verified multimodal on the current API).
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re

import httpx
from langchain_core.tools import tool

from ..config import get_secret

logger = logging.getLogger(__name__)

VISION_MODEL = os.environ.get("SCREEN_VISION_MODEL", "qwen/qwen3.6-27b")
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_DIMENSION = 1600  # downscale to keep tokens/latency sane

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=90)
    return _client


def _grab_screen_b64() -> str:
    from PIL import ImageGrab

    image = ImageGrab.grab()
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode()


@tool
async def analyze_screen(question: str = "") -> str:
    """Look at the user's screen right now and answer a question about it.

    Args:
        question: what to find out, e.g. "what does this error say?",
            "summarize this article", "what app is open?". Empty = describe
            what's visible.
    """
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        return "Cannot see the screen: GROQ_API_KEY is not configured."
    try:
        import asyncio

        image_b64 = await asyncio.to_thread(_grab_screen_b64)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Screen capture failed")
        return f"Could not capture the screen: {exc}"

    prompt = question.strip() or "Describe what is currently visible on this screen, concisely."
    try:
        response = await _get_client().post(
            GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": VISION_MODEL,
                "temperature": 0.2,
                "max_tokens": 1500,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{prompt}\nThis is a screenshot of the user's "
                                "Windows desktop. Answer directly and concisely.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                            },
                        ],
                    }
                ],
            },
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return _THINK.sub("", text).strip() or "The vision model returned no answer."
    except Exception:
        logger.exception("Vision analysis failed")
        return "Screen analysis failed (vision model error)."


TOOLS = [analyze_screen]
