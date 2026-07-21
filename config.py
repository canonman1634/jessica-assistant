import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
BLAND_API_KEY = os.environ["BLAND_API_KEY"]
YELP_API_KEY = os.environ.get("YELP_API_KEY", "")
MY_EMAIL = os.environ.get("MY_EMAIL", "")

# ── User identity (determines which memory file is used) ─────────────────────
JESSICA_USER = os.environ.get("JESSICA_USER", "default")

# ── Google ────────────────────────────────────────────────────────────────────
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials/google_credentials.json")
GOOGLE_TOKEN_PATH = os.environ.get("GOOGLE_TOKEN_PATH", "credentials/google_token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

# ── App ───────────────────────────────────────────────────────────────────────
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
TZ = os.environ.get("TZ", "America/Chicago")
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "7"))
MY_EMAIL = os.environ.get("MY_EMAIL", "")

# ── Family context ────────────────────────────────────────────────────────────
_context_path = Path(__file__).parent / "context.json"

def load_context() -> dict:
    with open(_context_path) as f:
        return json.load(f)
