from __future__ import print_function

import os
import traceback
import logging
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from services.token_store import TokenStore

log = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/meetings.space.created']


class MeetService:
    """Service wrapper for Google Meet auth/token flow.

    connect() will ensure credentials (token.json) exist/are refreshed and
    return a short message suitable for the UI: (bool, message).
    """

    def __init__(self, credentials_path='credentials.json', token_path='token.json', scopes=None):
        # Get the Frontend directory path
        frontend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Make paths absolute relative to Frontend directory
        self.credentials_path = os.path.join(frontend_dir, credentials_path) if not os.path.isabs(credentials_path) else credentials_path
        self.token_path = os.path.join(frontend_dir, token_path) if not os.path.isabs(token_path) else token_path

        self.scopes = scopes or SCOPES
        # token storage helper
        self._token_store = TokenStore()

    def connect(self):
        """Run the OAuth flow or refresh tokens. Returns (success: bool, message: str)."""
        try:
            creds = None
            # ensure paths are absolute relative to project root
            creds_path = os.path.abspath(self.credentials_path)
            token_path = os.path.abspath(self.token_path)

            log.debug("MeetService.connect: credentials_path=%s token_path=%s", creds_path, token_path)

            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_file(token_path, self.scopes)
                except (json.JSONDecodeError, ValueError) as e:
                    log.warning(f"Corrupted token file at {token_path}, deleting it. Error: {e}")
                    try:
                        os.remove(token_path)
                        log.info(f"Deleted corrupted token file: {token_path}")
                    except Exception as delete_err:
                        log.error(f"Failed to delete corrupted token: {delete_err}")
                    creds = None  # Will trigger fresh OAuth flow

            if not creds or not creds.valid:
                # try refresh
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open(token_path, 'w') as token:
                            token.write(creds.to_json())
                        # save token to DB
                        try:
                            token_dict = json.loads(creds.to_json())
                        except Exception:
                            token_dict = {"raw": creds.to_json()}
                        self._token_store.save_token("GMeet", token_dict, encrypt=bool(os.getenv("TOKEN_ENCRYPTION_KEY")))
                        return True, "Token refreshed (token.json updated)."
                    except Exception as exc:
                        tb = traceback.format_exc()
                        log.exception("Failed to refresh credentials: %s", exc)
                        return False, f"Failed to refresh token: {exc}\n{tb}"
                # run full auth flow
                if not os.path.exists(creds_path):
                    msg = (f"Missing OAuth client secrets file.\n\n"
                           f"Expected location: {creds_path}\n\n"
                           f"Please:\n"
                           f"1. Download credentials.json from Google Cloud Console\n"
                           f"2. Place it in: Sentinel-AI-Frontend/credentials.json")
                    log.error(msg)
                    return False, msg

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, self.scopes)
                    # explicit open_browser=True, port defaults to 0 (random free port)
                    creds = flow.run_local_server(port=0, open_browser=True)
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                    # save token to DB
                    try:
                        token_dict = json.loads(creds.to_json())
                    except Exception:
                        token_dict = {"raw": creds.to_json()}
                    self._token_store.save_token("GMeet", token_dict, encrypt=bool(os.getenv("TOKEN_ENCRYPTION_KEY")))
                    return True, "Authorization complete (token.json created)."
                except Exception as exc:
                    tb = traceback.format_exc()
                    log.exception("OAuth flow failed: %s", exc)
                    return False, f"OAuth flow failed: {exc}\n{tb}"

            # credentials valid
            # still save current token snapshot to DB (optional)
            try:
                token_dict = json.loads(creds.to_json())
            except Exception:
                token_dict = {"raw": creds.to_json()}
            self._token_store.save_token("GMeet", token_dict, encrypt=bool(os.getenv("TOKEN_ENCRYPTION_KEY")))
            return True, "Valid credentials already present (token.json)."

        except Exception as exc:
            tb = traceback.format_exc()
            log.exception("Unexpected MeetService error: %s", exc)
            return False, f"Meet auth failed: {exc}\n{tb}"