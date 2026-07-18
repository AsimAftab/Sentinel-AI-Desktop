"""Notes tools for the Notes agent — SQLite-backed via ``sentinel_core.store.Store``.

Notes persist indefinitely in the local ``notes`` table (id, title, body, tags,
created_at, updated_at). Tools are sync (sqlite is fast and local); they return
short human-readable strings and never raise.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from langchain_core.tools import tool

from sentinel_core.store import Store

logger = logging.getLogger(__name__)

_store: Store | None = None


def _get_store() -> Store:
    """Lazy module-level Store singleton (WAL mode makes a second connection safe)."""
    global _store
    if _store is None:
        _store = Store()
    return _store


def _normalize_tags(tags: str) -> str:
    """Comma-separated input -> canonical 'a,b,c' lowercase form."""
    return ",".join(t.strip().lower() for t in tags.split(",") if t.strip())


def _fmt_date(ts: float, fmt: str = "%b %d, %Y") -> str:
    try:
        return datetime.fromtimestamp(ts).strftime(fmt)
    except (TypeError, ValueError, OSError):
        return "unknown date"


def _preview(body: str, length: int = 100) -> str:
    body = body.replace("\n", " ").strip()
    return body[:length] + "..." if len(body) > length else body


@tool
def create_note(title: str, body: str, tags: str = "") -> str:
    """Create a new note in the persistent local knowledge base.

    Use when the user asks to remember, save, or note down something.

    Args:
        title: Short descriptive title.
        body: Full content of the note.
        tags: Optional comma-separated tags, e.g. "work,ideas".
    """
    try:
        if not title.strip():
            return "Cannot create a note without a title."
        now = time.time()
        cur = _get_store()._execute(
            "INSERT INTO notes(title, body, tags, created_at, updated_at) VALUES(?,?,?,?,?)",
            (title.strip(), body.strip(), _normalize_tags(tags), now, now),
        )
        tag_str = f" (tags: {_normalize_tags(tags)})" if _normalize_tags(tags) else ""
        return f"Note saved: '{title.strip()}' with ID {cur.lastrowid}{tag_str}."
    except Exception as exc:
        logger.warning("create_note failed: %s", exc)
        return f"Error saving note: {exc}"


@tool
def list_notes(limit: int = 10) -> str:
    """List the most recent notes with ID, title, date, tags, and a preview.

    Use when the user asks what notes they have.

    Args:
        limit: Maximum number of notes to return (1-50, default 10).
    """
    try:
        limit = max(1, min(50, limit))
        rows = _get_store()._query(
            "SELECT id, title, body, tags, created_at FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        if not rows:
            return "You have no notes yet. Use create_note to add one."
        lines = [f"Your notes (showing {len(rows)}):"]
        for r in rows:
            tags = f" [tags: {r['tags']}]" if r["tags"] else ""
            lines.append(
                f"#{r['id']} {r['title']} ({_fmt_date(r['created_at'], '%b %d')}){tags}\n"
                f"   {_preview(r['body'])}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("list_notes failed: %s", exc)
        return f"Error listing notes: {exc}"


@tool
def search_notes(query: str, limit: int = 10) -> str:
    """Search notes by keyword across title, body, and tags.

    Use when the user asks to find a note about a topic.

    Args:
        query: Keyword or phrase to search for.
        limit: Maximum number of matches (1-25, default 10).
    """
    try:
        limit = max(1, min(25, limit))
        pattern = f"%{query.strip()}%"
        rows = _get_store()._query(
            "SELECT id, title, body, tags, updated_at FROM notes "
            "WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (pattern, pattern, pattern, limit),
        )
        if not rows:
            return f"No notes found matching '{query}'."
        lines = [f"Notes matching '{query}' ({len(rows)} found):"]
        for r in rows:
            tags = f" [tags: {r['tags']}]" if r["tags"] else ""
            lines.append(
                f"#{r['id']} {r['title']} ({_fmt_date(r['updated_at'])}){tags}\n"
                f"   {_preview(r['body'])}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("search_notes failed: %s", exc)
        return f"Error searching notes: {exc}"


@tool
def get_note(note_id: int) -> str:
    """Retrieve the full content of one note by its numeric ID.

    Use after list_notes or search_notes when the user wants the whole note.

    Args:
        note_id: The note's ID (shown as #N in listings).
    """
    try:
        rows = _get_store()._query(
            "SELECT id, title, body, tags, created_at, updated_at FROM notes WHERE id=?",
            (note_id,),
        )
        if not rows:
            return f"No note found with ID {note_id}."
        r = rows[0]
        parts = [f"Note #{r['id']}: {r['title']}", "", r["body"]]
        if r["tags"]:
            parts += ["", f"Tags: {r['tags']}"]
        parts += [
            f"Created: {_fmt_date(r['created_at'], '%B %d, %Y %I:%M %p')}",
            f"Updated: {_fmt_date(r['updated_at'], '%B %d, %Y %I:%M %p')}",
        ]
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("get_note failed: %s", exc)
        return f"Error retrieving note: {exc}"


@tool
def update_note(
    note_id: int,
    title: str | None = None,
    body: str | None = None,
    tags: str | None = None,
) -> str:
    """Update a note's title, body, and/or tags. Unspecified fields are kept.

    Args:
        note_id: The note's ID.
        title: New title, or omit to keep the current one.
        body: New body text, or omit to keep the current one.
        tags: New comma-separated tags (empty string clears tags), or omit.
    """
    try:
        sets: list[str] = []
        params: list[object] = []
        if title is not None and title.strip():
            sets.append("title=?")
            params.append(title.strip())
        if body is not None and body.strip():
            sets.append("body=?")
            params.append(body.strip())
        if tags is not None:
            sets.append("tags=?")
            params.append(_normalize_tags(tags))
        if not sets:
            return "Nothing to update: provide a new title, body, or tags."

        sets.append("updated_at=?")
        params.append(time.time())
        params.append(note_id)
        cur = _get_store()._execute(f"UPDATE notes SET {', '.join(sets)} WHERE id=?", tuple(params))
        if cur.rowcount == 0:
            return f"No note found with ID {note_id}."
        return f"Note #{note_id} updated."
    except Exception as exc:
        logger.warning("update_note failed: %s", exc)
        return f"Error updating note: {exc}"


@tool
def delete_note(note_id: int) -> str:
    """Permanently delete a note by its numeric ID.

    Args:
        note_id: The note's ID (shown as #N in listings).
    """
    try:
        store = _get_store()
        rows = store._query("SELECT title FROM notes WHERE id=?", (note_id,))
        if not rows:
            return f"No note found with ID {note_id}."
        store._execute("DELETE FROM notes WHERE id=?", (note_id,))
        return f"Deleted note #{note_id} ('{rows[0]['title']}')."
    except Exception as exc:
        logger.warning("delete_note failed: %s", exc)
        return f"Error deleting note: {exc}"


TOOLS = [
    create_note,
    list_notes,
    search_notes,
    get_note,
    update_note,
    delete_note,
]
