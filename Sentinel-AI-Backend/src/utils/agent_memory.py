# src/utils/agent_memory.py
"""
Agent Memory Service - Short-term memory for LangGraph agents.

Stores conversation history, agent actions, and tool calls in MongoDB.
Allows agents to know what has been done in the current session and recent past.

Uses existing MongoDB connection from environment variables.
"""

import os
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# Try to import MongoDB
try:
    from pymongo import MongoClient, DESCENDING
    from pymongo.errors import PyMongoError
    from bson import ObjectId
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    print("⚠️ pymongo not installed. Agent memory will use in-memory fallback.")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class MemoryType:
    """Types of memory entries."""
    COMMAND = "command"           # User voice command
    AGENT_ACTION = "agent_action" # Agent was invoked
    TOOL_CALL = "tool_call"       # Tool was called
    RESULT = "result"             # Final result/response
    CONTEXT = "context"           # Contextual information
    ERROR = "error"               # Error occurred


class AgentMemory:
    """
    Short-term memory service for LangGraph agents.

    Features:
    - Stores conversation history per user session
    - Tracks which agents were invoked and what tools they used
    - Provides context injection for agents
    - Auto-expires old memories (TTL)
    - Falls back to in-memory storage if MongoDB unavailable
    """

    # Default TTL: 24 hours (memories auto-expire)
    DEFAULT_TTL_HOURS = 24

    # Collection name
    COLLECTION_NAME = "agent_memory"

    def __init__(self):
        self.mongodb_available = MONGODB_AVAILABLE
        self.db_client = None
        self.db = None
        self.memory_collection = None

        # In-memory fallback storage
        self._memory_fallback: List[Dict] = []

        # Current session tracking
        self._current_session_id: Optional[str] = None
        self._current_user_id: Optional[str] = None

        # Setup MongoDB connection
        if MONGODB_AVAILABLE:
            try:
                connection_string = os.getenv("MONGODB_CONNECTION_STRING")
                if connection_string:
                    self.db_client = MongoClient(connection_string)
                    db_name = os.getenv("MONGODB_DATABASE", "sentinel_ai_db")
                    self.db = self.db_client[db_name]
                    self.memory_collection = self.db[self.COLLECTION_NAME]

                    # Create indexes for efficient queries
                    self._create_indexes()

                    log.info("✅ AgentMemory connected to MongoDB")
                else:
                    log.warning("⚠️ MONGODB_CONNECTION_STRING not found. Using in-memory fallback.")
                    self.mongodb_available = False
            except Exception as e:
                log.exception("Failed to connect to MongoDB: %s", e)
                self.mongodb_available = False

    def _create_indexes(self):
        """Create indexes for efficient queries and TTL expiration."""
        if not self.memory_collection:
            return

        try:
            # Index for user + session queries
            self.memory_collection.create_index([
                ("user_id", DESCENDING),
                ("session_id", DESCENDING),
                ("timestamp", DESCENDING)
            ])

            # Index for user + time-based queries
            self.memory_collection.create_index([
                ("user_id", DESCENDING),
                ("timestamp", DESCENDING)
            ])

            # TTL index - auto-delete documents after expires_at
            self.memory_collection.create_index(
                "expires_at",
                expireAfterSeconds=0  # Delete when expires_at is reached
            )

            log.info("✅ AgentMemory indexes created")
        except PyMongoError as e:
            log.warning("Failed to create indexes (may already exist): %s", e)

    def start_session(self, user_id: Optional[str] = None) -> str:
        """
        Start a new conversation session.

        Args:
            user_id: User ID (optional, will try to get from context)

        Returns:
            session_id: Unique session identifier
        """
        self._current_session_id = str(uuid.uuid4())
        self._current_user_id = user_id or self._get_user_id_from_context()

        log.info("📝 Started new session: %s for user: %s",
                 self._current_session_id, self._current_user_id)

        return self._current_session_id

    def end_session(self):
        """End the current session."""
        if self._current_session_id:
            log.info("📝 Ended session: %s", self._current_session_id)
        self._current_session_id = None

    def _get_user_id_from_context(self) -> Optional[str]:
        """Get current user_id from user context file."""
        backend_dir = Path(__file__).parent.parent.parent
        context_path = backend_dir.parent / "user_context.json"

        if context_path.exists():
            try:
                with open(context_path, 'r') as f:
                    context = json.load(f)
                    return context.get("current_user_id") or context.get("user_id")
            except Exception as e:
                log.warning("Failed to read user context: %s", e)

        return None

    def store(
        self,
        memory_type: str,
        content: Dict[str, Any],
        agent: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None
    ) -> Optional[str]:
        """
        Store a memory entry.

        Args:
            memory_type: Type of memory (command, agent_action, tool_call, result, error)
            content: Memory content (dict with relevant data)
            agent: Agent name (Browser, Music, Meeting, etc.)
            session_id: Session ID (uses current session if not provided)
            user_id: User ID (uses current user if not provided)
            ttl_hours: Hours until memory expires (default: 24)

        Returns:
            memory_id: ID of stored memory entry
        """
        # Use current session/user if not provided
        session_id = session_id or self._current_session_id
        user_id = user_id or self._current_user_id or self._get_user_id_from_context()
        ttl_hours = ttl_hours or self.DEFAULT_TTL_HOURS

        # Build memory document
        now = datetime.utcnow()
        memory_doc = {
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": now,
            "type": memory_type,
            "agent": agent,
            "content": content,
            "expires_at": now + timedelta(hours=ttl_hours)
        }

        # Store in MongoDB or fallback
        if self.mongodb_available and self.memory_collection:
            try:
                result = self.memory_collection.insert_one(memory_doc)
                log.debug("Stored memory: type=%s agent=%s", memory_type, agent)
                return str(result.inserted_id)
            except PyMongoError as e:
                log.error("Failed to store memory in MongoDB: %s", e)
                # Fall through to in-memory

        # In-memory fallback
        memory_doc["_id"] = str(uuid.uuid4())
        self._memory_fallback.append(memory_doc)

        # Cleanup old in-memory entries (keep last 100)
        if len(self._memory_fallback) > 100:
            self._memory_fallback = self._memory_fallback[-100:]

        return memory_doc["_id"]

    def store_command(self, command: str, session_id: Optional[str] = None) -> Optional[str]:
        """Store a user voice command."""
        return self.store(
            memory_type=MemoryType.COMMAND,
            content={"command": command},
            session_id=session_id
        )

    def store_agent_action(
        self,
        agent: str,
        input_text: str,
        output_text: str,
        tools_used: List[str] = None,
        success: bool = True,
        duration_ms: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Store an agent action/invocation."""
        return self.store(
            memory_type=MemoryType.AGENT_ACTION,
            agent=agent,
            content={
                "input": input_text,
                "output": output_text,
                "tools_used": tools_used or [],
                "success": success,
                "duration_ms": duration_ms
            },
            session_id=session_id
        )

    def store_tool_call(
        self,
        agent: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: str,
        success: bool = True,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Store a tool call."""
        return self.store(
            memory_type=MemoryType.TOOL_CALL,
            agent=agent,
            content={
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output[:500] if tool_output else None,  # Truncate long outputs
                "success": success
            },
            session_id=session_id
        )

    def store_error(
        self,
        error_message: str,
        agent: Optional[str] = None,
        context: Optional[Dict] = None,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Store an error."""
        return self.store(
            memory_type=MemoryType.ERROR,
            agent=agent,
            content={
                "error": error_message,
                "context": context
            },
            session_id=session_id
        )

    def get_session_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get memory entries for a specific session.

        Args:
            session_id: Session ID (uses current session if not provided)
            limit: Maximum entries to return

        Returns:
            List of memory entries (oldest first)
        """
        session_id = session_id or self._current_session_id
        if not session_id:
            return []

        if self.mongodb_available and self.memory_collection:
            try:
                cursor = self.memory_collection.find(
                    {"session_id": session_id}
                ).sort("timestamp", 1).limit(limit)

                return list(cursor)
            except PyMongoError as e:
                log.error("Failed to get session history: %s", e)

        # In-memory fallback
        return [m for m in self._memory_fallback if m.get("session_id") == session_id][-limit:]

    def get_recent_memories(
        self,
        user_id: Optional[str] = None,
        minutes: int = 30,
        limit: int = 10,
        memory_types: List[str] = None
    ) -> List[Dict]:
        """
        Get recent memories for a user (across sessions).

        Args:
            user_id: User ID (uses current user if not provided)
            minutes: How far back to look
            limit: Maximum entries to return
            memory_types: Filter by memory types (e.g., ["command", "agent_action"])

        Returns:
            List of memory entries (most recent first)
        """
        user_id = user_id or self._current_user_id or self._get_user_id_from_context()
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        if self.mongodb_available and self.memory_collection:
            try:
                query = {
                    "user_id": user_id,
                    "timestamp": {"$gte": cutoff}
                }

                if memory_types:
                    query["type"] = {"$in": memory_types}

                cursor = self.memory_collection.find(query).sort(
                    "timestamp", DESCENDING
                ).limit(limit)

                return list(cursor)
            except PyMongoError as e:
                log.error("Failed to get recent memories: %s", e)

        # In-memory fallback
        results = [
            m for m in self._memory_fallback
            if m.get("user_id") == user_id and m.get("timestamp", datetime.min) >= cutoff
        ]
        if memory_types:
            results = [m for m in results if m.get("type") in memory_types]
        return sorted(results, key=lambda x: x.get("timestamp", datetime.min), reverse=True)[:limit]

    def get_context_for_agent(
        self,
        agent: Optional[str] = None,
        include_other_agents: bool = True,
        minutes: int = 15,
        max_entries: int = 5
    ) -> str:
        """
        Generate context string to inject into agent prompts.

        This allows agents to know what has been done recently.

        Args:
            agent: Current agent name (to highlight relevant history)
            include_other_agents: Include actions from other agents
            minutes: How far back to look
            max_entries: Maximum entries to include

        Returns:
            Context string to prepend to agent prompt
        """
        memories = self.get_recent_memories(
            minutes=minutes,
            limit=max_entries * 2,  # Get more, then filter
            memory_types=[MemoryType.COMMAND, MemoryType.AGENT_ACTION, MemoryType.RESULT]
        )

        if not memories:
            return ""

        # Build context string
        context_lines = ["[Recent Activity]"]

        for memory in reversed(memories[:max_entries]):  # Oldest first
            mem_type = memory.get("type")
            content = memory.get("content", {})
            mem_agent = memory.get("agent")

            # Skip other agents if not requested
            if not include_other_agents and mem_agent and mem_agent != agent:
                continue

            if mem_type == MemoryType.COMMAND:
                context_lines.append(f"• User asked: \"{content.get('command', '')}\"")

            elif mem_type == MemoryType.AGENT_ACTION:
                action_agent = mem_agent or "Unknown"
                output = content.get("output", "")[:100]  # Truncate
                tools = content.get("tools_used", [])

                if tools:
                    context_lines.append(f"• {action_agent} agent used {', '.join(tools)}: {output}")
                else:
                    context_lines.append(f"• {action_agent} agent responded: {output}")

            elif mem_type == MemoryType.RESULT:
                context_lines.append(f"• Result: {content.get('result', '')[:100]}")

        if len(context_lines) <= 1:
            return ""

        context_lines.append("")  # Empty line before actual prompt
        return "\n".join(context_lines)

    def get_last_command(self, session_id: Optional[str] = None) -> Optional[str]:
        """Get the last user command in the session."""
        session_id = session_id or self._current_session_id

        memories = self.get_recent_memories(
            minutes=60,
            limit=1,
            memory_types=[MemoryType.COMMAND]
        )

        if memories:
            return memories[0].get("content", {}).get("command")
        return None

    def get_agent_history(
        self,
        agent: str,
        minutes: int = 30,
        limit: int = 5
    ) -> List[Dict]:
        """Get recent actions for a specific agent."""
        all_memories = self.get_recent_memories(
            minutes=minutes,
            limit=limit * 3,
            memory_types=[MemoryType.AGENT_ACTION, MemoryType.TOOL_CALL]
        )

        return [m for m in all_memories if m.get("agent") == agent][:limit]

    def clear_session(self, session_id: Optional[str] = None):
        """Clear all memories for a session."""
        session_id = session_id or self._current_session_id
        if not session_id:
            return

        if self.mongodb_available and self.memory_collection:
            try:
                result = self.memory_collection.delete_many({"session_id": session_id})
                log.info("Cleared %d memories for session %s", result.deleted_count, session_id)
            except PyMongoError as e:
                log.error("Failed to clear session: %s", e)

        # In-memory fallback
        self._memory_fallback = [
            m for m in self._memory_fallback if m.get("session_id") != session_id
        ]

    def clear_old_memories(self, hours: int = 24):
        """Manually clear memories older than specified hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        if self.mongodb_available and self.memory_collection:
            try:
                result = self.memory_collection.delete_many({
                    "timestamp": {"$lt": cutoff}
                })
                log.info("Cleared %d old memories", result.deleted_count)
            except PyMongoError as e:
                log.error("Failed to clear old memories: %s", e)

        # In-memory fallback
        self._memory_fallback = [
            m for m in self._memory_fallback
            if m.get("timestamp", datetime.min) >= cutoff
        ]

    def close(self):
        """Close database connection."""
        if self.db_client:
            try:
                self.db_client.close()
            except:
                pass


# Singleton instance
_agent_memory_instance: Optional[AgentMemory] = None


def get_agent_memory() -> AgentMemory:
    """Get or create singleton AgentMemory instance."""
    global _agent_memory_instance
    if _agent_memory_instance is None:
        _agent_memory_instance = AgentMemory()
    return _agent_memory_instance
