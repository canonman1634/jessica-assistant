---
name: memory_management
trigger: the owner shares a persistent fact, preference, or correction — or asks you to forget one
---

# Skill: Memory management

## Layers
- **Procedural** (this file and its siblings) — how to act. Git-committed,
  loaded into every system prompt, never changes at runtime.
- **Semantic** (`remember`/`forget`, backed by `memory_{user}.json` +
  `memory/semantic/`) — durable facts: people, preferences, standing notes.
  Small enough to load in full every turn, and also vector-indexed so it
  still resolves well once it grows.
- **Episodic** (`memory/episodic/`) — dated events: what Jessica actually did
  (calls placed, emails sent, events created) and decisions the owner made.
  Written automatically by the agent loop and by the nightly Dreamer, not
  something the model calls directly.

## Procedure
1. When the owner states a fact worth keeping (a contact, a preference, a
   standing instruction), call `remember` immediately with the right
   category — don't wait to be asked.
   - `people`: key = name, value = description/role/contact info.
   - `prefs`: key = the preference name, value = its value.
   - `notes`: key = the note text itself.
2. When the owner asks to forget something, call `forget` with the category
   and a key/keyword that matches what they said.
3. Do not narrate memory writes unless the owner would find it useful to know
   (e.g. confirming a correction landed).

## Never
- Store sensitive information (financial account numbers, medical record
  numbers, passwords) beyond what's strictly needed for the task at hand.
- Silently overwrite a `people`/`prefs` entry on a guess — if the new value
  conflicts with a stored one, confirm before overwriting.
