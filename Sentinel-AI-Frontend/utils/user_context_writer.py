# utils/user_context_writer.py
# Helper to write user context for backend consumption

import json
import os
from datetime import datetime
from pathlib import Path


class UserContextWriter:
    """
    Writes user context to a JSON file that the backend can read.
    This enables the backend to know which user is currently logged in.
    """

    def __init__(self):
        # Get project root (parent of Frontend directory)
        self.frontend_dir = Path(__file__).parent.parent
        self.project_root = self.frontend_dir.parent

        # Single canonical location for user context
        self.context_path = self.project_root / "user_context.json"

    def write_user_context(self, user_id: str, username: str, additional_data: dict = None):
        """
        Write current user context to file.

        Args:
            user_id: User's database ID
            username: User's username
            additional_data: Optional additional context data
        """
        context = {
            "current_user_id": str(user_id),
            "user_id": str(user_id),  # Duplicate for compatibility
            "username": username,
            "session_active": True,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if additional_data:
            context.update(additional_data)

        # Write to canonical location
        try:
            # Create directory if needed
            self.context_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.context_path, 'w') as f:
                json.dump(context, f, indent=2)

            print(f"✅ User context written to: {self.context_path}")
        except Exception as e:
            print(f"⚠️ Failed to write user context: {e}")

    def clear_user_context(self):
        """Clear user context (called on logout)."""
        context = {
            "current_user_id": None,
            "user_id": None,
            "username": None,
            "session_active": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            if self.context_path.exists():
                with open(self.context_path, 'w') as f:
                    json.dump(context, f, indent=2)
                print(f"✅ User context cleared: {self.context_path}")
        except Exception as e:
            print(f"⚠️ Failed to clear user context: {e}")

    def read_user_context(self) -> dict:
        """Read current user context (for debugging)."""
        if self.context_path.exists():
            try:
                with open(self.context_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to read user context: {e}")

        return {"current_user_id": None, "session_active": False}
