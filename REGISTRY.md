# Memory architecture — registry

How Jessica's memory system is wired, so this survives across sessions and
future changes are made with the whole picture in view. Adapted from the
layered procedural/semantic/episodic pattern (originally written up for an
FP&A forecast agent) to a single-user assistant used through Claude Code
sessions.

## Layers

| Layer | Lives in | Loaded how | Written by |
|---|---|---|---|
| Procedural (how to act) | `skills/*.md` | Concatenated into the system prompt every turn | Git commits (methodology changes only) |
| Semantic (durable facts) | `memory_{user}.json` + `memory/semantic/` | Full dump every turn (small) + top-k retrieval by relevance | `remember`/`forget` tool calls |
| Episodic (dated events) | `memory/episodic/` | Top-k retrieval by relevance to the current message | Immediate tool-action logging (`agent.py`) + session-summary distillation (`dreamer.py`, run on demand or via a Routine) |
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
4. On demand (`python dreamer.py`, or a Claude Code Routine on a schedule):
   - **Semantic pass**: Haiku dedupes/normalizes `memory_{user}.json`.
   - **Episodic pass**: Haiku distills the day's staged turns (user message
     + reply) into compact, dated session-summary cards, then advances the
     staging checkpoint so the same turns aren't distilled twice.
   - A dream report email is sent to `MY_EMAIL` with token usage/cost for
     both passes.

## Retrieval path

`agent.py._build_system_prompt` embeds the incoming message and queries both
Chroma collections for top-k relevant facts/events
(`tools/memory_tool.load_relevant_memory_for_prompt`), injected into the
system prompt alongside the always-loaded compact semantic summary. Whatever
is acting as Jessica in a given session is responsible for calling this to
build its system prompt.

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

## Two separate skill systems — don't confuse them

- `skills/*.md` (this dir, top-level) — Jessica's own procedural docs,
  written for `agent.py._load_procedural_memory` to concatenate into a
  system prompt. **Nothing currently calls that path** (the WhatsApp loop
  that used to call it is gone), so a file living only here will not
  auto-trigger in a Claude Code session.
- `.claude/skills/<name>/SKILL.md` — real Claude Code skills, auto-loaded
  and auto-triggered by Claude Code itself based on the `description` in
  their frontmatter (e.g. `email-calendar-sync`, `restaurant-reservations`,
  `home-services`). These are what actually fire when you talk to a fresh
  Claude Code session. They call Jessica's Python tools via
  `python scripts/run_tool.py <tool_name> '<json args>'` (Bash) rather than
  as native tool calls, since those tools were built for `agent.py`'s
  registry, not for Claude Code directly.

If a capability needs to work from a Claude Code session, it needs a
`.claude/skills/` entry — a `skills/*.md` file alone won't be seen.

## Extending this

- New tool categories → add the Python tool function (`tools/<name>.py`)
  and register it in `agent.py`'s `_TOOL_HANDLERS`/`_TOOLS`, then add a
  `.claude/skills/<name>/SKILL.md` that calls it via
  `scripts/run_tool.py` (see above).
- New semantic fact types → just call `remember` with a new `category`; no
  code change needed unless it needs its own retrieval shaping.
- Consolidation cadence is whatever you set up to call `dreamer.py` (manual
  run or a Claude Code Routine) — there's no background cron anymore.
