"""
One-time backfill: index existing memory_{user}.json entries into the
vector-backed semantic store (memory/semantic/).

Needed because the vector index was introduced after memory_{user}.json
already existed in production — remember()/forget() write to both going
forward, but facts saved before that change were never indexed. Safe to
re-run; upserts are idempotent (same card_id -> replaced, not duplicated).

Usage:
    python scripts/backfill_semantic_memory.py
    JESSICA_USER=jason python scripts/backfill_semantic_memory.py   # explicit user
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import JESSICA_USER
from tools import vector_memory
from tools.memory_tool import _card_id

_MEMORY_PATH = Path(__file__).parent.parent / f"memory_{JESSICA_USER}.json"


def backfill() -> None:
    if not _MEMORY_PATH.exists():
        print(f"No memory file at {_MEMORY_PATH} for user '{JESSICA_USER}' — nothing to backfill.")
        return

    data = json.loads(_MEMORY_PATH.read_text())
    written = 0

    for key, value in data.get("people", {}).items():
        vector_memory.upsert_semantic(_card_id("people", key), f"{key}: {value}", {"type": "people", "key": key})
        written += 1

    for key, value in data.get("prefs", {}).items():
        vector_memory.upsert_semantic(_card_id("prefs", key), f"{key}: {value}", {"type": "prefs", "key": key})
        written += 1

    for note in data.get("notes", []):
        vector_memory.upsert_semantic(_card_id("notes", note), note, {"type": "note", "key": note})
        written += 1

    print(f"Backfilled {written} semantic card(s) for user '{JESSICA_USER}' "
          f"({len(data.get('people', {}))} people, {len(data.get('prefs', {}))} prefs, "
          f"{len(data.get('notes', []))} notes).")


if __name__ == "__main__":
    backfill()
