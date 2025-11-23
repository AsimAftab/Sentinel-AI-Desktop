import os
import json
import logging
from datetime import datetime

from pymongo import MongoClient
from config.database_config import DatabaseConfig
from bson import ObjectId

log = logging.getLogger(__name__)

class TokenStore:
    """
    Simplified token storage - stores tokens as plain JSON strings in MongoDB.
    No encryption complexity, just simple JSON storage.
    """
    def __init__(self):
        self.config = DatabaseConfig()
        params = self.config.get_connection_params()
        self._client = MongoClient(**params)
        self._db = self._client[self.config.MONGODB_DATABASE]
        self._col = self._db[self.config.MONGODB_COLLECTION_TOKENS]

    def save_token(self, service_name: str, token_dict: dict, user_id: str = None, encrypt: bool = False) -> dict:
        """
        Save token JSON (dict) to DB linked to user_id (if provided).
        Stores as plain JSON string - no encryption, no binary.
        Uses upsert to avoid duplicates - replaces existing token for same service+user.

        Note: 'encrypt' parameter is ignored (kept for backwards compatibility).
        """
        try:
            # Convert token dict to JSON string (not bytes!)
            token_json_str = json.dumps(token_dict)

            # Build query to find existing token
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id  # fallback to raw string

            # Build document to save
            doc = {
                "service": service_name,
                "token": token_json_str,  # Plain JSON string
                "encrypted": False,       # Always false now
                "scopes": token_dict.get("scope") or token_dict.get("scopes"),
                "expires_at": token_dict.get("expires_at") or token_dict.get("expires_in"),
                "refresh_token_present": bool(token_dict.get("refresh_token")),
                "updated_at": datetime.utcnow()
            }

            if user_id:
                doc["user_id"] = query["user_id"]

            # Use update_one with upsert=True to replace existing or insert new
            # This prevents duplicates!
            res = self._col.update_one(
                query,
                {
                    "$set": doc,
                    "$setOnInsert": {"created_at": datetime.utcnow()}
                },
                upsert=True
            )

            if res.upserted_id:
                log.info("Inserted new token for %s id=%s user_id=%s", service_name, res.upserted_id, doc.get("user_id"))
                return {"ok": True, "id": str(res.upserted_id), "encrypted": False, "action": "inserted"}
            else:
                log.info("Updated existing token for %s user_id=%s", service_name, doc.get("user_id"))
                return {"ok": True, "id": "updated", "encrypted": False, "action": "updated"}

        except Exception as exc:
            log.exception("Failed to save token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def get_token(self, service_name: str, user_id: str = None) -> dict:
        """
        Retrieve the most recent token for a specific user and service.
        Returns token dict if found.
        """
        try:
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id  # fallback to raw string

            # Get most recent token
            doc = self._col.find_one(query, sort=[("created_at", -1)])
            if not doc:
                log.warning("No token found for service=%s user_id=%s", service_name, user_id)
                return {"ok": False, "error": "Token not found"}

            # Parse JSON string to dict
            token_str = doc["token"]
            if isinstance(token_str, bytes):
                # Handle legacy binary tokens (migration path)
                token_dict = json.loads(token_str.decode('utf-8'))
            else:
                # New plain JSON string format
                token_dict = json.loads(token_str)

            log.info("Retrieved token for service=%s user_id=%s", service_name, user_id)
            return {
                "ok": True,
                "token": token_dict,
                "encrypted": False,
                "created_at": doc.get("created_at"),
                "token_id": str(doc["_id"])
            }
        except Exception as exc:
            log.exception("Failed to get token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def get_latest_token(self, service_name: str, user_id: str = None) -> dict:
        """
        Alias for get_token - retrieves most recent token.
        """
        return self.get_token(service_name, user_id)

    def update_token(self, service_name: str, token_dict: dict, user_id: str = None, encrypt: bool = False) -> dict:
        """
        Update existing token or create new one if not found.

        Note: 'encrypt' parameter is ignored (kept for backwards compatibility).
        """
        try:
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id

            # Check if token exists
            existing = self._col.find_one(query, sort=[("created_at", -1)])

            if existing:
                # Update existing token
                token_json_str = json.dumps(token_dict)

                update_doc = {
                    "$set": {
                        "token": token_json_str,  # Plain JSON string
                        "encrypted": False,
                        "scopes": token_dict.get("scope") or token_dict.get("scopes"),
                        "expires_at": token_dict.get("expires_at") or token_dict.get("expires_in"),
                        "refresh_token_present": bool(token_dict.get("refresh_token")),
                        "updated_at": datetime.utcnow()
                    }
                }

                self._col.update_one({"_id": existing["_id"]}, update_doc)
                log.info("Updated token for service=%s user_id=%s", service_name, user_id)
                return {"ok": True, "id": str(existing["_id"]), "updated": True}
            else:
                # Create new token
                return self.save_token(service_name, token_dict, user_id, encrypt)

        except Exception as exc:
            log.exception("Failed to update token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def delete_token(self, service_name: str, user_id: str = None) -> dict:
        """
        Delete token for a specific user and service.
        """
        try:
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id

            result = self._col.delete_many(query)
            log.info("Deleted %d tokens for service=%s user_id=%s", result.deleted_count, service_name, user_id)
            return {"ok": True, "deleted_count": result.deleted_count}
        except Exception as exc:
            log.exception("Failed to delete token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass
