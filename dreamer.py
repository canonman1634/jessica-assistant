"""
Dreamer — nightly memory consolidation.

Finds all memory_{user}.json files, asks Claude Haiku to deduplicate and
normalize each one against context.json, then writes them back.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from config import ANTHROPIC_API_KEY, MY_EMAIL, TZ
from tools.email_tool import send_email_direct

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)
_BASE = Path(__file__).parent
_CONTEXT_PATH = _BASE / "context.json"

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


def _dream_one(memory_path: Path, context_raw: str) -> dict:
    """Consolidate a single memory file. Returns a summary dict."""
    user = memory_path.stem.removeprefix("memory_")
    memory_raw = memory_path.read_text()
    memory_before = json.loads(memory_raw)

    before_counts = {
        "people": len(memory_before.get("people", {})),
        "prefs": len(memory_before.get("prefs", {})),
        "notes": len(memory_before.get("notes", [])),
    }

    if sum(before_counts.values()) == 0:
        logger.info("Dreamer: memory empty for '%s', skipping", user)
        return {"user": user, "skipped": True, "reason": "empty memory"}

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": _PROMPT.format(context=context_raw, memory=memory_raw)}],
    )

    raw = response.content[0].text.strip()

    try:
        memory_after = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Dreamer: invalid JSON from Claude for '{user}': {e}\n{raw[:200]}") from e

    if not all(k in memory_after for k in ("people", "prefs", "notes")):
        raise ValueError(f"Dreamer: unexpected schema for '{user}': {raw[:200]}")
    if not isinstance(memory_after["people"], dict):
        raise ValueError(f"Dreamer: 'people' must be a dict for '{user}'")
    if not isinstance(memory_after["prefs"], dict):
        raise ValueError(f"Dreamer: 'prefs' must be a dict for '{user}'")
    if not isinstance(memory_after["notes"], list):
        raise ValueError(f"Dreamer: 'notes' must be a list for '{user}'")

    memory_path.write_text(json.dumps(memory_after, indent=2))

    after_counts = {
        "people": len(memory_after.get("people", {})),
        "prefs": len(memory_after.get("prefs", {})),
        "notes": len(memory_after.get("notes", [])),
    }

    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens

    return {
        "user": user,
        "before": before_counts,
        "after": after_counts,
        "tokens": {"input": input_tokens, "output": output_tokens},
        "cost_usd": round((input_tokens / 1_000_000) * 1.00 + (output_tokens / 1_000_000) * 5.00, 6),
        "dreamed_at": datetime.now(_TZ).isoformat(),
    }


def dream() -> list[dict]:
    """Consolidate all memory_{user}.json files. Returns a list of summaries."""
    memory_files = sorted(_BASE.glob("memory_*.json"))
    if not memory_files:
        logger.info("Dreamer: no memory files found, skipping")
        return []

    context_raw = _CONTEXT_PATH.read_text() if _CONTEXT_PATH.exists() else "{}"
    summaries = []

    for path in memory_files:
        try:
            summary = _dream_one(path, context_raw)
            summaries.append(summary)
            logger.info("Dreamer complete for '%s': %s", summary["user"], summary)
        except Exception:
            logger.exception("Dreamer failed for '%s'", path.name)

    if MY_EMAIL and summaries:
        _send_dream_report(summaries)

    return summaries


def _send_dream_report(summaries: list[dict]) -> None:
    dreamed_at = datetime.now(_TZ).isoformat()
    lines = [f"Jessica dream report — {dreamed_at[:10]}\n"]

    for s in summaries:
        if s.get("skipped"):
            lines.append(f"  {s['user']}: skipped ({s.get('reason', '')})")
            continue
        before, after = s["before"], s["after"]
        tokens = s["tokens"]
        lines.append(
            f"  {s['user']}:\n"
            f"    People:      {before['people']} → {after['people']}\n"
            f"    Preferences: {before['prefs']} → {after['prefs']}\n"
            f"    Notes:       {before['notes']} → {after['notes']}\n"
            f"    Tokens:      {tokens['input']:,} in / {tokens['output']:,} out\n"
            f"    Cost:        ${s['cost_usd']:.6f}"
        )

    try:
        send_email_direct(
            to=MY_EMAIL,
            subject=f"Jessica dream report — {dreamed_at[:10]}",
            body="\n".join(lines),
        )
    except Exception:
        logger.exception("Failed to send dream report email")
