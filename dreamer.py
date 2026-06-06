"""
Dreamer — nightly memory consolidation.

Reads context.json + memory.json, asks Claude (Haiku) to deduplicate,
remove redundancies, and normalize. Writes back a clean memory.json.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from config import ANTHROPIC_API_KEY, TZ

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)
_MEMORY_PATH = Path(__file__).parent / "memory.json"
_CONTEXT_PATH = Path(__file__).parent / "context.json"

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_PROMPT = """\
You are consolidating memory files for a personal assistant.

## Static context (read-only — do not copy these facts into memory.json):
{context}

## Current memory.json:
{memory}

Clean memory.json by applying these rules:
1. Deduplicate — merge entries that refer to the same person, preference, or fact
2. Remove anything already captured verbatim in the static context above
3. Normalize formatting — consistent capitalization, terse one-line values
4. Merge redundant people entries (e.g. "Dr. Kim" and "Dr. Kim (pediatrician)" → one entry)
5. Preserve all unique, useful facts

Return ONLY valid JSON matching this exact schema — no markdown, no explanation:
{{"people": {{"name": "description"}}, "prefs": {{"preference": "value"}}, "notes": ["note1", "note2"]}}"""


def dream() -> dict:
    """
    Consolidate memory.json using Claude Haiku. Returns a summary dict.
    Safe to call if memory.json is missing or empty.
    """
    if not _MEMORY_PATH.exists():
        logger.info("Dreamer: no memory.json, skipping")
        return {"skipped": True, "reason": "no memory file"}

    memory_raw = _MEMORY_PATH.read_text()
    memory_before = json.loads(memory_raw)

    before_counts = {
        "people": len(memory_before.get("people", {})),
        "prefs": len(memory_before.get("prefs", {})),
        "notes": len(memory_before.get("notes", [])),
    }

    if sum(before_counts.values()) == 0:
        logger.info("Dreamer: memory is empty, skipping")
        return {"skipped": True, "reason": "empty memory"}

    context_raw = _CONTEXT_PATH.read_text() if _CONTEXT_PATH.exists() else "{}"

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": _PROMPT.format(context=context_raw, memory=memory_raw)}],
    )

    raw = response.content[0].text.strip()

    memory_after = json.loads(raw)
    # Validate schema before overwriting
    if not all(k in memory_after for k in ("people", "prefs", "notes")):
        raise ValueError(f"Dreamer: unexpected schema in response: {raw[:200]}")
    if not isinstance(memory_after["people"], dict):
        raise ValueError("Dreamer: 'people' must be a dict")
    if not isinstance(memory_after["prefs"], dict):
        raise ValueError("Dreamer: 'prefs' must be a dict")
    if not isinstance(memory_after["notes"], list):
        raise ValueError("Dreamer: 'notes' must be a list")

    _MEMORY_PATH.write_text(json.dumps(memory_after, indent=2))

    after_counts = {
        "people": len(memory_after.get("people", {})),
        "prefs": len(memory_after.get("prefs", {})),
        "notes": len(memory_after.get("notes", [])),
    }

    summary = {
        "before": before_counts,
        "after": after_counts,
        "dreamed_at": datetime.now(_TZ).isoformat(),
    }
    logger.info("Dreamer complete: %s", summary)
    return summary
