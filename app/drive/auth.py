"""Google OAuth (installed-app flow) shared by Drive and YouTube.

One-time human step: the first call to get_credentials() opens a browser window
for the user to sign in and grant consent. The resulting token is cached to
settings.google_token_file and silently refreshed after that — no further
browser interaction is needed.
"""
from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import settings

logger = logging.getLogger(__name__)

# Single combined scope set: read-only Drive access to pull source footage,
# plus YouTube upload access to publish the finished Shorts.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class MissingClientSecretError(RuntimeError):
    pass


def get_credentials() -> Credentials:
    token_path = Path(settings.google_token_file)
    client_secret_path = Path(settings.google_oauth_client_secret_file)

    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception:
            logger.warning("Token refresh failed, falling back to interactive auth.")

    if not client_secret_path.exists():
        raise MissingClientSecretError(
            "Google OAuth client secret not found at "
            f"{client_secret_path}. Download it from Google Cloud Console "
            "(APIs & Services > Credentials > OAuth client ID > Desktop app) "
            "and save it there, then restart."
        )

    logger.info("Opening a browser window for one-time Google account authorization...")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds
