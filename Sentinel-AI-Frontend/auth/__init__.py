"""
Sentinel AI Authentication Module

This module provides secure authentication and session management
using the system keyring for credential storage.
"""

from .keyring_auth import KeyringAuthFixed
from .session_manager import SessionManager

__all__ = ['KeyringAuthFixed', 'SessionManager']