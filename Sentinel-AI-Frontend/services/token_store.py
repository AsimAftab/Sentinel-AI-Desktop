import json
import logging
from datetime import datetime

from config.database_config import DatabaseConfig
from bson import ObjectId

log = logging.getLogger(__name__)

# ── Encryption helpers ──────────────────────────────────────────────────────
_ENCRYPTION_SERVICE = "SentinelApp-TokenEncryption"
_ENCRYPTION_KEY_NAME = "fernet_key"


def _get_or_create_encryption_key() -> bytes:
    """Return the Fernet key from system keyring, creating it on first use."""
    import keyring

    key_str = keyring.get_password(_ENCRYPTION_SERVICE, _ENCRYPTION_KEY_NAME)
    if not key_str:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        keyring.set_password(_ENCRYPTION_SERVICE, _ENCRYPTION_KEY_NAME, key.decode())
        log.info("Generated new token encryption key and stored in keyring")
        return key
    return key_str.encode()


def _encrypt_token(token_json_str: str) -> str:
    """Encrypt a token JSON string with Fernet symmetric encryption."""
    from cryptography.fernet import Fernet

    f = Fernet(_get_or_create_encryption_key())
    return f.encrypt(token_json_str.encode()).decode()


def _decrypt_token(data: str) -> str:
    """Decrypt a Fernet-encrypted token string.

    Falls back to the raw string on failure so legacy unencrypted tokens
    stored before this change are still readable (migration path).
    """
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_get_or_create_encryption_key())
        return f.decrypt(data.encode()).decode()
    except Exception:
        # Legacy plain-JSON token — return as-is for transparent migration
        return data


# ── TokenStore ──────────────────────────────────────────────────────────────


class TokenStore:
    """
    Secure token storage — stores Fernet-encrypted token JSON in MongoDB.
    Uses the shared MongoClient connection pool (no per-instance TCP connections).
    """

    def __init__(self):
        self.config = DatabaseConfig()

    def _get_collection(self):
        """Return the tokens collection using the shared connection pool."""
        client = self.config.get_client()
        db = client[self.config.MONGODB_DATABASE]
        return db[self.config.MONGODB_COLLECTION_TOKENS]

    def save_token(
        self, service_name: str, token_dict: dict, user_id: str = None, encrypt: bool = True
    ) -> dict:
        """
        Encrypt and save token JSON to MongoDB linked to user_id.
        Uses upsert to avoid duplicates.
        """
        try:
            col = self._get_collection()
            token_json_str = json.dumps(token_dict)
            encrypted_token = _encrypt_token(token_json_str)

            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id

            doc = {
                "service": service_name,
                "token": encrypted_token,
                "encrypted": True,
                "scopes": token_dict.get("scope") or token_dict.get("scopes"),
                "expires_at": token_dict.get("expires_at") or token_dict.get("expires_in"),
                "refresh_token_present": bool(token_dict.get("refresh_token")),
                "updated_at": datetime.utcnow(),
            }
            if user_id:
                doc["user_id"] = query["user_id"]

            res = col.update_one(
                query, {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True
            )

            if res.upserted_id:
                log.info("Inserted encrypted token for %s user_id=%s", service_name, user_id)
                return {
                    "ok": True,
                    "id": str(res.upserted_id),
                    "encrypted": True,
                    "action": "inserted",
                }
            else:
                log.info("Updated encrypted token for %s user_id=%s", service_name, user_id)
                return {"ok": True, "id": "updated", "encrypted": True, "action": "updated"}

        except Exception as exc:
            log.exception("Failed to save token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def get_token(self, service_name: str, user_id: str = None) -> dict:
        """Retrieve and decrypt the most recent token for a service/user."""
        try:
            col = self._get_collection()
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id

            doc = col.find_one(query, sort=[("created_at", -1)])
            if not doc:
                log.warning("No token found for service=%s user_id=%s", service_name, user_id)
                return {"ok": False, "error": "Token not found"}

            token_raw = doc["token"]
            if isinstance(token_raw, bytes):
                token_raw = token_raw.decode("utf-8")

            # Decrypt (falls back transparently for legacy plain-JSON tokens)
            token_str = _decrypt_token(token_raw)
            token_dict = json.loads(token_str)

            log.info("Retrieved token for service=%s user_id=%s", service_name, user_id)
            return {
                "ok": True,
                "token": token_dict,
                "encrypted": doc.get("encrypted", False),
                "created_at": doc.get("created_at"),
                "token_id": str(doc["_id"]),
            }
        except Exception as exc:
            log.exception("Failed to get token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def get_latest_token(self, service_name: str, user_id: str = None) -> dict:
        """Alias for get_token."""
        return self.get_token(service_name, user_id)

    def update_token(
        self, service_name: str, token_dict: dict, user_id: str = None, encrypt: bool = True
    ) -> dict:
        """Update existing token or create new one if not found."""
        try:
            col = self._get_collection()
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id

            existing = col.find_one(query, sort=[("created_at", -1)])
            if existing:
                encrypted_token = _encrypt_token(json.dumps(token_dict))
                col.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "token": encrypted_token,
                            "encrypted": True,
                            "scopes": token_dict.get("scope") or token_dict.get("scopes"),
                            "expires_at": token_dict.get("expires_at")
                            or token_dict.get("expires_in"),
                            "refresh_token_present": bool(token_dict.get("refresh_token")),
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                log.info("Updated encrypted token for service=%s user_id=%s", service_name, user_id)
                return {"ok": True, "id": str(existing["_id"]), "updated": True}
            else:
                return self.save_token(service_name, token_dict, user_id)

        except Exception as exc:
            log.exception("Failed to update token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def delete_token(self, service_name: str, user_id: str = None) -> dict:
        """Delete token for a specific user and service."""
        try:
            col = self._get_collection()
            query = {"service": service_name}
            if user_id:
                try:
                    query["user_id"] = ObjectId(user_id)
                except Exception:
                    query["user_id"] = user_id

            result = col.delete_many(query)
            log.info(
                "Deleted %d tokens for service=%s user_id=%s",
                result.deleted_count,
                service_name,
                user_id,
            )
            return {"ok": True, "deleted_count": result.deleted_count}
        except Exception as exc:
            log.exception("Failed to delete token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def close(self):
        """No-op — connection managed by shared DatabaseConfig pool."""
        pass
