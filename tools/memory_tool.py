"""
Memory tools — allow Jessica to remember and forget facts across sessions.
Memory is stored per-user, keyed by the JESSICA_USER env var.
"""
import json
import logging
from pathlib import Path

from config import JESSICA_USER

logger = logging.getLogger(__name__)
_MEMORY_PATH = Path(__file__).parent.parent / f"memory_{JESSICA_USER}.json"


def _load() -> dict:
    if not _MEMORY_PATH.exists():
        return {"people": {}, "prefs": {}, "notes": []}
    try:
        return json.loads(_MEMORY_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {"people": {}, "prefs": {}, "notes": []}


def _save(data: dict) -> None:
    _MEMORY_PATH.write_text(json.dumps(data, indent=2))


async def remember(args: dict) -> dict:
    category = args.get("category", "notes")
    key = args.get("key", "")
    value = args.get("value", "")

    data = _load()

    if category == "notes":
        note = key or value
        if not note:
            return {"content": [{"type": "text", "text": "Provide a note in the key field."}]}
        notes = data.setdefault("notes", [])
        if note not in notes:
            notes.append(note)
        _save(data)
        return {"content": [{"type": "text", "text": f"Noted: {note}"}]}

    if not key or not value:
        return {"content": [{"type": "text", "text": "Both key and value are required for people/prefs."}]}

    data.setdefault(category, {})[key] = value
    _save(data)
    return {"content": [{"type": "text", "text": f"Remembered — {category}/{key}: {value}"}]}


async def forget(args: dict) -> dict:
    category = args.get("category", "notes")
    key = args.get("key", "")

    data = _load()

    if category == "notes":
        before = len(data.get("notes", []))
        data["notes"] = [n for n in data.get("notes", []) if key.lower() not in n.lower()]
        removed = before - len(data["notes"])
        _save(data)
        return {"content": [{"type": "text", "text": f"Removed {removed} note(s) matching '{key}'."}]}

    if key in data.get(category, {}):
        del data[category][key]
        _save(data)
        return {"content": [{"type": "text", "text": f"Forgot {category}/{key}."}]}

    return {"content": [{"type": "text", "text": f"No entry found for {category}/{key}."}]}


def load_memory_for_prompt() -> str:
    """Return a compact string for injection into the system prompt."""
    data = _load()
    parts = []

    if data.get("people"):
        parts.append("People:\n" + "\n".join(f"  {k}: {v}" for k, v in data["people"].items()))
    if data.get("prefs"):
        parts.append("Preferences:\n" + "\n".join(f"  {k}: {v}" for k, v in data["prefs"].items()))
    if data.get("notes"):
        parts.append("Notes:\n" + "\n".join(f"  - {n}" for n in data["notes"]))

    return "\n".join(parts) if parts else "(none yet)"
