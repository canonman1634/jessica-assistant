"""
Append-only staging log for raw activity — the write path's first stop.

Every tool call and every turn gets appended here cheaply during the session.
Nothing here is retrieved directly by the agent; the nightly Dreamer reads
unconsolidated entries, distills them into semantic/episodic cards, and
advances the checkpoint so the same activity isn't distilled twice.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import JESSICA_USER, TZ

logger = logging.getLogger(__name__)

_DIR = Path(__file__).parent.parent / "memory" / "staging"
_TZ = ZoneInfo(TZ)


def _log_path() -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR / f"activity_{JESSICA_USER}.jsonl"


def _checkpoint_path() -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR / f"checkpoint_{JESSICA_USER}.json"


def log_activity(kind: str, **fields) -> None:
    """kind: 'tool_call' | 'turn' | 'decision'."""
    entry = {"ts": datetime.now(_TZ).isoformat(), "kind": kind, **fields}
    try:
        with _log_path().open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        logger.exception("Failed to write staging entry")


def read_unconsolidated() -> list[dict]:
    """Entries appended since the last consolidation checkpoint."""
    path = _log_path()
    if not path.exists():
        return []
    checkpoint = _read_checkpoint()
    lines = path.read_text().splitlines()
    return [json.loads(line) for line in lines[checkpoint:] if line.strip()]


def _read_checkpoint() -> int:
    path = _checkpoint_path()
    if not path.exists():
        return 0
    try:
        return json.loads(path.read_text()).get("line_count", 0)
    except (json.JSONDecodeError, OSError):
        return 0


def advance_checkpoint() -> None:
    """Mark all currently-written lines as consolidated."""
    path = _log_path()
    total = len(path.read_text().splitlines()) if path.exists() else 0
    _checkpoint_path().write_text(json.dumps({"line_count": total}))
