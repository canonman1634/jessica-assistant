"""
Restaurant lookup tools — queries Google Places (primary), Yelp (best-effort;
account may be on a paid plan or unconfigured), and TripAdvisor, and returns
each source's results labeled separately so Jessica can display all of them.
Rating/review-count filtering (4.0+, 100+ reviews) happens client-side.
"""

import logging
import requests
from config import GOOGLE_PLACES_API_KEY, YELP_API_KEY, TRIPADVISOR_API_KEY

logger = logging.getLogger(__name__)

_MIN_RATING = 4.0
_MIN_REVIEWS = 100


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _search_google(location: str, term: str) -> str:
    if not GOOGLE_PLACES_API_KEY:
        return "Google: skipped (GOOGLE_PLACES_API_KEY not configured)."
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": f"{term} in {location}", "key": GOOGLE_PLACES_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.exception("Google Places search failed")
        return f"Google: request failed ({e})."

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        return f"Google: error ({data.get('status')}: {data.get('error_message', '')})."

    matches = [
        r for r in data.get("results", [])
        if r.get("rating", 0) >= _MIN_RATING and r.get("user_ratings_total", 0) >= _MIN_REVIEWS
    ]
    if not matches:
        return "Google: no results met the 4.0+ rating / 100+ review bar."

    lines = [
        f"  - {r['name']} — {r['rating']}★ ({r['user_ratings_total']} reviews), {r.get('formatted_address', '')}"
        for r in matches[:10]
    ]
    return "Google:\n" + "\n".join(lines)


def _search_yelp(location: str, term: str, price: str | None) -> str:
    if not YELP_API_KEY:
        return "Yelp: skipped (YELP_API_KEY not configured)."
    params = {"location": location, "term": term, "sort_by": "rating", "limit": 20}
    if price:
        params["price"] = price
    try:
        resp = requests.get(
            "https://api.yelp.com/v3/businesses/search",
            headers={"Authorization": f"Bearer {YELP_API_KEY}"},
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # Yelp's free tier is gone — a 401/402/429 here is expected if the
        # account isn't on a paid plan. Report it as a source-level note,
        # not a hard failure of the whole search.
        logger.warning("Yelp search failed: %s", e)
        return f"Yelp: unavailable ({e})."

    businesses = resp.json().get("businesses", [])
    matches = [
        b for b in businesses
        if b.get("rating", 0) >= _MIN_RATING and b.get("review_count", 0) >= _MIN_REVIEWS
    ]
    if not matches:
        return "Yelp: no results met the 4.0+ rating / 100+ review bar."

    lines = [
        f"  - {b['name']} — {b['rating']}★ ({b['review_count']} reviews), "
        f"{', '.join(b.get('location', {}).get('display_address', []))}, "
        f"phone: {b.get('display_phone', 'n/a')}"
        for b in matches
    ]
    return "Yelp:\n" + "\n".join(lines)


def _search_tripadvisor(location: str, term: str) -> str:
    if not TRIPADVISOR_API_KEY:
        return "TripAdvisor: skipped (TRIPADVISOR_API_KEY not configured)."
    try:
        resp = requests.get(
            "https://api.content.tripadvisor.com/api/v1/location/search",
            params={
                "key": TRIPADVISOR_API_KEY,
                "searchQuery": f"{term} {location}",
                "category": "restaurants",
                "language": "en",
            },
            headers={"accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        candidates = resp.json().get("data", [])
    except requests.RequestException as e:
        logger.exception("TripAdvisor search failed")
        return f"TripAdvisor: request failed ({e})."

    if not candidates:
        return "TripAdvisor: no results found."

    lines = []
    for c in candidates[:8]:
        loc_id = c.get("location_id")
        if not loc_id:
            continue
        try:
            d_resp = requests.get(
                f"https://api.content.tripadvisor.com/api/v1/location/{loc_id}/details",
                params={"key": TRIPADVISOR_API_KEY, "language": "en"},
                headers={"accept": "application/json"},
                timeout=15,
            )
            d_resp.raise_for_status()
            d = d_resp.json()
        except requests.RequestException:
            continue

        rating = float(d.get("rating") or 0)
        num_reviews = int(d.get("num_reviews") or 0)
        if rating >= _MIN_RATING and num_reviews >= _MIN_REVIEWS:
            lines.append(
                f"  - {d.get('name', c.get('name'))} — {rating}★ ({num_reviews} reviews), "
                f"{d.get('address_obj', {}).get('address_string', '')}"
            )

    if not lines:
        return "TripAdvisor: no results met the 4.0+ rating / 100+ review bar."
    return "TripAdvisor:\n" + "\n".join(lines)


async def search_restaurants(args: dict) -> dict:
    """Search Google Places, Yelp, and TripAdvisor for restaurants near a
    location. Filters each source to rating >= 4.0 and review_count >= 100.
    Always attempts all three sources and labels results by source, even if
    one is unconfigured or errors."""
    location = args.get("location", "")
    term = args.get("term", "restaurants")
    price = args.get("price")

    if not location:
        return _err("location is required (e.g. a specific town/suburb name).")

    sections = [
        _search_google(location, term),
        _search_yelp(location, term, price),
        _search_tripadvisor(location, term),
    ]
    return _ok("\n\n".join(sections))


async def get_restaurant_details(args: dict) -> dict:
    """Look up a specific restaurant by name + location across Google, Yelp,
    and TripAdvisor for rating, review count, and phone number."""
    name = args.get("name", "")
    location = args.get("location", "")

    if not name or not location:
        return _err("name and location are required.")

    sections = [
        _search_google(location, name),
        _search_yelp(location, name, None),
        _search_tripadvisor(location, name),
    ]
    return _ok("\n\n".join(sections))
