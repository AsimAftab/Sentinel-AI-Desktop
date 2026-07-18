"""Workspace definitions — named app groups like "dev mode".

Stored as JSON at data_dir()/workspaces.json. The same file is read by the
sentinel-mcp-windows server (workspace_* tools), so voice/chat and the GUI
share one source of truth.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .config import data_dir


def _path() -> Path:
    return data_dir() / "workspaces.json"


def load_workspaces() -> dict:
    path = _path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — corrupt file shouldn't brick the API
        return {}


def save_workspaces(workspaces: dict) -> None:
    path = _path()
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(workspaces, f, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
