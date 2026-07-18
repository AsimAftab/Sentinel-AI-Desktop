"""Sentinel Core tool modules.

Conventions (enforced by review, consumed by agents.registry):
- Each module exposes a module-level ``TOOLS: list`` of langchain ``@tool`` functions.
- Tools are ``async def`` wherever the underlying I/O allows.
- Tools never raise: they return a short human-readable error string instead
  (never a traceback).
- No prints; use ``logging``. No blocking ``time.sleep``. No pyautogui.
"""
