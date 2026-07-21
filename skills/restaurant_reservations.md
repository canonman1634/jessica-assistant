---
name: restaurant_reservations
trigger: any request for a restaurant recommendation or to make/change a restaurant reservation
---

# Skill: Restaurant reservations & recommendations

## Inputs
- Your own knowledge for recommendations (no live search tool exists yet)
- Remembered facts (`remember`/`forget`, category `prefs`/`people`/`notes`) for
  cuisine preferences, dietary restrictions, past favorites, and go-to spots
- Bland.ai via `make_call`, `check_call_status`, `get_transcript` to actually
  place a reservation call

## Procedure
1. **Recommendations**: ask enough to narrow it down — cuisine, neighborhood/
   city, party size, occasion, budget — using what's already remembered about
   the owner's tastes before asking again. Offer 2-3 options with a short
   reason each, not an exhaustive list.
2. **Reservations**: once a restaurant is picked, you need its phone number.
   If it's not already known from context/memory, ask the owner for it rather
   than guessing — don't invent or look up a phone number.
3. Confirm restaurant name, phone number, date, time, and party size with the
   owner before calling.
4. Follow the phone-calls skill: state who you'll call, the number, and the
   objective ("reserve a table for N at [time] on [date] under the name
   [owner]"), then wait for explicit approval before `make_call`.
5. After the call, report back the outcome (confirmed / waitlisted / needs a
   different time) from `check_call_status`/`get_transcript`.
6. If the owner mentions a lasting preference (favorite restaurant, dietary
   restriction, disliked cuisine), offer to `remember` it for next time.

## Never
- Invent a restaurant's phone number, hours, or availability — say if you
  don't know rather than guessing.
- Place the reservation call without explicit approval of restaurant, date,
  time, and party size in this conversation.
- Assume a reservation succeeded without checking the call outcome.

## Validation
- Restate the confirmed reservation details (or the failure reason) back to
  the owner once the call result is known.
