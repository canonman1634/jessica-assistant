---
name: email-calendar-sync
description: Scans Gmail for calendar-relevant messages (appointments, invitations, reservations, deadlines, cancellations), proposes calendar additions/edits/deletions, and applies only what the user approves. Runs twice daily via a scheduled Routine; can also be invoked manually to check for updates immediately.
---

# Email → Calendar Sync

## When this runs

Fired twice daily (7am / 6pm CT) by a scheduled Routine, each time into a fresh
session with no memory of prior runs. All state that needs to persist across
runs (which emails have already been looked at) lives in Gmail labels, not in
conversation history. Can also be run manually anytime.

## Process

1. **Find candidate emails.**
   - Call `list_labels` and look for a label named exactly
     `jessica/calendar-reviewed`. If it doesn't exist, create it with
     `create_label` and note the `labelId` it returns.
   - `search_threads`'s `label:` filter takes a **label ID, not a display
     name** — always resolve the ID via `list_labels` first, then search:
     `-label:<labelId> newer_than:2d`. The 2-day window is a safety margin
     in case a scheduled run is missed.
   - Look for: appointment confirmations, event invitations, reservations
     (restaurants, travel, medical, etc.), school/daycare notices with dates,
     meeting requests, and cancellation/reschedule notices. Ignore
     promotional/social mail with no concrete date or time.

2. **Label every candidate as reviewed immediately** (`label_message` or
   `label_thread` with the `jessica/calendar-reviewed` label ID from step 1)
   once you've looked at it — whether or not it turns into a proposal. This is
   what stops the same email from being re-proposed on the next run.

3. **Cross-reference the calendar** for each calendar-relevant email
   (`list_events` / `get_event` around the relevant date):
   - No matching event exists → propose an **ADD**.
   - A matching event exists but details differ (time, location, title) →
     propose an **EDIT**.
   - The email cancels or reschedules an existing event → propose a
     **DELETE** (or an EDIT if it's a reschedule of the same event).
   - Match events by more than just title (time, attendees) to avoid false
     positives against unrelated events with similar names.

4. **Present proposals — do not apply anything yet.**
   - Post a concise, numbered list. For each item include: action
     (ADD/EDIT/DELETE), title, date/time, location, and a one-line source
     (`from: <subject> — <sender>`).
   - If nothing relevant was found, say so briefly (e.g. "No calendar updates
     from this scan.") and stop there.
   - End your turn without calling `create_event`, `update_event`, or
     `delete_event`. The user may not reply until much later — that's
     expected.

5. **Apply on approval.**
   - When the user replies (in this same session, whenever that happens)
     approving some or all items, apply exactly what was approved with
     `create_event` / `update_event` / `delete_event`.
   - If they approve with a correction ("yes but push it to 3pm"), apply
     their correction, not the original proposal.
   - Confirm what was actually changed after applying.

## Rules

- Never create, edit, or delete a calendar event without explicit approval
  given in the conversation.
- Never re-propose an email already labeled `jessica/calendar-reviewed`.
- If an email is ambiguous (unclear date/time, unclear if still relevant),
  include it as a proposal with the ambiguity called out rather than guessing.
- Default to the user's primary calendar; check `list_calendars` if context
  suggests a different one (e.g. a shared family calendar).
