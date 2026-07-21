---
name: restaurant_reservations
trigger: any request for a restaurant recommendation or to make/change a restaurant reservation
---

# Skill: Restaurant reservations & recommendations

## Inputs
- `search_restaurants`, `get_restaurant_details` — queries Google Places
  (primary), Yelp, and TripAdvisor for rating/review-count verification and
  phone numbers; results come back labeled by source
- Your own knowledge for narrowing down cuisine/vibe within the allowed area
- Remembered facts (`remember`/`forget`, category `prefs`/`people`/`notes`) for
  cuisine preferences, dietary restrictions, past favorites, and go-to spots
- Bland.ai via `make_call`, `check_call_status`, `get_transcript` for phone
  reservations when no online booking is available

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
ambiguous, ask the owner rather than guessing — don't silently include or
exclude a borderline suburb.

If someone other than these two groups is named, ask who's going and treat it
as a normal recommendation (no fixed boundary/party size — ask for area and
party size like anything else).

## Procedure
1. Ask who's going (see boundaries above) if not already stated, plus
   cuisine/vibe/occasion preferences — check remembered prefs first before
   asking again.
2. Use `search_restaurants` with a specific town/suburb inside the correct
   boundary (not the whole region at once) to find candidates. It queries
   Google (primary, 4.5+ rating / 100+ reviews) and Yelp (4.0+ rating / 100+
   reviews) as hard filters — never propose a restaurant that doesn't meet
   its source's bar, or that you haven't verified with
   `search_restaurants`/`get_restaurant_details`. TripAdvisor results come
   back unfiltered — treat them as a reference/cross-check only, not
   qualifying evidence on their own. Always show the owner the results from
   every source that returned something (labeled Google/Yelp/TripAdvisor),
   even if one source came back empty or unavailable — don't silently drop a
   source. If a source is skipped/unconfigured (e.g. Yelp has no free tier
   anymore and may need a paid key), say so briefly rather than pretending it
   wasn't tried.
3. Offer 2-3 options with rating, review count, source, and town, so the
   owner can confirm none of them are recent duplicates/misses before
   picking one.
4. **Booking order** — once a restaurant is picked:
   a. Check the Yelp result from `get_restaurant_details` for a Resy or
      OpenTable link/mention (the `transactions` field or the Yelp page).
   b. If nothing conclusive there, ask the owner to confirm whether the
      restaurant takes Resy or OpenTable bookings — you don't have direct
      Resy/OpenTable account access, so you can't silently browse either
      platform.
   c. If neither applies (or the owner isn't sure), fall back to calling the
      restaurant directly via `make_call`, per the phone-calls skill: state
      who you'll call, the number (from the Yelp lookup or the owner), and
      the objective ("reserve a table for [party size] at [time] on [date]
      under the name [owner]"), then wait for explicit approval before
      calling.
5. Confirm restaurant, date, time, and party size with the owner before
   taking any booking action, regardless of which path is used.
6. After a phone reservation, report the outcome (confirmed / waitlisted /
   needs a different time) from `check_call_status`/`get_transcript`.
7. If the owner mentions a lasting preference (favorite restaurant, dietary
   restriction, disliked cuisine), offer to `remember` it for next time.

## Never
- Recommend a restaurant outside the applicable group's boundary, or one that
  doesn't meet its source's rating/review bar (Google 4.5★ / 100 reviews,
  Yelp 4.0★ / 100 reviews — TripAdvisor alone is not enough to qualify a
  restaurant).
- Invent a restaurant's phone number, hours, Resy/OpenTable availability, or
  booking link — verify via the tools or ask, never guess.
- Place a reservation call without explicit approval of restaurant, date,
  time, and party size in this conversation.
- Assume a reservation succeeded without checking the call outcome.

## Validation
- Restate the confirmed reservation details (restaurant, date, time, party
  size, and how it was booked) back to the owner once known.
