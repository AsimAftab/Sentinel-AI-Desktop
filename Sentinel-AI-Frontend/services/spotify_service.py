from __future__ import print_function

import os
import traceback
import logging
import json
import webbrowser
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from threading import Thread
import time

from services.token_store import TokenStore

log = logging.getLogger(__name__)

# Spotify OAuth configuration
# If modifying these scopes, delete the cached token from MongoDB
SPOTIFY_SCOPES = [
    'user-modify-playback-state',
    'user-read-playback-state',
    'user-read-currently-playing',
    'playlist-read-private',
    'playlist-read-collaborative',
    'user-library-read'
]


class SpotifyService:
    """Service wrapper for Spotify OAuth flow.

    connect() will run the OAuth flow, save credentials to MongoDB,
    and return a short message suitable for the UI: (bool, message).
    """

    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, user_id=None):
        # Load credentials from environment variables if not provided
        from dotenv import load_dotenv

        # Get the Backend directory path (where .env is located)
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Frontend dir
        project_root = os.path.dirname(current_dir)  # Project root
        backend_dir = os.path.join(project_root, "Sentinel-AI-Backend")
        env_path = os.path.join(backend_dir, ".env")

        load_dotenv(env_path)

        self.client_id = client_id or os.getenv('SPOTIPY_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('SPOTIPY_CLIENT_SECRET')
        self.redirect_uri = redirect_uri or os.getenv('SPOTIPY_REDIRECT_URI') or 'http://localhost:8888/callback'

        self.user_id = user_id
        self.scope = ' '.join(SPOTIFY_SCOPES)

        # Token storage helper
        self._token_store = TokenStore()

        # OAuth flow state
        self._auth_code = None
        self._auth_error = None
        self._server = None

    def connect(self):
        """Run the Spotify OAuth flow. Returns (success: bool, message: str)."""
        try:
            # Check if credentials are configured
            if not self.client_id or not self.client_secret:
                msg = (
                    "Spotify credentials not configured.\n\n"
                    "Please add the following to Sentinel-AI-Backend/.env:\n"
                    "SPOTIPY_CLIENT_ID=your_client_id\n"
                    "SPOTIPY_CLIENT_SECRET=your_client_secret\n"
                    "SPOTIPY_REDIRECT_URI=http://localhost:8888/callback\n\n"
                    "IMPORTANT: In Spotify Developer Dashboard, add BOTH redirect URIs:\n"
                    "  • http://localhost:8888/callback\n"
                    "  • http://127.0.0.1:8888/callback\n\n"
                    "Get credentials at: https://developer.spotify.com/dashboard"
                )
                log.error(msg)
                return False, msg

            print(f"🎵 Starting Spotify OAuth flow...")
            print(f"   Client ID: {self.client_id[:20]}...")
            print(f"   Redirect URI: {self.redirect_uri}")

            # Check if valid token already exists
            if self.user_id:
                result = self._token_store.get_token("Spotify", self.user_id)
                if result.get("ok"):
                    token_data = result.get("token", {})
                    # Check if token is still valid
                    if not self._is_token_expired(token_data):
                        log.info("Valid Spotify token already exists")
                        return True, "Valid Spotify credentials already present."
                    else:
                        # Try to refresh the token
                        refresh_result = self._refresh_token(token_data)
                        if refresh_result[0]:
                            return refresh_result

            # Start OAuth flow
            log.info("Starting Spotify OAuth flow...")

            # Parse redirect URI to get host and port
            parsed_uri = urlparse(self.redirect_uri)
            host = parsed_uri.hostname or 'localhost'
            port = parsed_uri.port or 8888

            # Start local server to receive callback
            self._start_local_server(host, port)

            # Generate authorization URL
            auth_url = self._get_authorize_url()

            log.info(f"Opening browser for Spotify authorization: {auth_url}")

            # Open browser for authorization
            webbrowser.open(auth_url)

            # Wait for callback (with timeout)
            timeout = 120  # 2 minutes
            start_time = time.time()

            while self._auth_code is None and self._auth_error is None:
                if time.time() - start_time > timeout:
                    self._stop_local_server()
                    return False, "Authorization timeout. Please try again."
                time.sleep(0.1)

            # Stop the server
            self._stop_local_server()

            # Check for errors
            if self._auth_error:
                return False, f"Authorization failed: {self._auth_error}"

            # Exchange authorization code for access token
            log.info("Exchanging authorization code for access token...")
            token_info = self._get_access_token(self._auth_code)

            if not token_info:
                return False, "Failed to obtain access token."

            # Save token to MongoDB
            self._save_token(token_info)

            return True, "Successfully connected to Spotify!"

        except Exception as exc:
            tb = traceback.format_exc()
            log.exception("Unexpected SpotifyService error: %s", exc)
            return False, f"Spotify auth failed: {exc}\n{tb}"

    def _get_authorize_url(self):
        """Generate Spotify authorization URL."""
        from urllib.parse import urlencode

        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'show_dialog': 'true'  # Always show account selection dialog
        }

        return f"https://accounts.spotify.com/authorize?{urlencode(params)}"

    def _start_local_server(self, host, port):
        """Start local HTTP server to receive OAuth callback."""
        service = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Parse the callback URL
                parsed_path = urlparse(self.path)
                query_params = parse_qs(parsed_path.query)

                log.info(f"Received callback: {self.path}")
                print(f"🔔 Spotify callback received: {self.path}")

                if 'code' in query_params:
                    service._auth_code = query_params['code'][0]
                    log.info(f"Authorization code received: {service._auth_code[:20]}...")
                    print(f"✅ Authorization code received!")

                    # Send success response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    success_html = """
                        <html>
                        <head>
                            <title>Spotify Authorization Successful</title>
                            <style>
                                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #1DB954; color: white; }
                                h1 { font-size: 48px; margin-bottom: 20px; }
                                p { font-size: 18px; }
                            </style>
                        </head>
                        <body>
                            <h1>✅ Success!</h1>
                            <p>You have successfully authorized Spotify.</p>
                            <p>You can close this window and return to the application.</p>
                            <script>
                                setTimeout(function() { window.close(); }, 2000);
                            </script>
                        </body>
                        </html>
                    """
                    self.wfile.write(success_html.encode('utf-8'))
                elif 'error' in query_params:
                    service._auth_error = query_params['error'][0]
                    log.error(f"Authorization error: {service._auth_error}")
                    print(f"❌ Authorization error: {service._auth_error}")

                    # Send error response
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    error_html = f"""
                        <html>
                        <head>
                            <title>Spotify Authorization Failed</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f44336; color: white; }}
                                h1 {{ font-size: 48px; margin-bottom: 20px; }}
                                p {{ font-size: 18px; }}
                            </style>
                        </head>
                        <body>
                            <h1>❌ Authorization Failed</h1>
                            <p>Error: {service._auth_error}</p>
                            <p>You can close this window and try again.</p>
                        </body>
                        </html>
                    """
                    self.wfile.write(error_html.encode('utf-8'))
                else:
                    # Unknown callback
                    log.warning(f"Unknown callback received: {self.path}")
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    invalid_html = """
                        <html>
                        <body>
                            <h1>Invalid Callback</h1>
                            <p>Unexpected callback format. Please try again.</p>
                        </body>
                        </html>
                    """
                    self.wfile.write(invalid_html.encode('utf-8'))

            def log_message(self, format, *args):
                # Log to our logger instead of stderr
                log.info(f"HTTP: {format % args}")

        try:
            # Bind to 0.0.0.0 to listen on all interfaces (accepts both localhost and 127.0.0.1)
            self._server = HTTPServer(('0.0.0.0', port), CallbackHandler)
            # Run server in background thread
            server_thread = Thread(target=self._server.serve_forever, daemon=True)
            server_thread.start()

            # Give server a moment to start
            time.sleep(0.5)

            log.info(f"Local server started on 0.0.0.0:{port} (accessible via localhost:{port} or 127.0.0.1:{port})")
            print(f"🌐 Local callback server started on port {port}")
            print(f"   Accessible at: http://localhost:{port} and http://127.0.0.1:{port}")
        except Exception as e:
            log.error(f"Failed to start local server: {e}")
            print(f"❌ Failed to start local server: {e}")
            raise

    def _stop_local_server(self):
        """Stop the local HTTP server."""
        if self._server:
            try:
                self._server.shutdown()
                log.info("Local server stopped")
            except Exception as e:
                log.error(f"Error stopping server: {e}")

    def _get_access_token(self, auth_code):
        """Exchange authorization code for access token."""
        import requests

        token_url = "https://accounts.spotify.com/api/token"

        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            token_info = response.json()

            # Add expires_at timestamp
            token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)

            log.info("Successfully obtained Spotify access token")
            return token_info

        except Exception as e:
            log.error(f"Failed to get access token: {e}")
            return None

    def _refresh_token(self, token_data):
        """Refresh an expired Spotify token."""
        import requests

        refresh_token = token_data.get('refresh_token')
        if not refresh_token:
            return False, "No refresh token available. Please reconnect."

        token_url = "https://accounts.spotify.com/api/token"

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            new_token_info = response.json()

            # Add expires_at timestamp
            new_token_info['expires_at'] = int(time.time()) + new_token_info.get('expires_in', 3600)

            # Preserve refresh token if not provided in response
            if 'refresh_token' not in new_token_info:
                new_token_info['refresh_token'] = refresh_token

            # Save refreshed token
            self._save_token(new_token_info)

            log.info("Successfully refreshed Spotify token")
            return True, "Token refreshed successfully."

        except Exception as e:
            log.error(f"Failed to refresh token: {e}")
            return False, f"Failed to refresh token: {e}"

    def _save_token(self, token_info):
        """Save token to MongoDB."""
        try:
            result = self._token_store.save_token("Spotify", token_info, user_id=self.user_id)
            if result.get("ok"):
                log.info(f"Spotify token saved to MongoDB for user {self.user_id}")
            else:
                log.error(f"Failed to save Spotify token: {result.get('error')}")
        except Exception as e:
            log.error(f"Error saving Spotify token: {e}")

    def _is_token_expired(self, token_data):
        """Check if token is expired."""
        expires_at = token_data.get('expires_at', 0)
        # Add 60 second buffer
        return int(time.time()) >= (expires_at - 60)
