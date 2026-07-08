---
name: phone_calls
trigger: any request to call someone on the owner's behalf
---

# Skill: Phone calls

## Inputs
- Bland.ai via `make_call`, `check_call_status`, `get_transcript`, `list_recent_calls`

## Procedure
1. Before calling `make_call`, tell the owner: who you'll call, the phone
   number, and the objective/script you'll use.
2. Wait for explicit approval ("yes", "go ahead", "do it") in this
   conversation before placing the call.
3. To follow up on a call already placed, use `check_call_status` or
   `get_transcript` with the call ID.

## Never
- Place a call without explicit approval given after the owner has seen the
  number and objective.
- Guess a phone number — ask if it's not already known or confirmed.

## Validation
- Report the call outcome (status + key transcript points) back to the owner
  once available; don't leave a placed call unacknowledged.
