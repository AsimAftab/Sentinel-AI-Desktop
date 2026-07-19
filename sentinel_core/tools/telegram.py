"""Telegram messaging via the user's own bot (Bot API over HTTPS).

Setup (one-time, telegram_setup_status explains it in-app):
1. In Telegram, talk to @BotFather -> /newbot -> copy the token.
2. Message your new bot once, then save secrets TELEGRAM_BOT_TOKEN and
   TELEGRAM_CHAT_ID (your chat id — get it from the getUpdates output or
   @userinfobot) via Settings or the /secrets endpoint.
"""

from __future__ import annotations

import logging

import httpx
from langchain_core.tools import tool

from ..config import get_secret

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20)
    return _client


def _config() -> tuple[str, str] | str:
    token = get_secret("TELEGRAM_BOT_TOKEN")
    chat_id = get_secret("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return (
            "Telegram is not set up. Steps: 1) create a bot with @BotFather and "
            "copy its token; 2) send your bot any message; 3) save secrets "
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Sentinel."
        )
    return token, chat_id


@tool
def telegram_setup_status() -> str:
    """Whether Telegram messaging is configured, with setup steps if not."""
    config = _config()
    return "Telegram is configured and ready." if isinstance(config, tuple) else config


@tool
async def send_telegram_message(text: str) -> str:
    """Send a Telegram message to the user's configured chat.

    Args:
        text: message content (plain text).
    """
    config = _config()
    if isinstance(config, str):
        return config
    token, chat_id = config
    try:
        response = await _get_client().post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
        )
        body = response.json()
        if body.get("ok"):
            return "Message sent on Telegram."
        return f"Telegram error: {body.get('description', 'unknown')}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram send failed")
        return f"Could not reach Telegram: {exc}"


@tool
async def read_telegram_messages(limit: int = 10) -> str:
    """Read the most recent messages sent to the user's Telegram bot.

    Args:
        limit: max messages to return.
    """
    config = _config()
    if isinstance(config, str):
        return config
    token, _chat_id = config
    try:
        response = await _get_client().get(
            f"https://api.telegram.org/bot{token}/getUpdates", params={"limit": 100}
        )
        body = response.json()
        if not body.get("ok"):
            return f"Telegram error: {body.get('description', 'unknown')}"
        messages = []
        for update in body.get("result", []):
            msg = update.get("message") or {}
            if msg.get("text"):
                sender = (msg.get("from") or {}).get("first_name", "?")
                messages.append(f"{sender}: {msg['text']}")
        if not messages:
            return "No recent messages."
        return "\n".join(messages[-limit:])
    except Exception as exc:  # noqa: BLE001
        logger.exception("Telegram read failed")
        return f"Could not reach Telegram: {exc}"


TOOLS = [telegram_setup_status, send_telegram_message, read_telegram_messages]
