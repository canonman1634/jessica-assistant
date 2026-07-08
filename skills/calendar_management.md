---
name: calendar_management
trigger: any request to check availability or create/update a calendar event
---

# Skill: Calendar management

## Inputs
- Google Calendar via `list_upcoming`, `check_availability`, `create_event`, `update_event`
- `context.json` → `owner.timezone`

## Procedure
1. For "what's on my calendar" style requests, use `list_upcoming` with a
   sensible `days_ahead` (default 7 unless the owner specifies a range).
2. Before proposing a new time, call `check_availability` for that slot.
3. Confirm title, date, start/end time, and location with the owner before
   calling `create_event` or `update_event`.

## Never
- Create or update an event without explicit confirmation of the final
  details in this conversation.
- Double-book a slot already confirmed unavailable without calling that out.

## Validation
- After writing, restate what was actually created/changed so the owner can
  catch a mismatch immediately.
