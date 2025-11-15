import os
import json
import logging
from datetime import datetime

from pymongo import MongoClient
from config.database_config import DatabaseConfig
from bson import ObjectId

log = logging.getLogger(__name__)

# optional encryption
try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False

class TokenStore:
    def __init__(self):
        self.config = DatabaseConfig()
        params = self.config.get_connection_params()
        self._client = MongoClient(**params)
        self._db = self._client[self.config.MONGODB_DATABASE]
        self._col = self._db[self.config.MONGODB_COLLECTION_TOKENS]
        # Load encryption key from env if provided (base64 urlsafe)
        self._enc_key = os.getenv('TOKEN_ENCRYPTION_KEY')
        if self._enc_key and not CRYPTO_AVAILABLE:
            log.warning("TOKEN_ENCRYPTION_KEY provided but 'cryptography' not installed. Tokens will be stored plaintext.")
            self._enc_key = None

    def _encrypt(self, plaintext: bytes) -> bytes:
        if not self._enc_key:
            return plaintext
        f = Fernet(self._enc_key.encode() if isinstance(self._enc_key, str) else self._enc_key)
        return f.encrypt(plaintext)

    def _decrypt(self, ciphertext: bytes) -> bytes:
        if not self._enc_key:
            return ciphertext
        f = Fernet(self._enc_key.encode() if isinstance(self._enc_key, str) else self._enc_key)
        return f.decrypt(ciphertext)

    def save_token(self, service_name: str, token_dict: dict, user_id: str = None, encrypt: bool = False) -> dict:
        """
        Save token JSON (dict) to DB linked to user_id (if provided).
        """
        try:
            payload = json.dumps(token_dict).encode('utf-8')
            encrypted = False
            if encrypt and self._enc_key and CRYPTO_AVAILABLE:
                payload = self._encrypt(payload)
                encrypted = True

            doc = {
                "service": service_name,
                "token": payload,          # bytes; pymongo will store as Binary
                "encrypted": encrypted,
                "scopes": token_dict.get("scope") or token_dict.get("scopes"),
                "expires_at": token_dict.get("expires_at") or token_dict.get("expires_in"),
                "refresh_token_present": bool(token_dict.get("refresh_token")),
                "created_at": datetime.utcnow()
            }

            if user_id:
                try:
                    doc["user_id"] = ObjectId(user_id)
                except Exception:
                    doc["user_id"] = user_id  # fallback to raw string

            res = self._col.insert_one(doc)
            log.info("Saved token for %s id=%s encrypted=%s user_id=%s", service_name, res.inserted_id, encrypted, doc.get("user_id"))
            return {"ok": True, "id": str(res.inserted_id), "encrypted": encrypted}
        except Exception as exc:
            log.exception("Failed to save token for %s: %s", service_name, exc)
            return {"ok": False, "error": str(exc)}

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass