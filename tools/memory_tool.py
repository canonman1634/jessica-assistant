"""
Memory tools — allow Jessica to remember and forget facts across sessions.
Memory is stored per-user, keyed by the JESSICA_USER env var.

This is the semantic-memory write path: `remember`/`forget` update both the
compact JSON summary (always loaded into the prompt in full — cheap since it
stays small) and a durable, vector-indexed fact card (retrieved top-k when it
grows). Every call is also staged as a "decision" activity for the nightly
Dreamer to fold into episodic memory.
"""
import json
import logging
import re
from pathlib import Path

from config import JESSICA_USER
from tools import vector_memory, staging

logger = logging.getLogger(__name__)
_MEMORY_PATH = Path(__file__).parent.parent / f"memory_{JESSICA_USER}.json"


def _card_id(category: str, key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return f"sem-{category}-{slug}"[:100]


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
        vector_memory.upsert_semantic(_card_id("notes", note), note, {"type": "note", "key": note})
        staging.log_activity("decision", category="notes", key=note, value=note)
        return {"content": [{"type": "text", "text": f"Noted: {note}"}]}

    if not key or not value:
        return {"content": [{"type": "text", "text": "Both key and value are required for people/prefs."}]}

    data.setdefault(category, {})[key] = value
    _save(data)
    vector_memory.upsert_semantic(_card_id(category, key), f"{key}: {value}", {"type": category, "key": key})
    staging.log_activity("decision", category=category, key=key, value=value)
    return {"content": [{"type": "text", "text": f"Remembered — {category}/{key}: {value}"}]}


async def forget(args: dict) -> dict:
    category = args.get("category", "notes")
    key = args.get("key", "")

    data = _load()

    if category == "notes":
        before = data.get("notes", [])
        removed_notes = [n for n in before if key.lower() in n.lower()]
        data["notes"] = [n for n in before if n not in removed_notes]
        _save(data)
        for note in removed_notes:
            vector_memory.delete_semantic(_card_id("notes", note))
        return {"content": [{"type": "text", "text": f"Removed {len(removed_notes)} note(s) matching '{key}'."}]}

    if key in data.get(category, {}):
        del data[category][key]
        _save(data)
        vector_memory.delete_semantic(_card_id(category, key))
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


def load_relevant_memory_for_prompt(query: str, k: int = 5) -> str:
    """Top-k semantic facts + episodic events relevant to the current message.

    Complements load_memory_for_prompt(): that one dumps the full compact
    summary (cheap while it's small); this one retrieves what's relevant as
    episodic memory grows unbounded (every tool action, every session) and a
    full dump stops being practical.
    """
    semantic_hits = vector_memory.query_semantic(query, k=k)
    episodic_hits = vector_memory.query_episodic(query, k=k)

    parts = []
    if semantic_hits:
        parts.append("Relevant facts:\n" + "\n".join(f"  - {h['text']}" for h in semantic_hits))
    if episodic_hits:
        lines = []
        for h in episodic_hits:
            date = h["metadata"].get("date", "")[:10]
            lines.append(f"  - [{date}] {h['text']}")
        parts.append("Relevant past events:\n" + "\n".join(lines))

    return "\n".join(parts) if parts else ""
