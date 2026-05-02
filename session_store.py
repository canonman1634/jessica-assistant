"""
Tracks Claude Agent SDK session IDs keyed by phone number.
Sessions older than LOG_RETENTION_DAYS are purged automatically.
"""

import json
import time
from pathlib import Path
from config import LOG_RETENTION_DAYS

_SESSIONS_DIR = Path(__file__).parent / "sessions"
_SESSIONS_FILE = _SESSIONS_DIR / "sessions.json"


def _load() -> dict:
    _SESSIONS_DIR.mkdir(exist_ok=True)
    if not _SESSIONS_FILE.exists():
        return {}
    try:
        return json.loads(_SESSIONS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    _SESSIONS_DIR.mkdir(exist_ok=True)
    _SESSIONS_FILE.write_text(json.dumps(data, indent=2))


def _purge_old(data: dict) -> dict:
    cutoff = time.time() - (LOG_RETENTION_DAYS * 86400)
    return {k: v for k, v in data.items() if v.get("updated_at", 0) > cutoff}


def get_session_id(phone: str) -> str | None:
    data = _purge_old(_load())
    return data.get(phone, {}).get("session_id")


def save_session_id(phone: str, session_id: str) -> None:
    data = _purge_old(_load())
    data[phone] = {"session_id": session_id, "updated_at": time.time()}
    _save(data)


def clear_session(phone: str) -> None:
    data = _load()
    data.pop(phone, None)
    _save(data)


def purge_old_sessions() -> int:
    """Called by scheduler nightly. Returns number of sessions removed."""
    before = _load()
    after = _purge_old(before)
    _save(after)
    return len(before) - len(after)
