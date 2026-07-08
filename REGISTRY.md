# Memory architecture — registry

How Jessica's memory system is wired, so this survives across sessions and
future changes are made with the whole picture in view. Adapted from the
layered procedural/semantic/episodic pattern (originally written up for an
FP&A forecast agent) to a single-user WhatsApp assistant.

## Layers

| Layer | Lives in | Loaded how | Written by |
|---|---|---|---|
| Procedural (how to act) | `skills/*.md` | Concatenated into the system prompt every turn | Git commits (methodology changes only) |
| Semantic (durable facts) | `memory_{user}.json` + `memory/semantic/` | Full dump every turn (small) + top-k retrieval by relevance | `remember`/`forget` tool calls |
| Episodic (dated events) | `memory/episodic/` | Top-k retrieval by relevance to the current message | Immediate tool-action logging (`agent.py`) + nightly session-summary distillation (`dreamer.py`) |
| Working memory | Assembled fresh in `agent.py._build_system_prompt` | N/A — ephemeral, rebuilt every turn | N/A |

## Write path

1. Every tool call and every completed turn is appended to
   `memory/staging/activity_{user}.jsonl` (cheap, append-only,
   `tools/staging.py`).
2. `send_email` / `create_event` / `update_event` / `make_call` also get an
   **immediate** episodic card (`agent.py._log_episodic_tool_action`) —
   deterministic, no LLM needed, since it's just recording what happened.
3. `remember` / `forget` write semantic facts immediately (JSON + vector
   card) and stage a `decision` activity entry.
4. Nightly at 3 AM CT (`scheduler.py` → `dreamer.py`):
   - **Semantic pass**: Haiku dedupes/normalizes `memory_{user}.json`.
   - **Episodic pass**: Haiku distills the day's staged turns (user message
     + reply) into compact, dated session-summary cards, then advances the
     staging checkpoint so the same turns aren't distilled twice.
   - A dream report email is sent to `MY_EMAIL` with token usage/cost for
     both passes.

## Retrieval path

Every turn, `agent.py` embeds the incoming message and queries both Chroma
collections for top-k relevant facts/events
(`tools/memory_tool.load_relevant_memory_for_prompt`), injected into the
system prompt alongside the always-loaded compact semantic summary.

## One-time backfill

The vector index was introduced after `memory_{user}.json` already existed
in production, so `scripts/backfill_semantic_memory.py` indexes whatever is
currently in that file into `memory/semantic/`. Run it once per deployed
user after this change ships (safe to re-run — upserts are idempotent):

```
JESSICA_USER=<user> python scripts/backfill_semantic_memory.py
```

There's no equivalent for episodic memory — it didn't exist before, so
there's no prior data to backfill; it starts accumulating from the first
turn after deploy.

## Extending this

- New tool categories → add a `skills/<name>.md` procedural doc; it's picked
  up automatically (`agent.py` globs `skills/*.md`).
- New semantic fact types → just call `remember` with a new `category`; no
  code change needed unless it needs its own retrieval shaping.
- Consolidation cadence is the deterministic nightly cron in
  `scheduler.py` — change the trigger there, not with a vibe.
