"""
Yelp Fusion tools — restaurant search/lookup for recommendations.
Rating and review-count filtering happens client-side since Yelp's API
doesn't support a minimum-review-count query param.
"""

import logging
import requests
from config import YELP_API_KEY

logger = logging.getLogger(__name__)

_YELP_BASE = "https://api.yelp.com/v3"
_HEADERS = {"Authorization": f"Bearer {YELP_API_KEY}"}


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


async def search_restaurants(args: dict) -> dict:
    """Search Yelp for restaurants near a location, filtered to rating >= 4.0
    and review_count >= 100."""
    location = args.get("location", "")
    term = args.get("term", "restaurants")
    price = args.get("price")  # optional "1,2,3,4"

    if not YELP_API_KEY:
        return _err("YELP_API_KEY is not configured.")
    if not location:
        return _err("location is required (e.g. a city/suburb name).")

    params = {
        "location": location,
        "term": term,
        "sort_by": "rating",
        "limit": 20,
    }
    if price:
        params["price"] = price

    try:
        resp = requests.get(f"{_YELP_BASE}/businesses/search", headers=_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.exception("Yelp search failed")
        return _err(f"Yelp search failed: {e}")

    businesses = resp.json().get("businesses", [])
    matches = [
        b for b in businesses
        if b.get("rating", 0) >= 4.0 and b.get("review_count", 0) >= 100
    ]

    if not matches:
        return _ok(f"No restaurants near '{location}' met the 4.0+ rating / 100+ review bar.")

    lines = []
    for b in matches:
        addr = ", ".join(b.get("location", {}).get("display_address", []))
        lines.append(
            f"- {b['name']} — {b['rating']}★ ({b['review_count']} reviews), "
            f"{b.get('price', 'n/a')}, {addr}, phone: {b.get('display_phone', 'n/a')}, "
            f"yelp: {b.get('url', '')}"
        )
    return _ok("\n".join(lines))


async def get_restaurant_details(args: dict) -> dict:
    """Look up a specific restaurant on Yelp by name + location for rating,
    review count, phone, and Yelp page (Yelp page sometimes links out to
    Resy/OpenTable reservation widgets)."""
    name = args.get("name", "")
    location = args.get("location", "")

    if not YELP_API_KEY:
        return _err("YELP_API_KEY is not configured.")
    if not name or not location:
        return _err("name and location are required.")

    params = {"term": name, "location": location, "limit": 1}
    try:
        resp = requests.get(f"{_YELP_BASE}/businesses/search", headers=_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.exception("Yelp lookup failed")
        return _err(f"Yelp lookup failed: {e}")

    businesses = resp.json().get("businesses", [])
    if not businesses:
        return _err(f"No Yelp match found for '{name}' near '{location}'.")

    b = businesses[0]
    addr = ", ".join(b.get("location", {}).get("display_address", []))
    transactions = ", ".join(b.get("transactions", [])) or "none listed"
    return _ok(
        f"{b['name']} — {b['rating']}★ ({b['review_count']} reviews), "
        f"{addr}, phone: {b.get('display_phone', 'n/a')}, "
        f"yelp: {b.get('url', '')}, yelp transactions: {transactions}"
    )
