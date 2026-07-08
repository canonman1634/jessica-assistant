"""
Dreamer — nightly memory consolidation.

Two jobs, both using Claude Haiku (cheap, high-volume, doesn't need the
flagship model):

1. Semantic cleanup — reads context.json + memory_{user}.json, deduplicates,
   removes redundancies, normalizes. Writes back a clean memory file.
2. Episodic distillation — reads the raw activity staged since the last
   checkpoint (every turn: user message + reply) and writes a compact,
   dated session-summary card per session into episodic memory. This is the
   deferred write path: raw turns accumulate cheaply during the day, and
   only get folded into durable, retrievable memory once, here, instead of
   on every message.
"""
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from config import ANTHROPIC_API_KEY, MY_EMAIL, TZ, JESSICA_USER
from tools.email_tool import send_email_direct
from tools import vector_memory, staging

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)
_MEMORY_PATH = Path(__file__).parent / f"memory_{JESSICA_USER}.json"
_CONTEXT_PATH = Path(__file__).parent / "context.json"

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SESSION_SUMMARY_PROMPT = """\
You are writing a compact episodic memory entry for a personal assistant.

Below is a batch of raw conversation turns (user message + assistant reply) \
from one or more sessions with {phone}, most recent last:

{turns}

Write a short dated digest (2-5 bullet points) of what actually happened or \
was decided — skip small talk and routine confirmations, focus on facts, \
decisions, and outcomes worth recalling later. Return ONLY the bullet points, \
no preamble."""

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
    Nightly consolidation: semantic cleanup + episodic distillation.
    Returns a summary dict. Safe to call when either store is empty.
    """
    semantic = _consolidate_semantic()
    episodic = _distill_episodic()

    if semantic.get("skipped") and episodic.get("skipped"):
        return {"skipped": True, "reason": "nothing to consolidate", "user": JESSICA_USER}

    summary = {
        "user": JESSICA_USER,
        "semantic": semantic,
        "episodic": episodic,
        "dreamed_at": datetime.now(_TZ).isoformat(),
    }
    logger.info("Dreamer complete: %s", summary)

    if MY_EMAIL:
        _send_dream_report(summary)

    return summary


def _consolidate_semantic() -> dict:
    """Dedupe/normalize memory_{user}.json. Returns a sub-summary dict."""
    if not _MEMORY_PATH.exists():
        logger.info("Dreamer: no memory file for user '%s', skipping semantic pass", JESSICA_USER)
        return {"skipped": True, "reason": "no memory file"}

    memory_raw = _MEMORY_PATH.read_text()
    memory_before = json.loads(memory_raw)

    before_counts = {
        "people": len(memory_before.get("people", {})),
        "prefs": len(memory_before.get("prefs", {})),
        "notes": len(memory_before.get("notes", [])),
    }

    if sum(before_counts.values()) == 0:
        logger.info("Dreamer: memory is empty for user '%s', skipping semantic pass", JESSICA_USER)
        return {"skipped": True, "reason": "empty memory"}

    context_raw = _CONTEXT_PATH.read_text() if _CONTEXT_PATH.exists() else "{}"

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": _PROMPT.format(context=context_raw, memory=memory_raw)}],
    )

    raw = response.content[0].text.strip()

    try:
        memory_after = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Dreamer: invalid JSON from Claude: {e}\n{raw[:200]}") from e
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

    usage = response.usage
    cost_usd = (usage.input_tokens / 1_000_000) * 1.00 + (usage.output_tokens / 1_000_000) * 5.00

    return {
        "skipped": False,
        "before": before_counts,
        "after": after_counts,
        "tokens": {"input": usage.input_tokens, "output": usage.output_tokens},
        "cost_usd": round(cost_usd, 6),
    }


def _distill_episodic() -> dict:
    """Fold staged raw turns into dated episodic session-summary cards."""
    entries = staging.read_unconsolidated()
    turns = [e for e in entries if e.get("kind") == "turn"]

    if not turns:
        logger.info("Dreamer: no staged turns for user '%s', skipping episodic pass", JESSICA_USER)
        staging.advance_checkpoint()
        return {"skipped": True, "reason": "no staged activity"}

    by_phone = defaultdict(list)
    for t in turns:
        by_phone[t.get("phone", "unknown")].append(t)

    total_input, total_output, cards_written = 0, 0, 0

    for phone, phone_turns in by_phone.items():
        turns_text = "\n\n".join(
            f"[{t['ts']}] User: {t['user_message']}\nJessica: {t['reply']}" for t in phone_turns
        )
        response = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": _SESSION_SUMMARY_PROMPT.format(phone=phone, turns=turns_text),
            }],
        )
        digest = response.content[0].text.strip()
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        if digest:
            date = datetime.now(_TZ).strftime("%Y-%m-%d")
            card_id = f"epi-{date}-session-{uuid.uuid4().hex[:8]}"
            vector_memory.add_episodic(card_id, digest, {
                "type": "session_summary", "phone": phone,
                "date": datetime.now(_TZ).isoformat(),
                "turn_count": len(phone_turns),
            })
            cards_written += 1

    staging.advance_checkpoint()
    cost_usd = (total_input / 1_000_000) * 1.00 + (total_output / 1_000_000) * 5.00

    return {
        "skipped": False,
        "turns_distilled": len(turns),
        "cards_written": cards_written,
        "tokens": {"input": total_input, "output": total_output},
        "cost_usd": round(cost_usd, 6),
    }


def _send_dream_report(summary: dict) -> None:
    dreamed_at = summary["dreamed_at"]
    semantic = summary["semantic"]
    episodic = summary["episodic"]

    lines = [f"Jessica dreamed at {dreamed_at} (user: {summary['user']})", ""]
    total_input = total_output = 0.0
    total_cost = 0.0

    lines.append("Semantic memory (facts):")
    if semantic.get("skipped"):
        lines.append(f"  Skipped — {semantic['reason']}")
    else:
        before, after = semantic["before"], semantic["after"]
        removed = sum(before[k] - after[k] for k in before if after[k] < before[k])
        added = sum(after[k] - before[k] for k in after if after[k] > before[k])
        lines += [
            f"  People:      {before['people']} → {after['people']}",
            f"  Preferences: {before['prefs']} → {after['prefs']}",
            f"  Notes:       {before['notes']} → {after['notes']}",
            f"  Net:         +{added} added, -{removed} removed",
        ]
        total_input += semantic["tokens"]["input"]
        total_output += semantic["tokens"]["output"]
        total_cost += semantic["cost_usd"]

    lines.append("")
    lines.append("Episodic memory (events):")
    if episodic.get("skipped"):
        lines.append(f"  Skipped — {episodic['reason']}")
    else:
        lines += [
            f"  Turns distilled: {episodic['turns_distilled']}",
            f"  Session-summary cards written: {episodic['cards_written']}",
        ]
        total_input += episodic["tokens"]["input"]
        total_output += episodic["tokens"]["output"]
        total_cost += episodic["cost_usd"]

    lines.append("")
    lines.append("Haiku token usage (combined):")
    lines += [
        f"  Input:  {int(total_input):,}",
        f"  Output: {int(total_output):,}",
        f"  Total:  {int(total_input + total_output):,}",
        f"  Cost:   ${total_cost:.6f}",
    ]

    try:
        send_email_direct(
            to=MY_EMAIL,
            subject=f"Jessica dream report — {dreamed_at[:10]} ({summary['user']})",
            body="\n".join(lines) + "\n",
        )
    except Exception:
        logger.exception("Failed to send dream report email")
