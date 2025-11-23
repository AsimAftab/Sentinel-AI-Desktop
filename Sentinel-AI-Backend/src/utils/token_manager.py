# src/utils/token_manager.py

import os
import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Try to import MongoDB - fall back to file-based if not available
try:
    from pymongo import MongoClient
    from bson import ObjectId
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    print("⚠️ pymongo not installed. Tokens will use file-based fallback.")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class TokenManager:
    """
    Simplified token management for backend.
    Retrieves tokens from MongoDB (preferred) or falls back to file-based tokens.
    No encryption - tokens stored as plain JSON strings.
    """

    def __init__(self):
        self.mongodb_available = MONGODB_AVAILABLE
        self.db_client = None
        self.db = None
        self.tokens_collection = None

        # Setup MongoDB connection if available
        if MONGODB_AVAILABLE:
            try:
                connection_string = os.getenv("MONGODB_CONNECTION_STRING")
                if connection_string:
                    self.db_client = MongoClient(connection_string)
                    db_name = os.getenv("MONGODB_DATABASE", "sentinel_ai_db")
                    self.db = self.db_client[db_name]
                    self.tokens_collection = self.db.get_collection(
                        os.getenv("MONGODB_COLLECTION_TOKENS", "service_tokens")
                    )
                    log.info("✅ TokenManager connected to MongoDB")
                else:
                    log.warning("⚠️ MONGODB_CONNECTION_STRING not found in environment")
                    self.mongodb_available = False
            except Exception as e:
                log.exception("Failed to connect to MongoDB: %s", e)
                self.mongodb_available = False

        # File paths for fallback
        self.backend_dir = Path(__file__).parent.parent.parent
        self.frontend_dir = self.backend_dir.parent / "Sentinel-AI-Frontend"

    def get_user_id_from_context(self) -> Optional[str]:
        """
        Get current user_id from user context file.
        This file is written by the frontend when a user logs in.
        """
        # Single canonical location at project root
        context_path = self.backend_dir.parent / "user_context.json"

        if context_path.exists():
            try:
                with open(context_path, 'r') as f:
                    context = json.load(f)
                    user_id = context.get("current_user_id") or context.get("user_id")
                    if user_id:
                        log.info("✅ Found user_id from context: %s", user_id)
                        return str(user_id)
            except Exception as e:
                log.warning("Failed to read user context from %s: %s", context_path, e)

        log.warning("⚠️ No user context found. Tokens will not be user-specific.")
        return None

    def get_token_from_db(self, service_name: str, user_id: Optional[str] = None) -> Optional[dict]:
        """
        Retrieve token from MongoDB.
        Tokens are stored as plain JSON strings (no encryption).
        """
        if not self.mongodb_available or self.tokens_collection is None:
            return None

        try:
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id  # fallback to string

            # Get most recent token
            doc = self.tokens_collection.find_one(query, sort=[("created_at", -1)])

            if not doc:
                log.warning("No token found in DB for service=%s user_id=%s", service_name, user_id)
                return None

            # Parse JSON string to dict
            token_str = doc["token"]
            if isinstance(token_str, bytes):
                # Handle legacy binary tokens (migration path)
                token_dict = json.loads(token_str.decode('utf-8'))
            else:
                # New plain JSON string format
                token_dict = json.loads(token_str)

            log.info("✅ Retrieved token from DB for service=%s user_id=%s", service_name, user_id)
            return token_dict

        except Exception as e:
            log.exception("Failed to get token from DB: %s", e)
            return None

    def get_token_from_file(self, token_path: Path) -> Optional[dict]:
        """
        Fallback: retrieve token from file (token.json).
        """
        if not token_path.exists():
            return None

        try:
            with open(token_path, 'r') as f:
                token_dict = json.load(f)
                log.info("✅ Retrieved token from file: %s", token_path)
                return token_dict
        except Exception as e:
            log.warning("Failed to read token from file %s: %s", token_path, e)
            return None

    def get_calendar_credentials(self, user_id: Optional[str] = None, scopes: list = None) -> Optional[Credentials]:
        """
        Get Google Calendar credentials for a user.
        Tries MongoDB first, then falls back to file-based tokens.

        Args:
            user_id: User ID to retrieve token for (if None, uses context)
            scopes: OAuth scopes (defaults to Calendar scopes)

        Returns:
            Credentials object or None
        """
        if scopes is None:
            scopes = [
                'https://www.googleapis.com/auth/calendar',
                'https://www.googleapis.com/auth/calendar.events'
            ]

        # Auto-detect user_id if not provided
        if user_id is None:
            user_id = self.get_user_id_from_context()

        # Try MongoDB first
        token_dict = self.get_token_from_db("GMeet", user_id)

        # Fallback to file if DB fails
        if not token_dict:
            log.info("Falling back to file-based tokens...")
            # Check multiple possible locations
            token_paths = [
                self.backend_dir / "token.json",
                self.frontend_dir / "token.json",
            ]

            for token_path in token_paths:
                token_dict = self.get_token_from_file(token_path)
                if token_dict:
                    break

        if not token_dict:
            log.error("❌ No token found in DB or files for user_id=%s", user_id)
            return None

        # Handle "raw" format from meet_service
        if "raw" in token_dict and isinstance(token_dict["raw"], str):
            try:
                token_dict = json.loads(token_dict["raw"])
            except:
                pass

        # Create Credentials object
        try:
            creds = Credentials.from_authorized_user_info(token_dict, scopes)

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    log.info("Token expired, refreshing...")
                    creds.refresh(Request())
                    log.info("✅ Token refreshed successfully")

                    # Save refreshed token back to DB
                    if self.mongodb_available and user_id:
                        try:
                            self._save_refreshed_token(creds, user_id)
                        except Exception as e:
                            log.warning("Failed to save refreshed token to DB: %s", e)

                except Exception as e:
                    log.error("Failed to refresh token: %s", e)
                    return None

            return creds

        except Exception as e:
            log.exception("Failed to create Credentials object: %s", e)
            return None

    def _save_refreshed_token(self, creds: Credentials, user_id: str):
        """Save refreshed token back to database as plain JSON string."""
        if not self.mongodb_available or self.tokens_collection is None:
            return

        try:
            token_dict = json.loads(creds.to_json())

            query = {"service": "GMeet"}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except:
                    query["user_id"] = user_id

            # Update existing token (store as plain JSON string)
            update_doc = {
                "$set": {
                    "token": json.dumps(token_dict),  # Plain JSON string
                    "encrypted": False,
                    "updated_at": datetime.utcnow(),
                    "expires_at": token_dict.get("expires_at") or token_dict.get("expires_in"),
                }
            }

            result = self.tokens_collection.update_one(query, update_doc)
            if result.modified_count > 0:
                log.info("✅ Saved refreshed token to DB")
            else:
                log.warning("Token update returned 0 modified documents")

        except Exception as e:
            log.exception("Failed to save refreshed token: %s", e)

    def close(self):
        """Close database connection."""
        if self.db_client:
            try:
                self.db_client.close()
            except:
                pass


# Singleton instance
_token_manager_instance = None


def get_token_manager() -> TokenManager:
    """Get or create singleton TokenManager instance."""
    global _token_manager_instance
    if _token_manager_instance is None:
        _token_manager_instance = TokenManager()
    return _token_manager_instance
