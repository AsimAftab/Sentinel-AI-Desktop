import os
import threading
from dotenv import load_dotenv

load_dotenv()

# Module-level singleton client — shared across all services
_mongo_client = None
_mongo_client_lock = threading.Lock()


class DatabaseConfig:
    # MongoDB Settings
    MONGODB_CONNECTION_STRING = os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "sentinel_ai_db")
    MONGODB_COLLECTION_USERS = os.getenv("MONGODB_COLLECTION_USERS", "users")
    MONGODB_COLLECTION_TOKENS = os.getenv("MONGODB_COLLECTION_TOKENS", "service_tokens")

    # Connection Pool Settings
    MONGODB_MAX_POOL_SIZE = int(os.getenv("MONGODB_MAX_POOL_SIZE", "10"))
    MONGODB_CONNECT_TIMEOUT = int(os.getenv("MONGODB_CONNECT_TIMEOUT", "10000"))

    @classmethod
    def get_connection_params(cls):
        return {
            "host": cls.MONGODB_CONNECTION_STRING,
            "maxPoolSize": cls.MONGODB_MAX_POOL_SIZE,
            "connectTimeoutMS": cls.MONGODB_CONNECT_TIMEOUT,
            "serverSelectionTimeoutMS": 5000,
        }

    @classmethod
    def get_client(cls):
        """Return a shared MongoClient singleton (thread-safe, connection-pooled)."""
        global _mongo_client
        if _mongo_client is None:
            with _mongo_client_lock:
                if _mongo_client is None:
                    from pymongo import MongoClient

                    _mongo_client = MongoClient(**cls.get_connection_params())
        return _mongo_client

    @classmethod
    def ping(cls) -> bool:
        """Check if MongoDB is reachable. Returns True if healthy, False otherwise."""
        try:
            client = cls.get_client()
            client.admin.command("ping")
            return True
        except Exception:
            return False

    @classmethod
    def close(cls):
        """Close the MongoDB client and release resources."""
        global _mongo_client
        with _mongo_client_lock:
            if _mongo_client is not None:
                try:
                    _mongo_client.close()
                except Exception:
                    pass
                _mongo_client = None
