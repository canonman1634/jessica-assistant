---
name: email-calendar-sync
description: Scans Gmail for calendar-relevant messages (appointments, invitations, reservations, deadlines, cancellations). Auto-applies clear-cut new events straight to the calendar and holds anything ambiguous or risky (edits/deletes of existing events, unclear dates) for approval. Always sends a push notification summarizing what happened. Runs twice daily via a scheduled Routine; can also be invoked manually to check for updates immediately.
---

# Email → Calendar Sync

## When this runs

Fired twice daily (7am / 6pm CT) by a scheduled Routine, into a fresh session
each time. This requires the Routine (at claude.ai/code/routines, not the
raw trigger API) to have this repository and the Gmail + Google Calendar
connectors explicitly attached under its Repositories/Connectors settings —
a fresh session has no access to either otherwise. All state that needs to
persist across runs (which emails have already been looked at) lives in
Gmail labels, not in conversation history, so the process below doesn't
depend on remembering earlier turns. Can also be run manually anytime.

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
   - No matching event exists → this is a candidate **ADD**.
   - A matching event exists but details differ (time, location, title) →
     this is a candidate **EDIT**.
   - The email cancels or reschedules an existing event → this is a
     candidate **DELETE** (or an EDIT if it's a reschedule of the same
     event).
   - Match events by more than just title (time, attendees) to avoid false
     positives against unrelated events with similar names.

4. **Auto-apply clear-cut ADDs; hold everything else for approval.**
   - A **new** event (no existing calendar entry to conflict with) counts as
     clear-cut when the email states an unambiguous date, start time (or
     clearly all-day), and — if relevant — location, without conflicting
     information elsewhere in the thread. Apply these immediately with
     `create_event`, including the `jennifer.a.hinz@gmail.com` attendee and
     any reminder handling below. This covers things like a coach's practice
     schedule, a confirmed appointment, or a reservation with a stated time.
   - Everything else stays a **proposal, not applied**: any **EDIT** or
     **DELETE** of an existing event (these touch something already on the
     calendar and a wrong guess is costly), and any **ADD** that's ambiguous
     (fuzzy date/time, conflicting details, unclear if still relevant, or a
     tentative/"TBD" placeholder).
   - Post one concise summary covering both: what was auto-applied (title,
     date/time, location, one-line source `from: <subject> — <sender>`) and
     what's pending review as a numbered list (action, title, date/time,
     location, source, and — for proposals — the reason it wasn't
     auto-applied).
   - Always send a `PushNotification` after a run that found anything —
     applied or pending — summarizing it in one line (e.g. "Added 4 Steelers
     practices to your calendar" or "2 added, 1 item needs your review").
     Don't let auto-applied changes go unnoticed just because they didn't
     need approval.
   - If nothing relevant was found, say so briefly (e.g. "No calendar updates
     from this scan.") and stop there — no notification needed.

5. **Apply proposals on approval.**
   - When the user replies (in this same session, whenever that happens)
     approving some or all pending items, apply exactly what was approved
     with `create_event` / `update_event` / `delete_event`.
   - If they approve with a correction ("yes but push it to 3pm"), apply
     their correction, not the original proposal.
   - Always add `jennifer.a.hinz@gmail.com` as an attendee on every calendar
     entry created or updated, in addition to any other approved changes.
   - For an all-day event that needs a same-day reminder at a specific time
     (e.g. "7am reminder"), use a negative `overrideReminders` minutes value
     equal to `-(hour * 60)` — e.g. 7am is `minutes: -420`. A positive value
     counts backwards from midnight into the previous day, which is wrong
     here.
   - Confirm what was actually changed after applying.

## Rules

- Never edit or delete an existing calendar event without explicit approval
  given in the conversation. Clear-cut new events (see step 4) may be added
  without waiting for approval, but must always be reported via a
  `PushNotification` so nothing goes on the calendar unnoticed.
- Never re-propose or re-add from an email already labeled
  `jessica/calendar-reviewed`.
- If an email is ambiguous (unclear date/time, unclear if still relevant),
  hold it as a proposal with the ambiguity called out rather than guessing.
- Default to the user's primary calendar; check `list_calendars` if context
  suggests a different one (e.g. a shared family calendar).
- Every calendar entry this skill creates or updates must include
  `jennifer.a.hinz@gmail.com` as an attendee.
