from .keyring_auth import KeyringAuthFixed

class SessionManager:
    @staticmethod
    def save_session(username: str, token: str):
        """Legacy method - now handled by KeyringAuthFixed"""
        pass

    @staticmethod
    def get_session(username: str):
        """Get session token for user"""
        return KeyringAuthFixed.get_session_token(username)

    @staticmethod
    def delete_session(username: str):
        """Delete user session"""
        return KeyringAuthFixed.logout_user(username)

    @staticmethod
    def is_logged_in(username: str):
        """Check if user is logged in"""
        return KeyringAuthFixed.is_logged_in(username)