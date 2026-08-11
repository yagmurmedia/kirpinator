"""Google OAuth (installed-app flow) for Drive and YouTube — kept as two
independent credentials, not one shared token.

Real-world reason this matters: the source-footage Drive folder and the
"Yağmurun Oyun Bahçesi" YouTube channel turned out to belong to two
different Google accounts. A single combined-scope token can only ever be
signed in as one of them — authorizing it against the YouTube account broke
Drive access to the source folder, and vice versa. So each purpose gets its
own scope set and its own cached token file
(google_token_drive.json / google_token_youtube.json), authorized
separately and refreshed independently.

One-time human step per purpose: the first call to get_credentials(purpose)
for that purpose opens a browser window for sign-in/consent. After that the
token is cached and silently refreshed — no further browser interaction
needed for that purpose.
"""
from __future__ import annotations

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES: dict[str, list[str]] = {
    "drive": ["https://www.googleapis.com/auth/drive.readonly"],
    "youtube": [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ],
}


class MissingClientSecretError(RuntimeError):
    pass


def _token_path(purpose: str) -> Path:
    base = Path(settings.google_token_file)
    return base.with_name(f"{base.stem}_{purpose}{base.suffix}")


def get_credentials(purpose: str) -> Credentials:
    if purpose not in SCOPES:
        raise ValueError(f"Unknown auth purpose {purpose!r}, expected one of {list(SCOPES)}")
    scopes = SCOPES[purpose]
    token_path = _token_path(purpose)
    client_secret_path = Path(settings.google_oauth_client_secret_file)

    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception:
            logger.warning("Token refresh failed for %s, falling back to interactive auth.", purpose)

    if not client_secret_path.exists():
        raise MissingClientSecretError(
            "Google OAuth client secret not found at "
            f"{client_secret_path}. Download it from Google Cloud Console "
            "(APIs & Services > Credentials > OAuth client ID > Desktop app) "
            "and save it there, then restart."
        )

    logger.info("Opening a browser window for one-time Google account authorization (%s)...", purpose)
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds
