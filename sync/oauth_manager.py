"""
Google OAuth 2.0 Manager for Pedne Sewa Trust - Employment Registry.
Implements desktop InstalledAppFlow, local token caching, and token refresh.
Does NOT hardcode passwords, client secrets, or private keys.
"""

import os
import json
from pathlib import Path
from typing import Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from app.config import config
from utils.logger import logger

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class OAuthManager:
    """Manages Google OAuth 2.0 desktop authentication lifecycle."""

    def __init__(self):
        token_file = config.get("google_token_file") or (config.app_data_dir / "google_token.json")
        self.token_path = Path(token_file)
        self._creds: Optional[Credentials] = None

    def get_credentials_path(self) -> Optional[str]:
        """Returns path to client_secret.json / credentials.json if configured and exists."""
        p = config.get("google_credentials_file", "")
        if p and os.path.exists(p):
            return p

        # Check default locations
        base_dir = config.base_dir
        app_dir = base_dir / "app"
        search_dirs = [
            app_dir,
            base_dir,
            config.app_data_dir,
        ]

        # Support PyInstaller bundled execution
        import sys
        if hasattr(sys, "_MEIPASS"):
            meipass = Path(sys._MEIPASS)
            search_dirs.extend([meipass / "app", meipass])
        if hasattr(sys, "executable") and sys.executable:
            exe_parent = Path(sys.executable).parent
            search_dirs.extend([exe_parent / "app", exe_parent])

        for cand in ("credentials.json", "client_secret.json", "google_credentials.json"):
            for s_dir in search_dirs:
                cand_path = s_dir / cand
                if cand_path.exists():
                    return str(cand_path)

        return None

    def get_credentials(self) -> Optional[Credentials]:
        """
        Retrieves valid Google OAuth credentials.
        Refreshes expired access tokens using the stored refresh token.
        """
        if self._creds and self._creds.valid:
            return self._creds

        # Load from stored token file
        if self.token_path.exists():
            try:
                self._creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                logger.warning("Could not parse existing token file: %s", e)
                self._creds = None

        # If expired but has refresh token, refresh it
        if self._creds and self._creds.expired and self._creds.refresh_token:
            try:
                self._creds.refresh(Request())
                self.save_credentials(self._creds)
                logger.info("Successfully refreshed Google OAuth access token.")
            except Exception as e:
                logger.warning("Token refresh failed: %s", e)
                self._creds = None

        return self._creds if (self._creds and self._creds.valid) else None

    def save_credentials(self, creds: Credentials):
        """Persists credentials (including refresh token) locally in user AppData."""
        self._creds = creds
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            logger.info("Google OAuth token cached securely to %s", self.token_path)
        except Exception as e:
            logger.error("Failed to save credentials token: %s", e)

    def is_authenticated(self) -> bool:
        """Returns True if valid or refreshable credentials exist."""
        creds = self.get_credentials()
        return creds is not None and creds.valid

    def get_connected_account(self) -> str:
        """Returns information on the connected account."""
        if not self.is_authenticated():
            return "Not Connected"
        # Extract account info from credentials if stored
        creds = self.get_credentials()
        if creds and hasattr(creds, "account") and creds.account:
            return creds.account
        return "Connected (Google Account)"

    def authorize_desktop_flow(self, credentials_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Launches standard Google OAuth 2.0 browser authorization flow for desktop.
        Returns: (success, message)
        """
        creds_file = credentials_path or self.get_credentials_path()
        if not creds_file or not os.path.exists(creds_file):
            return False, "Google Cloud OAuth client credentials file (credentials.json) not found. Please configure it in Settings."

        try:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            # Run local web server on random high port for OAuth callback
            creds = flow.run_local_server(port=0, open_browser=True, prompt="consent")
            self.save_credentials(creds)
            return True, "Successfully authorized Google account for spreadsheet backup."
        except Exception as e:
            logger.error("OAuth desktop authorization error: %s", e)
            return False, f"Google authorization could not be completed: {e}"

    def disconnect(self):
        """Clears local tokens and revokes in-memory credentials."""
        self._creds = None
        if self.token_path.exists():
            try:
                self.token_path.unlink()
                logger.info("Removed Google OAuth token cache.")
            except Exception as e:
                logger.error("Failed to delete token file: %s", e)


oauth_manager = OAuthManager()
