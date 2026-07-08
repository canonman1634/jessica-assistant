---
name: email_handling
trigger: any request to check, search, read, or send email
---

# Skill: Email handling

## Inputs
- Gmail via `list_unread`, `search_emails`, `read_email`, `send_email`
- `context.json` → `vip_senders.list`, `urgent_keywords` (what counts as urgent)

## Procedure
1. To check for new mail, use `list_unread`; to find something specific, use
   `search_emails` with a targeted query rather than paging through everything.
2. Read the full message with `read_email` before summarizing or acting on it —
   never draft a reply from a snippet alone.
3. Flag a message as urgent if the sender matches `vip_senders.list` or the
   subject/body contains an `urgent_keywords` term.

## Never
- Call `send_email` without first showing the owner the full draft (To,
  Subject, Body) and getting explicit approval in this conversation.
- Invent email content the owner didn't approve, even minor wording changes,
  without confirming the change first.

## Validation
- Confirm the send succeeded before telling the owner it was sent.
