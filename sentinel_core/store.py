"""Local-first SQLite storage: settings overrides, chat history, agent memory, notes.

Replaces the legacy MongoDB dependency. Synchronous sqlite3 wrapped with
``asyncio.to_thread`` at the call sites that need it; SQLite in WAL mode is
fast enough for a single-user desktop service.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .config import data_dir

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

    # -- agent memory -------------------------------------------------------
    def add_memory(
        self,
        kind: str,
        content: dict,
        agent: str | None = None,
        session_id: str | None = None,
        ttl_hours: float | None = 24,
    ) -> None:
        expires = time.time() + ttl_hours * 3600 if ttl_hours else None
        self._execute(
            "INSERT INTO memory(session_id, kind, agent, content, created_at, expires_at) "
            "VALUES(?,?,?,?,?,?)",
            (session_id, kind, agent, json.dumps(content), time.time(), expires),
        )

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
        return cur.rowcount

    def context_block(self, minutes: int = 30) -> str:
        """Compact '[Recent Activity]' block injected into agent prompts."""
        items = self.recent_memory(minutes=minutes)
        if not items:
            return ""
        lines = []
        for item in items:
            content = item["content"]
            if item["kind"] == "command":
                lines.append(f'• User asked: "{content.get("command", "")}"')
            elif item["kind"] == "agent_action":
                tools = ", ".join(content.get("tools_used", [])) or "no tools"
                output = content.get("output", "")[:150]
                lines.append(f"• {item['agent']} agent ({tools}): {output}")
            elif item["kind"] == "preference":
                lines.append(f"• Preference: {content.get('text', '')}")
        return "[Recent Activity]\n" + "\n".join(lines)
