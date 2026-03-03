# src/tools/notes_tools.py
"""
Notes/Knowledge Agent tools — MongoDB-backed persistent note storage.
Notes live in the 'agent_notes' collection and persist across sessions indefinitely.
"""

import os
from datetime import datetime
from typing import Optional
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()


def _get_notes_collection():
    """Return the notes collection using a lazy MongoClient connection."""
    from pymongo import MongoClient

    uri = os.getenv("MONGODB_CONNECTION_STRING")
    db_name = os.getenv("MONGODB_DATABASE", "sentinel_ai_db")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client[db_name]["agent_notes"]


@tool
def create_note(title: str, content: str, tags: str = "") -> str:
    """
    Creates a new note and saves it to the persistent knowledge base.

    Args:
        title: Short descriptive title for the note
        content: Full content/body of the note
        tags: Comma-separated tags for categorisation (e.g. "work,ideas,shopping")
    """
    try:
        col = _get_notes_collection()
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        doc = {
            "title": title.strip(),
            "content": content.strip(),
            "tags": tag_list,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        result = col.insert_one(doc)
        note_id = str(result.inserted_id)
        tag_str = f"\n🏷️  Tags: {', '.join(tag_list)}" if tag_list else ""
        return f"✅ **Note saved!**\n\n📝 Title: {title}\n🆔 ID: {note_id}{tag_str}"
    except Exception as e:
        return f"Error saving note: {e}"


@tool
def search_notes(query: str) -> str:
    """
    Searches notes by keyword across title, content, and tags.

    Args:
        query: Search term or phrase to look for in your notes
    """
    try:
        col = _get_notes_collection()
        # Create a text index if it doesn't exist
        col.create_index(
            [("title", "text"), ("content", "text"), ("tags", "text")], default_language="english"
        )

        cursor = (
            col.find({"$text": {"$search": query}}, {"score": {"$meta": "textScore"}})
            .sort([("score", {"$meta": "textScore"})])
            .limit(10)
        )

        notes = list(cursor)
        if not notes:
            # Fallback: regex search
            import re

            pattern = re.compile(query, re.IGNORECASE)
            notes = list(
                col.find(
                    {
                        "$or": [
                            {"title": {"$regex": pattern}},
                            {"content": {"$regex": pattern}},
                            {"tags": {"$in": [query.lower()]}},
                        ]
                    }
                ).limit(10)
            )

        if not notes:
            return f"🔍 No notes found matching '{query}'."

        result = f"🔍 **Search results for '{query}'** ({len(notes)} found)\n\n"
        for note in notes:
            nid = str(note["_id"])
            title = note.get("title", "Untitled")
            content = note.get("content", "")
            preview = content[:120] + "..." if len(content) > 120 else content
            date = note.get("updated_at", note.get("created_at", ""))
            date_str = date.strftime("%b %d, %Y") if hasattr(date, "strftime") else str(date)
            tags = ", ".join(note.get("tags", []))
            result += f"📝 **{title}** (ID: `{nid}`)\n"
            result += f"   {preview}\n"
            if tags:
                result += f"   🏷️ {tags}"
            result += f"   📅 {date_str}\n\n"

        return result.strip()
    except Exception as e:
        return f"Error searching notes: {e}"


@tool
def list_notes(limit: int = 10) -> str:
    """
    Lists your most recent notes with title, date, and a short preview.

    Args:
        limit: Maximum number of notes to return (1-50, default 10)
    """
    try:
        limit = max(1, min(50, limit))
        col = _get_notes_collection()
        notes = list(col.find().sort("created_at", -1).limit(limit))

        if not notes:
            return "📭 You have no notes yet. Use 'create note' to get started!"

        result = f"📚 **Your Notes** (showing {len(notes)})\n\n"
        for note in notes:
            nid = str(note["_id"])
            title = note.get("title", "Untitled")
            content = note.get("content", "")
            preview = content[:80] + "..." if len(content) > 80 else content
            date = note.get("created_at", "")
            date_str = date.strftime("%b %d") if hasattr(date, "strftime") else str(date)
            tags = " ".join(f"#{t}" for t in note.get("tags", []))
            result += f"[{date_str}] **{title}** (ID: `{nid}`)\n"
            result += f"  {preview}\n"
            if tags:
                result += f"  {tags}\n"
            result += "\n"

        return result.strip()
    except Exception as e:
        return f"Error listing notes: {e}"


@tool
def get_note(note_id: str) -> str:
    """
    Retrieves the full content of a specific note by its ID.

    Args:
        note_id: The note ID returned when it was created or listed
    """
    try:
        from bson import ObjectId

        col = _get_notes_collection()
        try:
            oid = ObjectId(note_id)
        except Exception:
            return f"❌ Invalid note ID format: {note_id}"

        note = col.find_one({"_id": oid})
        if not note:
            return f"❌ No note found with ID: {note_id}"

        title = note.get("title", "Untitled")
        content = note.get("content", "")
        tags = ", ".join(note.get("tags", []))
        created = note.get("created_at", "")
        updated = note.get("updated_at", "")
        created_str = (
            created.strftime("%B %d, %Y %I:%M %p") if hasattr(created, "strftime") else str(created)
        )
        updated_str = (
            updated.strftime("%B %d, %Y %I:%M %p") if hasattr(updated, "strftime") else str(updated)
        )

        result = f"📝 **{title}**\n\n"
        result += f"{content}\n\n"
        if tags:
            result += f"🏷️ Tags: {tags}\n"
        result += f"📅 Created: {created_str}\n"
        result += f"✏️ Updated: {updated_str}"
        return result
    except Exception as e:
        return f"Error retrieving note: {e}"


@tool
def update_note(
    note_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """
    Updates an existing note's title, content, or tags.

    Args:
        note_id: The ID of the note to update
        title: New title (leave empty to keep existing)
        content: New content (leave empty to keep existing)
        tags: New comma-separated tags (leave empty to keep existing)
    """
    try:
        from bson import ObjectId

        col = _get_notes_collection()
        try:
            oid = ObjectId(note_id)
        except Exception:
            return f"❌ Invalid note ID format: {note_id}"

        updates = {"updated_at": datetime.utcnow()}
        if title and title.strip():
            updates["title"] = title.strip()
        if content and content.strip():
            updates["content"] = content.strip()
        if tags is not None:
            updates["tags"] = [t.strip().lower() for t in tags.split(",") if t.strip()]

        if len(updates) == 1:  # Only updated_at, nothing else
            return "❌ Please provide at least one field to update (title, content, or tags)."

        result = col.update_one({"_id": oid}, {"$set": updates})
        if result.matched_count == 0:
            return f"❌ No note found with ID: {note_id}"

        return f"✅ Note `{note_id}` updated successfully."
    except Exception as e:
        return f"Error updating note: {e}"


@tool
def delete_note(note_id: str) -> str:
    """
    Permanently deletes a note by its ID.

    Args:
        note_id: The ID of the note to delete
    """
    try:
        from bson import ObjectId

        col = _get_notes_collection()
        try:
            oid = ObjectId(note_id)
        except Exception:
            return f"❌ Invalid note ID format: {note_id}"

        note = col.find_one({"_id": oid}, {"title": 1})
        if not note:
            return f"❌ No note found with ID: {note_id}"

        col.delete_one({"_id": oid})
        return f"🗑️ Note '{note.get('title', note_id)}' deleted."
    except Exception as e:
        return f"Error deleting note: {e}"


notes_tools = [
    create_note,
    search_notes,
    list_notes,
    get_note,
    update_note,
    delete_note,
]
