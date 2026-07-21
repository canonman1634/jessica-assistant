---
name: home-services
description: Looks up and helps schedule home services providers for Jason (insulation, handyman, plumbing, electrical, HVAC, roofing, etc.). Always scoped to zip 60010 (Barrington). Triggers on any request for that kind of provider or to schedule one.
---

# Home services lookup & scheduling

## Tools

This repo's home-services lookup and phone-call logic lives in
`tools/home_services_tool.py` and `tools/phone_tool.py` as plain Python
functions, not native Claude Code tools — invoke them via Bash through the
CLI bridge:

```
python scripts/run_tool.py search_home_services '{"service": "<type of work>"}'
python scripts/run_tool.py get_home_service_details '{"name": "<provider>"}'
python scripts/run_tool.py make_call '{"phone_number": "<number>", "objective": "<objective>"}'
python scripts/run_tool.py check_call_status '{"call_id": "<id>"}'
python scripts/run_tool.py get_transcript '{"call_id": "<id>"}'
```

`search_home_services`/`get_home_service_details` read Yelp (primary) and
Google Maps (reference) via a headless browser (no API keys) — this is
scraping, not an API, so a source can occasionally fail to parse or get
blocked. Treat that as a labeled note, not a hard failure of the whole
search. It does not return phone numbers, and both default to zip 60010
(Barrington) if no `location` is passed. `make_call` places a real phone
call via Bland.ai — only after explicit approval (see below).

## Search area

Search is always scoped to **60010** (Barrington) — the tools default to it
automatically. Don't ask for or substitute a different location/town for
this skill.

## Process

1. Confirm the type of work needed (insulation, handyman, plumbing,
   electrical, etc.) if not already stated.
2. Run `search_home_services` with the service type. Yelp is the hard
   filter — only propose a provider with a 4.0+ rating and 50+ reviews on
   Yelp. Google Maps results come back unfiltered — show them as a
   reference/cross-check, never as the sole basis to propose a provider.
3. Show Jason the results from both sources (labeled Yelp/Google), even if
   one came back empty or failed to parse — don't silently drop a source;
   note briefly if a source failed to parse or got blocked.
4. Offer 2-3 options with rating, review count, and city, so Jason can pick
   one.
5. Once a provider is picked, get the phone number from Jason if not
   already known (don't guess it), confirm the objective (estimate visit vs.
   book the work directly, and any timing preference), state who you'll
   call, the number, and the objective, and wait for explicit approval
   before running `make_call`.
6. After the call, report the outcome (appointment booked / estimate
   scheduled / needs a callback) from `check_call_status`/`get_transcript`.

## Never

- Propose a provider that doesn't meet the 4.0★ / 50-review bar on Yelp, or
  that you haven't verified with `search_home_services`/
  `get_home_service_details`.
- Treat Google's unfiltered results as sufficient on their own to qualify a
  provider — Yelp is the bar.
- Invent a phone number, hours, or availability — verify or ask, never
  guess.
- Place a call without explicit approval of the provider and objective in
  this conversation.
- Assume a call succeeded without checking the outcome.

## Validation

Restate what was actually booked/scheduled (provider, date/time if
applicable, and how it was arranged) back to Jason once known.
