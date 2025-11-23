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

        # Context file locations (write to both for reliability)
        self.context_paths = [
            self.project_root / "user_context.json",  # Project root
            self.frontend_dir / "user_context.json",  # Frontend dir
            self.project_root / "Sentinel-AI-Backend" / "user_context.json",  # Backend dir
        ]

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

        # Write to all locations
        for path in self.context_paths:
            try:
                # Create directory if needed
                path.parent.mkdir(parents=True, exist_ok=True)

                with open(path, 'w') as f:
                    json.dump(context, f, indent=2)

                print(f"✅ User context written to: {path}")
            except Exception as e:
                print(f"⚠️ Failed to write context to {path}: {e}")

    def clear_user_context(self):
        """Clear user context (called on logout)."""
        context = {
            "current_user_id": None,
            "user_id": None,
            "username": None,
            "session_active": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        for path in self.context_paths:
            try:
                if path.exists():
                    with open(path, 'w') as f:
                        json.dump(context, f, indent=2)
                    print(f"✅ User context cleared: {path}")
            except Exception as e:
                print(f"⚠️ Failed to clear context at {path}: {e}")

    def read_user_context(self) -> dict:
        """Read current user context (for debugging)."""
        for path in self.context_paths:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    print(f"⚠️ Failed to read context from {path}: {e}")

        return {"current_user_id": None, "session_active": False}
