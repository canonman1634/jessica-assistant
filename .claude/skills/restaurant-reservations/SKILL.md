---
name: restaurant-reservations
description: Recommends restaurants and makes reservations for Jason. Triggers on any request for a restaurant recommendation, or to book/change a restaurant reservation. Handles two fixed groups with different search boundaries and party sizes ("me and Jen" vs "the foodboyz") plus ad-hoc requests.
---

# Restaurant reservations & recommendations

## Tools

This repo's restaurant lookup and phone-call logic lives in
`tools/restaurant_tool.py` and `tools/phone_tool.py` as plain Python
functions, not native Claude Code tools — invoke them via Bash through the
CLI bridge:

```
python scripts/run_tool.py search_restaurants '{"location": "<town>", "term": "<cuisine/vibe>"}'
python scripts/run_tool.py get_restaurant_details '{"name": "<name>", "location": "<town>"}'
python scripts/run_tool.py make_call '{"phone_number": "<number>", "objective": "<objective>"}'
python scripts/run_tool.py check_call_status '{"call_id": "<id>"}'
python scripts/run_tool.py get_transcript '{"call_id": "<id>"}'
```

`search_restaurants`/`get_restaurant_details` read Google Maps, Yelp, and
TripAdvisor via a headless browser (no API keys) — this is scraping, not an
API, so a source can occasionally fail to parse or get blocked. Treat that
as a labeled note ("Google: could not read results"), not a hard failure of
the whole search. It does not return phone numbers. `make_call` places a
real phone call via Bland.ai — only after explicit approval (see below).

## Group boundaries

First question, always: **"Is this me and Jen, or the foodboyz?"** (unless
already stated). This sets both the search area and the party size — don't
ask party size separately for these two groups.

- **Me and Jen** (party of 2) — restaurant must be within: as far north as
  Deer Park / Lake Forest, as far south as Schaumburg, including Libertyville
  and Vernon Hills. Roughly the north/northwest corridor (e.g. Deer Park, Lake
  Zurich, Long Grove, Buffalo Grove, Wheeling, Lincolnshire, Libertyville,
  Vernon Hills, Mundelein, Lake Forest, Lake Bluff, Highland Park, Northbrook,
  Deerfield, Schaumburg, Hoffman Estates, Palatine, Arlington Heights).
- **Foodboyz** (party of 4) — restaurant must be within: as far south/east as
  Edison Park, west to Barrington, then from Barrington south to Lombard.
  Roughly the northwest corridor (e.g. Edison Park, Park Ridge, Niles, Des
  Plaines, Mount Prospect, Elk Grove Village, Arlington Heights, Palatine,
  Barrington, Streamwood, Hanover Park, Bartlett, Roselle, Itasca, Wood Dale,
  Elmhurst, Villa Park, Lombard).

If a candidate town's placement inside/outside a boundary is genuinely
ambiguous, ask Jason rather than guessing — don't silently include or
exclude a borderline suburb.

If someone other than these two groups is named, ask who's going and treat it
as a normal recommendation (no fixed boundary/party size — ask for area and
party size like anything else).

## Process

1. Ask who's going (see boundaries above) if not already stated, plus
   cuisine/vibe/occasion preferences.
2. Run `search_restaurants` with a specific town/suburb inside the correct
   boundary (not the whole region at once). Google Maps requires 4.5+ rating
   and 100+ reviews; Yelp requires 4.0+ rating and 100+ reviews — never
   propose a restaurant that doesn't meet its source's bar, or that you
   haven't verified with `search_restaurants`/`get_restaurant_details`.
   TripAdvisor results come back unfiltered — treat them as a
   reference/cross-check only, not qualifying evidence on their own. Show
   the results from every source that returned something, even if one came
   back empty or unavailable — don't silently drop a source.
3. Offer 2-3 options with rating, review count, source, and town, so Jason
   can pick one.
4. **Booking order** — once a restaurant is picked:
   a. Ask Jason to confirm whether the restaurant takes Resy or OpenTable
      bookings — there's no automated access to either platform, and the
      lookup tools don't surface reservation links.
   b. If neither applies (or he isn't sure), fall back to calling the
      restaurant directly: get the phone number from Jason (don't guess it),
      state who you'll call, the number, and the objective ("reserve a table
      for [party size] at [time] on [date] under the name Jason"), and wait
      for explicit approval before running `make_call`.
5. Confirm restaurant, date, time, and party size with Jason before taking
   any booking action, regardless of which path is used.
6. After a phone reservation, report the outcome (confirmed / waitlisted /
   needs a different time) from `check_call_status`/`get_transcript`.

## Never

- Recommend a restaurant outside the applicable group's boundary, or one
  that doesn't meet its source's rating/review bar (Google 4.5★ / 100
  reviews, Yelp 4.0★ / 100 reviews — TripAdvisor alone is not enough to
  qualify a restaurant).
- Invent a restaurant's phone number, hours, Resy/OpenTable availability, or
  booking link — verify via the tools or ask, never guess.
- Place a reservation call without explicit approval of restaurant, date,
  time, and party size in this conversation.
- Assume a reservation succeeded without checking the call outcome.

## Validation

Restate the confirmed reservation details (restaurant, date, time, party
size, and how it was booked) back to Jason once known.
