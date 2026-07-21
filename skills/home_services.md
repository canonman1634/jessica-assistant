---
name: home_services
trigger: any request for a home services provider (insulation, handyman, plumbing, electrical, HVAC, roofing, etc.) or to schedule one
---

# Skill: Home services lookup & scheduling

## Inputs
- `search_home_services`, `get_home_service_details` — headless-browser
  lookups (no API keys) against Yelp (primary) and Google Maps (reference);
  results come back labeled by source. It does not return phone numbers.
- Remembered facts (`remember`/`forget`) for past providers used
- Bland.ai via `make_call`, `check_call_status`, `get_transcript` to call and
  schedule an estimate/appointment

## Search area
Search is always scoped to **60010** (Barrington) — pass that zip as the
location to `search_home_services`/`get_home_service_details`. Don't ask
for or substitute a different location/town for this skill.

## Procedure
1. Confirm the type of work needed (insulation, handyman, plumbing,
   electrical, etc.) if not already stated.
2. Use `search_home_services` with the service type and location `60010`.
   Yelp is the hard filter — only propose a provider with a 4.0+ rating and
   50+ reviews on Yelp. Google Maps results come back unfiltered — show them
   as a reference/cross-check, never as the sole basis to propose a
   provider.
3. Show the owner the results from both sources (labeled Yelp/Google), even
   if one came back empty or failed to parse — don't silently drop a source;
   note briefly if a source failed to parse or got blocked.
4. Offer 2-3 options with rating, review count, and city, so the owner can
   pick one.
5. Once a provider is picked, get the phone number from the owner if not
   already known (don't guess it), confirm the objective (estimate visit vs.
   book the work directly, and any timing preference), then follow the
   phone-calls skill: state who you'll call, the number, and the objective,
   and wait for explicit approval before `make_call`.
6. After the call, report the outcome (appointment booked / estimate
   scheduled / needs a callback) from `check_call_status`/`get_transcript`.
7. If the owner mentions a preferred/blacklisted provider, offer to
   `remember` it for next time.

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
- Restate what was actually booked/scheduled (provider, date/time if
  applicable, and how it was arranged) back to the owner once known.
