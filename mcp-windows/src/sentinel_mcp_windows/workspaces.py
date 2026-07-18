"""App workspaces: named sets of apps + URLs that can be launched together.

Stored as JSON at %LOCALAPPDATA%\\SentinelAI\\workspaces.json with schema:
{"<name>": {"apps": [{"name": str, "app_id": str}], "urls": [str]}}
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from .server import _get_start_apps, _launch_app_id, _resolve_start_app, mcp

logger = logging.getLogger("sentinel-mcp-windows.workspaces")


def _store_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "SentinelAI" / "workspaces.json"


def _load_workspaces() -> dict[str, dict]:
    path = _store_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load workspaces.json; treating as empty")
        return {}


def _save_workspaces(workspaces: dict[str, dict]) -> None:
    """Atomic write via temp file + os.replace."""
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(workspaces, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _find_workspace(workspaces: dict[str, dict], name: str) -> str | None:
    """Case-insensitive workspace name lookup; returns the stored key or None."""
    lname = name.strip().lower()
    for key in workspaces:
        if key.lower() == lname:
            return key
    return None


@mcp.tool()
def workspace_list() -> str:
    """List saved workspaces with their app and URL counts."""
    try:
        workspaces = _load_workspaces()
        if not workspaces:
            return "No workspaces saved yet. Use workspace_save to create one."
        lines = []
        for name, ws in sorted(workspaces.items(), key=lambda kv: kv[0].lower()):
            apps = ws.get("apps", [])
            urls = ws.get("urls", [])
            app_names = ", ".join(a.get("name", "?") for a in apps) or "none"
            lines.append(f"{name}: {len(apps)} app(s) ({app_names}), {len(urls)} URL(s)")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("workspace_list failed")
        return f"Error listing workspaces: {e}"


@mcp.tool()
def workspace_open(name: str) -> str:
    """Open a saved workspace: launch all its apps and open all its URLs."""
    try:
        workspaces = _load_workspaces()
        key = _find_workspace(workspaces, name)
        if key is None:
            if not workspaces:
                return f"No workspace named '{name}' (no workspaces saved yet)."
            options = ", ".join(sorted(workspaces))
            return f"No workspace named '{name}'. Available: {options}"

        ws = workspaces[key]
        launched: list[str] = []
        failed: list[str] = []

        for app in ws.get("apps", []):
            app_name = app.get("name", "?")
            app_id = app.get("app_id", "")
            try:
                if not app_id:
                    raise ValueError("missing app_id")
                _launch_app_id(app_id)
                launched.append(app_name)
            except Exception as e:
                logger.warning("workspace_open: failed to launch %s: %s", app_name, e)
                failed.append(f"{app_name} (app)")

        for url in ws.get("urls", []):
            try:
                if urlparse(url).scheme not in ("http", "https"):
                    raise ValueError("only http/https URLs are opened")
                os.startfile(url)  # noqa: S606 - opens in default browser
                launched.append(url)
            except Exception as e:
                logger.warning("workspace_open: failed to open %s: %s", url, e)
                failed.append(f"{url} (url)")

        if not launched and not failed:
            return f"Workspace '{key}' is empty."
        parts = [f"Workspace '{key}':"]
        if launched:
            parts.append(f"launched {len(launched)} item(s): " + ", ".join(launched))
        if failed:
            parts.append(f"failed: {', '.join(failed)}")
        return " ".join(parts)
    except Exception as e:
        logger.exception("workspace_open failed")
        return f"Error opening workspace: {e}"


@mcp.tool()
def workspace_save(name: str, app_names: list[str], urls: list[str] = []) -> str:  # noqa: B006
    """Save (or overwrite) a workspace with the given app names and URLs.

    Each app name is resolved against installed apps; unresolved names are reported.
    """
    try:
        name = name.strip()
        if not name:
            return "Error: workspace name cannot be empty."
        if not app_names and not urls:
            return "Error: provide at least one app name or URL."

        bad_urls = [u for u in urls if urlparse(u).scheme not in ("http", "https")]
        if bad_urls:
            return f"Error: only http/https URLs are allowed: {', '.join(bad_urls)}"

        installed = _get_start_apps()
        resolved: list[dict[str, str]] = []
        unresolved: list[str] = []
        for app_name in app_names:
            app, error = _resolve_start_app(app_name, installed)
            if app is None:
                unresolved.append(f"{app_name} ({error})")
            else:
                resolved.append({"name": app["Name"], "app_id": app["AppID"]})

        if not resolved and not urls:
            return "Error: no apps could be resolved. " + "; ".join(unresolved)

        workspaces = _load_workspaces()
        existing = _find_workspace(workspaces, name)
        if existing is not None:
            del workspaces[existing]
        workspaces[name] = {"apps": resolved, "urls": list(urls)}
        _save_workspaces(workspaces)

        msg = (f"Saved workspace '{name}' with {len(resolved)} app(s) "
               f"and {len(urls)} URL(s).")
        if unresolved:
            msg += " Unresolved: " + "; ".join(unresolved)
        return msg
    except Exception as e:
        logger.exception("workspace_save failed")
        return f"Error saving workspace: {e}"


@mcp.tool()
def workspace_delete(name: str) -> str:
    """Delete a saved workspace by name (case-insensitive)."""
    try:
        workspaces = _load_workspaces()
        key = _find_workspace(workspaces, name)
        if key is None:
            return f"No workspace named '{name}'."
        del workspaces[key]
        _save_workspaces(workspaces)
        return f"Deleted workspace '{key}'."
    except Exception as e:
        logger.exception("workspace_delete failed")
        return f"Error deleting workspace: {e}"
