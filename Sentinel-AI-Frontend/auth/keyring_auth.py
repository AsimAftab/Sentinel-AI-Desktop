import keyring
import hashlib
import secrets
import json
import time
from typing import Optional, Dict, Any, Tuple
import re
import platform

# Separate service names to avoid Windows Credential Manager conflicts
USER_SERVICE_NAME = "SentinelApp-Users"
SESSION_SERVICE_NAME = "SentinelApp-Sessions"
USER_DATA_PREFIX = "user"
SESSION_PREFIX = "session"

# Session expiration time (24 hours in seconds)
SESSION_EXPIRY_HOURS = 24
SESSION_EXPIRY_SECONDS = SESSION_EXPIRY_HOURS * 3600

class KeyringAuthFixed:
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using SHA-256 with salt"""
        salt = hashlib.sha256(password.encode()).hexdigest()[:16]
        return hashlib.sha256((password + salt).encode()).hexdigest()

    @staticmethod
    def _generate_token() -> str:
        """Generate secure random token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def _get_timestamp() -> int:
        """Get current timestamp"""
        return int(time.time())

    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        return re.match(pattern, email) is not None

    @staticmethod
    def _validate_password(password: str) -> bool:
        """Validate password strength"""
        return len(password) >= 6

    @staticmethod
    def _clean_username(username: str) -> str:
        """Clean username for consistent storage"""
        return username.strip().lower().replace(" ", "_")

    @staticmethod
    def _create_session_data(token: str) -> str:
        """Create session data with expiration"""
        session_data = {
            "token": token,
            "created_at": KeyringAuthFixed._get_timestamp(),
            "expires_at": KeyringAuthFixed._get_timestamp() + SESSION_EXPIRY_SECONDS
        }
        return json.dumps(session_data)

    @staticmethod
    def _is_session_valid(session_json: str) -> Tuple[bool, Optional[str]]:
        """Check if session is valid and not expired"""
        try:
            session_data = json.loads(session_json)
            current_time = KeyringAuthFixed._get_timestamp()

            if current_time > session_data.get("expires_at", 0):
                return False, None  # Session expired

            return True, session_data.get("token")
        except:
            return False, None

    @staticmethod
    def _force_delete_credential(service: str, username: str) -> bool:
        """Force delete credential with multiple attempts for Windows compatibility"""
        attempts = [
            f"{service}:{username}",
            f"{service}",
            username,
            f"{service} {username}",
            f"{service}_{username}"
        ]

        success = False
        for attempt in attempts:
            try:
                keyring.delete_password(service, username)
                success = True
                break
            except:
                try:
                    # Try alternative deletion methods on Windows
                    if platform.system() == "Windows":
                        import subprocess
                        subprocess.run(f'cmdkey /delete:"{attempt}"', shell=True, capture_output=True)
                        success = True
                except:
                    continue

        return success

    @staticmethod
    def register_user(username: str, fullname: str, phone: str, email: str, password: str) -> Tuple[bool, str]:
        """Register a new user with improved validation"""
        try:
            # Clean and validate inputs
            username = KeyringAuthFixed._clean_username(username)

            if not all([username, fullname, phone, email, password]):
                return False, "All fields are required"

            if not KeyringAuthFixed._validate_email(email):
                return False, "Invalid email format"

            if not KeyringAuthFixed._validate_password(password):
                return False, "Password must be at least 6 characters"

            # Check if user already exists
            existing_user = KeyringAuthFixed.get_user(username)
            if existing_user:
                return False, "Username already exists"

            # Create user data
            user_data = {
                "username": username,
                "fullname": fullname,
                "phone": phone,
                "email": email,
                "password_hash": KeyringAuthFixed._hash_password(password),
                "created_at": KeyringAuthFixed._get_timestamp()
            }

            # Store user data with separate service name
            user_key = f"{USER_DATA_PREFIX}_{username}"
            keyring.set_password(USER_SERVICE_NAME, user_key, json.dumps(user_data))

            return True, "User registered successfully"

        except Exception as e:
            return False, f"Registration failed: {str(e)}"

    @staticmethod
    def authenticate_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Authenticate user with improved session management"""
        try:
            username = KeyringAuthFixed._clean_username(username)
            user_data = KeyringAuthFixed.get_user(username)

            if not user_data:
                return False, "User not found", None

            password_hash = KeyringAuthFixed._hash_password(password)
            if user_data["password_hash"] != password_hash:
                return False, "Incorrect password", None

            # Generate and store session with expiration
            token = KeyringAuthFixed._generate_token()
            session_data = KeyringAuthFixed._create_session_data(token)

            session_key = f"{SESSION_PREFIX}_{username}"
            keyring.set_password(SESSION_SERVICE_NAME, session_key, session_data)

            # Remove password hash from returned data
            user_data_safe = user_data.copy()
            del user_data_safe["password_hash"]

            return True, "Authentication successful", user_data_safe

        except Exception as e:
            return False, f"Authentication failed: {str(e)}", None

    @staticmethod
    def get_user(username: str) -> Optional[Dict[str, Any]]:
        """Get user data by username"""
        try:
            username = KeyringAuthFixed._clean_username(username)
            user_key = f"{USER_DATA_PREFIX}_{username}"
            user_data_json = keyring.get_password(USER_SERVICE_NAME, user_key)

            if user_data_json:
                return json.loads(user_data_json)
            return None
        except:
            return None

    @staticmethod
    def is_logged_in(username: str) -> bool:
        """Check if user has a valid, non-expired session"""
        try:
            username = KeyringAuthFixed._clean_username(username)
            session_key = f"{SESSION_PREFIX}_{username}"
            session_data = keyring.get_password(SESSION_SERVICE_NAME, session_key)

            if not session_data:
                return False

            is_valid, _ = KeyringAuthFixed._is_session_valid(session_data)

            # If session expired, clean it up
            if not is_valid:
                KeyringAuthFixed.logout_user(username)
                return False

            return True
        except:
            return False

    @staticmethod
    def logout_user(username: str) -> bool:
        """Logout user with improved cleanup"""
        try:
            username = KeyringAuthFixed._clean_username(username)
            session_key = f"{SESSION_PREFIX}_{username}"

            # Force delete session with multiple attempts
            success = KeyringAuthFixed._force_delete_credential(SESSION_SERVICE_NAME, session_key)

            # Additional cleanup attempts for Windows compatibility
            try:
                keyring.delete_password(SESSION_SERVICE_NAME, session_key)
            except:
                pass

            return True  # Return True even if deletion fails
        except:
            return False

    @staticmethod
    def get_session_token(username: str) -> Optional[str]:
        """Get valid session token for user"""
        try:
            username = KeyringAuthFixed._clean_username(username)
            session_key = f"{SESSION_PREFIX}_{username}"
            session_data = keyring.get_password(SESSION_SERVICE_NAME, session_key)

            if not session_data:
                return None

            is_valid, token = KeyringAuthFixed._is_session_valid(session_data)

            if not is_valid:
                KeyringAuthFixed.logout_user(username)
                return None

            return token
        except:
            return None

    @staticmethod
    def cleanup_expired_sessions() -> int:
        """Clean up all expired sessions (utility function)"""
        # Note: This is limited by keyring's inability to list all entries
        # In a real application, you'd maintain a list of active users
        return 0

    @staticmethod
    def delete_user(username: str) -> bool:
        """Delete user completely (user data + session)"""
        try:
            username = KeyringAuthFixed._clean_username(username)

            # Delete user data
            user_key = f"{USER_DATA_PREFIX}_{username}"
            KeyringAuthFixed._force_delete_credential(USER_SERVICE_NAME, user_key)

            # Delete session
            KeyringAuthFixed.logout_user(username)

            return True
        except:
            return False