# Memory layout

This directory holds Jessica's semantic + episodic memory. Directories are
created automatically at runtime; nothing under here except this file is
tracked in git — see `.gitignore` (per-user memory is PII, and the vector
index is a rebuildable cache, not a source of truth worth diffing).

```
memory/
  semantic/
    chroma_db/{user}/   vector index over durable facts (people, prefs, notes)
    cards/{user}/       the same facts as human-readable Markdown cards
  episodic/
    chroma_db/{user}/   vector index over dated events
    cards/{user}/       the same events as human-readable Markdown cards
  staging/
    activity_{user}.jsonl     append-only raw log (tool calls, turns, decisions)
    checkpoint_{user}.json    how much of the log the Dreamer has consolidated
```

- **Procedural memory** lives outside this directory, in `../skills/*.md` —
  it's methodology, not per-user data, so it IS git-tracked.
- **Write path**: `tools/memory_tool.py` (`remember`/`forget`) and
  `agent.py` write semantic facts and tool-action episodic cards
  immediately. Raw conversation turns are staged cheaply and only
  distilled into episodic session-summary cards by the nightly Dreamer
  (`dreamer.py`, scheduled in `scheduler.py`) — see `../REGISTRY.md`.
