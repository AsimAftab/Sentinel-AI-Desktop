"""Shared Google OAuth helper for meeting and email tools.

Single flow, file-based: client secrets from ``data_dir()/credentials.json``
(falling back to the legacy frontend copy), user token cached at
``data_dir()/google_token.json``. Expired tokens are refreshed silently; the
interactive browser flow runs only when no usable token exists.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from sentinel_core.config import data_dir

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LEGACY_CREDENTIALS = _REPO_ROOT / "Sentinel-AI-Frontend" / "credentials.json"

# Serialize token refresh / interactive flows across executor threads.
_lock = threading.Lock()


def _token_path() -> Path:
    return data_dir() / "google_token.json"


def _client_secrets_path() -> Path:
    """Locate credentials.json, or raise a ValueError with setup instructions."""
    for candidate in (data_dir() / "credentials.json", _LEGACY_CREDENTIALS):
        if candidate.exists():
            return candidate
    raise ValueError(
        "Google credentials.json not found. To set up Google integration:\n"
        "1. Go to https://console.cloud.google.com and create (or open) a project\n"
        "2. Enable the Google Calendar API and Gmail API\n"
        "3. Create OAuth 2.0 credentials (Desktop app) and download the JSON\n"
        f"4. Save it as: {data_dir() / 'credentials.json'}"
    )


def get_credentials(scopes: list[str]) -> Credentials:
    """Return valid Google OAuth credentials covering ``scopes``.

    Loads the cached token if present, refreshes it silently when expired, and
    only opens the interactive browser consent flow when no usable token
    exists. Raises ValueError when credentials.json is missing.
    """
    with _lock:
        token_path = _token_path()
        creds: Credentials | None = None
        granted: set[str] = set()

        if token_path.exists():
            try:
                cached = json.loads(token_path.read_text(encoding="utf-8"))
                granted = set(cached.get("scopes") or [])
                # Re-authenticate (rather than refresh) when the cached token was
                # granted for a different scope set than the one requested now.
                if granted >= set(scopes):
                    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
                else:
                    logger.info(
                        "Cached Google token lacks scopes %s; re-authenticating",
                        sorted(set(scopes) - granted),
                    )
            except Exception as exc:
                logger.warning("Ignoring unreadable Google token %s: %s", token_path, exc)
                creds = None

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_path.write_text(creds.to_json(), encoding="utf-8")
            except Exception as exc:
                logger.warning("Google token refresh failed, re-authenticating: %s", exc)
                creds = None

        if not creds or not creds.valid:
            from google_auth_oauthlib.flow import InstalledAppFlow

            secrets = _client_secrets_path()
            # Request the union of previously granted + newly requested scopes so
            # Calendar and Gmail tools converge on one token instead of ping-ponging.
            flow = InstalledAppFlow.from_client_secrets_file(
                str(secrets), sorted(set(scopes) | granted)
            )
            creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            logger.info("Google OAuth completed; token cached at %s", token_path)

        return creds
