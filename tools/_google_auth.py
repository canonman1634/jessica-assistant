"""
Shared Google OAuth2 credential helper.
- On Railway: loads token from GOOGLE_TOKEN_B64 environment variable
- Locally: opens browser for consent on first run, then loads cached token
"""

import base64
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH, GOOGLE_SCOPES


def get_google_credentials() -> Credentials:
    token_path = Path(GOOGLE_TOKEN_PATH)
    creds = None

    # On Railway, load token from environment variable
    token_b64 = os.environ.get("GOOGLE_TOKEN_B64")
    if token_b64 and not token_path.exists():
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(base64.b64decode(token_b64).decode())

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH, GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

    return creds
