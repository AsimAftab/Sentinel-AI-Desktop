import logging
from datetime import datetime
import bcrypt
from config.database_config import DatabaseConfig

logger = logging.getLogger(__name__)


def _sanitize_input(value: str, field_name: str = "input") -> str:
    """Reject non-string inputs to prevent NoSQL injection via dicts/lists."""
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field_name}: expected string, got {type(value).__name__}")
    return value


class UserService:
    def __init__(self):
        self.config = DatabaseConfig()

    def _get_users_collection(self):
        """Return the users collection using the shared connection pool."""
        client = self.config.get_client()
        db = client[self.config.MONGODB_DATABASE]
        return db[self.config.MONGODB_COLLECTION_USERS]

    def save_user(self, username, fullname, phone, email, password):
        try:
            username = _sanitize_input(username, "username")
            users_collection = self._get_users_collection()

            # Check if user already exists
            if users_collection.find_one({"username": username}):
                return False, "Username already exists in database"

            # Hash password
            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

            user_doc = {
                "username": username,
                "fullname": fullname,
                "phone": phone,
                "email": email,
                "password": hashed_password,
                "created_at": datetime.utcnow(),
                "is_active": True,
                "last_login": None,
            }

            result = users_collection.insert_one(user_doc)
            return True, f"User saved successfully with ID: {result.inserted_id}"

        except Exception as e:
            return False, f"Database error: {str(e)}"

    def get_user_by_username(self, username):
        """Get user document from MongoDB by username (includes _id)."""
        try:
            username = _sanitize_input(username, "username")
            users_collection = self._get_users_collection()
            return users_collection.find_one({"username": username})
        except Exception as e:
            logger.error("Error fetching user: %s", e)
            return None
