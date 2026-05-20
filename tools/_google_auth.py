"""
Shared Google OAuth2 credential helper.
- On Railway: loads token from GOOGLE_TOKEN_B64 environment variable
- Locally: opens browser for consent on first run, then loads cached token
- Web reauth: get_auth_url() / exchange_code() for Railway-hosted OAuth flow
"""

import base64
import os
import secrets
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH, GOOGLE_SCOPES


class AuthRequiredError(Exception):
    """Raised when Google credentials are missing or expired and cannot be auto-refreshed."""
    pass


def _token_path() -> Path:
    return Path(GOOGLE_TOKEN_PATH)


def _load_token_from_env():
    token_path = _token_path()
    token_b64 = os.environ.get("GOOGLE_TOKEN_B64")
    if token_b64 and not token_path.exists():
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(base64.b64decode(token_b64).decode())


def get_google_credentials() -> Credentials:
    _load_token_from_env()
    token_path = _token_path()
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
            return creds
        except Exception:
            pass

    # Running locally without a token — open browser flow
    app_url = os.environ.get("APP_URL", "")
    if not app_url:
        flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, GOOGLE_SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
        return creds

    raise AuthRequiredError(
        "Google account needs reauthorization. The user must visit the /auth URL to reconnect."
    )


def get_auth_url(redirect_uri: str, state: str | None = None) -> tuple[str, str]:
    """Generate a Google OAuth consent URL. Returns (auth_url, state)."""
    flow = Flow.from_client_secrets_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )
    if state is None:
        state = secrets.token_urlsafe(16)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url, state


def exchange_code(code: str, redirect_uri: str) -> Credentials:
    """Exchange an authorization code for credentials and save to disk."""
    flow = Flow.from_client_secrets_file(
        GOOGLE_CREDENTIALS_PATH,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_path = _token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds
