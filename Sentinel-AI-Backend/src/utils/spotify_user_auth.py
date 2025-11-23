# src/utils/spotify_user_auth.py

import os
import json
import logging
from typing import Optional
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


class SpotifyUserAuth:
    """
    Utility to get user-specific Spotify client instances.
    Fetches tokens from MongoDB based on current user context.
    """

    def __init__(self):
        # MongoDB configuration
        self.mongodb_uri = os.getenv('MONGODB_CONNECTION_STRING')
        self.db_name = os.getenv('MONGODB_DATABASE', 'sentinel_ai_db')
        self.tokens_collection = os.getenv('MONGODB_COLLECTION_TOKENS', 'service_tokens')

        # Spotify OAuth configuration
        self.client_id = os.getenv('SPOTIPY_CLIENT_ID')
        self.client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
        self.redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI', 'http://localhost:8888/callback')

        # User context file path (at project root, not backend root)
        # Current file: Sentinel-AI-Backend/src/utils/spotify_user_auth.py
        # Backend root: Sentinel-AI-Backend/
        # Project root: Sentinel-AI-Desktop/
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(backend_root)  # Go up one more level
        self.user_context_path = os.path.join(project_root, 'user_context.json')

        # MongoDB client (lazy initialization)
        self._mongo_client = None
        self._db = None
        self._tokens_col = None

    def _init_mongodb(self):
        """Initialize MongoDB connection (lazy)."""
        if self._mongo_client is None:
            try:
                self._mongo_client = MongoClient(self.mongodb_uri)
                self._db = self._mongo_client[self.db_name]
                self._tokens_col = self._db[self.tokens_collection]
                log.info("MongoDB connection initialized for Spotify user auth")
            except Exception as e:
                log.error(f"Failed to initialize MongoDB: {e}")
                raise

    def get_current_user_id(self) -> Optional[str]:
        """Read current user_id from user_context.json."""
        try:
            print(f"🔍 Looking for user_context.json at: {self.user_context_path}")

            if not os.path.exists(self.user_context_path):
                log.warning(f"user_context.json not found at {self.user_context_path}")
                print(f"❌ user_context.json not found at {self.user_context_path}")
                return None

            with open(self.user_context_path, 'r') as f:
                user_context = json.load(f)
                print(f"📄 user_context.json contents: {user_context}")

                user_id = user_context.get('user_id')
                if user_id:
                    log.info(f"Current user_id from context: {user_id}")
                    print(f"✅ Found user_id in context: {user_id}")
                    return user_id
                else:
                    log.warning("No user_id found in user_context.json")
                    print(f"⚠️ No user_id found in user_context.json")
                    return None
        except Exception as e:
            log.error(f"Error reading user_context.json: {e}")
            print(f"❌ Error reading user_context.json: {e}")
            return None

    def get_user_token(self, user_id: str) -> Optional[dict]:
        """Fetch Spotify token from MongoDB for a specific user."""
        try:
            self._init_mongodb()

            # Convert user_id to ObjectId
            try:
                user_obj_id = ObjectId(user_id)
                print(f"🔍 Searching for Spotify token with ObjectId: {user_obj_id}")
            except Exception as e:
                user_obj_id = user_id  # Fallback to string
                print(f"⚠️ Could not convert to ObjectId, using string: {user_id}")

            # Query MongoDB for Spotify token
            query = {
                "service": "Spotify",
                "user_id": user_obj_id
            }

            print(f"🔍 MongoDB query: {query}")
            print(f"🔍 Collection: {self.tokens_collection}")
            print(f"🔍 Database: {self.db_name}")

            token_doc = self._tokens_col.find_one(query, sort=[("created_at", -1)])

            if not token_doc:
                log.warning(f"No Spotify token found for user {user_id}")
                print(f"❌ No Spotify token found in MongoDB for user {user_id}")
                print(f"   Query used: {query}")
                return None

            # Parse token JSON
            token_str = token_doc.get("token")
            if isinstance(token_str, bytes):
                token_dict = json.loads(token_str.decode('utf-8'))
            else:
                token_dict = json.loads(token_str)

            log.info(f"Retrieved Spotify token for user {user_id}")
            print(f"✅ Retrieved Spotify token for user {user_id}")
            return token_dict

        except Exception as e:
            log.error(f"Error fetching Spotify token for user {user_id}: {e}")
            print(f"❌ Error fetching Spotify token: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_spotify_client(self, user_id: Optional[str] = None) -> Optional[spotipy.Spotify]:
        """
        Get a Spotify client instance for a specific user.
        If user_id is not provided, tries to read from user_context.json.

        Returns:
            spotipy.Spotify instance if successful, None otherwise
        """
        try:
            # Get user_id if not provided
            if user_id is None:
                user_id = self.get_current_user_id()

            if not user_id:
                log.error("No user_id available - cannot create Spotify client")
                return None

            # Fetch user token
            token_info = self.get_user_token(user_id)

            if not token_info:
                log.error(f"No Spotify token found for user {user_id}")
                return None

            # Check if token is expired
            if self._is_token_expired(token_info):
                log.info("Token expired, attempting refresh...")
                token_info = self._refresh_token(token_info, user_id)
                if not token_info:
                    log.error("Failed to refresh token")
                    return None

            # Create Spotify client with user token
            sp = spotipy.Spotify(auth=token_info.get('access_token'))
            log.info(f"Spotify client created for user {user_id}")
            return sp

        except Exception as e:
            log.error(f"Error creating Spotify client: {e}")
            return None

    def _is_token_expired(self, token_info: dict) -> bool:
        """Check if token is expired."""
        expires_at = token_info.get('expires_at', 0)
        # Add 60 second buffer
        return int(datetime.now().timestamp()) >= (expires_at - 60)

    def _refresh_token(self, token_info: dict, user_id: str) -> Optional[dict]:
        """Refresh an expired Spotify token."""
        import requests

        refresh_token = token_info.get('refresh_token')
        if not refresh_token:
            log.error("No refresh token available")
            return None

        token_url = "https://accounts.spotify.com/api/token"

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            new_token_info = response.json()

            # Add expires_at timestamp
            new_token_info['expires_at'] = int(datetime.now().timestamp()) + new_token_info.get('expires_in', 3600)

            # Preserve refresh token if not provided in response
            if 'refresh_token' not in new_token_info:
                new_token_info['refresh_token'] = refresh_token

            # Save refreshed token back to MongoDB
            self._save_token(new_token_info, user_id)

            log.info("Successfully refreshed Spotify token")
            return new_token_info

        except Exception as e:
            log.error(f"Failed to refresh token: {e}")
            return None

    def _save_token(self, token_info: dict, user_id: str):
        """Save refreshed token back to MongoDB."""
        try:
            self._init_mongodb()

            # Convert user_id to ObjectId
            try:
                user_obj_id = ObjectId(user_id)
            except Exception:
                user_obj_id = user_id

            token_json_str = json.dumps(token_info)

            query = {"service": "Spotify", "user_id": user_obj_id}

            update_doc = {
                "$set": {
                    "token": token_json_str,
                    "encrypted": False,
                    "expires_at": token_info.get('expires_at'),
                    "refresh_token_present": bool(token_info.get('refresh_token')),
                    "updated_at": datetime.utcnow()
                }
            }

            self._tokens_col.update_one(query, update_doc)
            log.info(f"Saved refreshed Spotify token for user {user_id}")

        except Exception as e:
            log.error(f"Error saving refreshed token: {e}")

    def close(self):
        """Close MongoDB connection."""
        if self._mongo_client:
            try:
                self._mongo_client.close()
                log.info("MongoDB connection closed")
            except Exception as e:
                log.error(f"Error closing MongoDB connection: {e}")


# Global instance for easy access
_spotify_auth_instance = None


def get_user_spotify_client(user_id: Optional[str] = None) -> Optional[spotipy.Spotify]:
    """
    Convenience function to get a user-specific Spotify client.

    Args:
        user_id: Optional user ID. If not provided, reads from user_context.json

    Returns:
        spotipy.Spotify instance or None if user not connected
    """
    global _spotify_auth_instance

    if _spotify_auth_instance is None:
        _spotify_auth_instance = SpotifyUserAuth()

    return _spotify_auth_instance.get_spotify_client(user_id)
