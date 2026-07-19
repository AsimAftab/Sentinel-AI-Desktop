"""Local-first SQLite storage: settings overrides, chat history, agent memory, notes.

Replaces the legacy MongoDB dependency. Synchronous sqlite3 wrapped with
``asyncio.to_thread`` at the call sites that need it; SQLite in WAL mode is
fast enough for a single-user desktop service.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
import threading
import time
import uuid
from pathlib import Path

from .config import data_dir

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_id TEXT,
    role TEXT NOT NULL,          -- user | assistant | agent | tool
    agent TEXT,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    kind TEXT NOT NULL,          -- command | agent_action | result | error | preference
    agent TEXT,
    content TEXT NOT NULL,       -- JSON
    created_at REAL NOT NULL,
    expires_at REAL              -- NULL = permanent (preferences)
);
CREATE INDEX IF NOT EXISTS idx_memory_time ON memory(created_at);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    due_at REAL NOT NULL,
    created_at REAL NOT NULL,
    fired INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (data_dir() / "sentinel.db")
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        # Per-turn semantically relevant context, set by ChatService before a
        # turn and appended by context_block(). Single-turn-at-a-time desktop
        # service, so a plain attribute is fine.
        self.turn_context = ""
        self._vec_ready = False
        try:
            import sqlite_vec

            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec USING vec0(embedding float[384])"
            )
            self._conn.commit()
            self._vec_ready = True
        except Exception:  # noqa: BLE001 — semantic memory degrades to recency-only
            logger.warning("sqlite-vec unavailable; semantic memory disabled", exc_info=True)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # -- settings overrides -------------------------------------------------
    def get_settings_overrides(self) -> dict:
        rows = self._query("SELECT value FROM settings WHERE key='overrides'")
        return json.loads(rows[0]["value"]) if rows else {}

    def save_settings_overrides(self, overrides: dict) -> None:
        self._execute(
            "INSERT INTO settings(key, value) VALUES('overrides', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(overrides),),
        )

    # -- sessions / messages ------------------------------------------------
    def start_session(self) -> str:
        session_id = uuid.uuid4().hex
        self._execute(
            "INSERT INTO sessions(id, started_at) VALUES(?, ?)", (session_id, time.time())
        )
        return session_id

    def end_session(self, session_id: str) -> None:
        self._execute("UPDATE sessions SET ended_at=? WHERE id=?", (time.time(), session_id))

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        self._execute(
            "INSERT INTO messages(session_id, turn_id, role, agent, content, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (session_id, turn_id, role, agent, content, time.time()),
        )

    def get_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self._query(
            "SELECT role, agent, content, created_at FROM messages "
            "WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        return [dict(r) for r in reversed(rows)]

    # -- reminders ----------------------------------------------------------
    def add_reminder(self, text: str, due_at: float) -> int:
        cur = self._execute(
            "INSERT INTO reminders(text, due_at, created_at) VALUES(?,?,?)",
            (text, due_at, time.time()),
        )
        return int(cur.lastrowid)

    def pending_reminders(self) -> list[dict]:
        rows = self._query(
            "SELECT id, text, due_at FROM reminders WHERE fired=0 ORDER BY due_at LIMIT 50"
        )
        return [dict(r) for r in rows]

    def due_reminders(self) -> list[dict]:
        rows = self._query(
            "SELECT id, text, due_at FROM reminders WHERE fired=0 AND due_at <= ?",
            (time.time(),),
        )
        return [dict(r) for r in rows]

    def mark_reminder_fired(self, reminder_id: int) -> None:
        self._execute("UPDATE reminders SET fired=1 WHERE id=?", (reminder_id,))

    def cancel_reminder(self, reminder_id: int) -> bool:
        cur = self._execute("DELETE FROM reminders WHERE id=? AND fired=0", (reminder_id,))
        return cur.rowcount > 0

    # -- agent memory -------------------------------------------------------
    def add_memory(
        self,
        kind: str,
        content: dict,
        agent: str | None = None,
        session_id: str | None = None,
        ttl_hours: float | None = 24,
    ) -> int:
        expires = time.time() + ttl_hours * 3600 if ttl_hours else None
        cur = self._execute(
            "INSERT INTO memory(session_id, kind, agent, content, created_at, expires_at) "
            "VALUES(?,?,?,?,?,?)",
            (session_id, kind, agent, json.dumps(content), time.time(), expires),
        )
        return int(cur.lastrowid)

    # -- semantic memory (sqlite-vec) ---------------------------------------
    def index_memory(self, memory_id: int, vector: list[float]) -> None:
        if not self._vec_ready:
            return
        try:
            self._execute(
                "INSERT OR REPLACE INTO memory_vec(rowid, embedding) VALUES(?, ?)",
                (memory_id, struct.pack(f"{len(vector)}f", *vector)),
            )
        except Exception:  # noqa: BLE001 — indexing is best-effort
            logger.debug("memory_vec insert failed", exc_info=True)

    def semantic_search(
        self, vector: list[float], limit: int = 5, max_distance: float = 0.95
    ) -> list[dict]:
        """Nearest memories by meaning; excludes expired rows."""
        if not self._vec_ready:
            return []
        now = time.time()
        rows = self._query(
            "SELECT m.id, m.kind, m.agent, m.content, m.created_at, v.distance "
            "FROM (SELECT rowid, distance FROM memory_vec WHERE embedding MATCH ? "
            "      ORDER BY distance LIMIT ?) v "
            "JOIN memory m ON m.id = v.rowid "
            "WHERE (m.expires_at IS NULL OR m.expires_at > ?) AND v.distance <= ?",
            (struct.pack(f"{len(vector)}f", *vector), limit * 2, now, max_distance),
        )
        out = []
        for r in rows[:limit]:
            item = dict(r)
            item["content"] = json.loads(item["content"])
            out.append(item)
        return out

    def delete_memory(self, memory_id: int) -> bool:
        cur = self._execute("DELETE FROM memory WHERE id=?", (memory_id,))
        if self._vec_ready:
            self._execute("DELETE FROM memory_vec WHERE rowid=?", (memory_id,))
        return cur.rowcount > 0

    def recent_memory(self, minutes: int = 30, limit: int = 12) -> list[dict]:
        now = time.time()
        rows = self._query(
            "SELECT kind, agent, content, created_at FROM memory "
            "WHERE created_at >= ? AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY id DESC LIMIT ?",
            (now - minutes * 60, now, limit),
        )
        out = []
        for r in reversed(rows):
            item = dict(r)
            item["content"] = json.loads(item["content"])
            out.append(item)
        return out

    def prune_memory(self) -> int:
        cur = self._execute(
            "DELETE FROM memory WHERE expires_at IS NOT NULL AND expires_at < ?", (time.time(),)
        )
        if self._vec_ready:
            self._execute("DELETE FROM memory_vec WHERE rowid NOT IN (SELECT id FROM memory)")
        return cur.rowcount

    @staticmethod
    def _memory_line(item: dict) -> str:
        content = item["content"]
        if item["kind"] == "command":
            return f'• User asked: "{content.get("command", "")}"'
        if item["kind"] == "agent_action":
            tools = ", ".join(content.get("tools_used", [])) or "no tools"
            return f"• {item['agent']} agent ({tools}): {content.get('output', '')[:150]}"
        if item["kind"] == "preference":
            return f"• Remembered: {content.get('text', '')}"
        if item["kind"] == "result":
            return f"• Sentinel replied: {content.get('response', '')[:150]}"
        return f"• {item['kind']}: {json.dumps(content)[:150]}"

    def context_block(self, minutes: int = 30) -> str:
        """'[Recent Activity]' (recency) + '[Relevant Memory]' (semantic, set
        per-turn by ChatService) — injected into agent prompts."""
        parts = []
        items = self.recent_memory(minutes=minutes)
        if items:
            parts.append("[Recent Activity]\n" + "\n".join(self._memory_line(i) for i in items))
        if self.turn_context:
            parts.append(self.turn_context)
        return "\n\n".join(parts)
