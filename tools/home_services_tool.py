"""
Home services lookup tools (insulation, handyman, plumbing, electrical,
etc.) — no API keys. Reads Yelp (primary) and Google Maps (reference) via a
headless browser. See tools/_web_lookup.py for the shared scraping and its
caveats.
"""

import asyncio

from playwright.async_api import async_playwright

from tools._web_lookup import err, ok, scrape_google_maps, scrape_yelp

_YELP_MIN_RATING = 4.0
_MIN_REVIEWS = 50
_DEFAULT_LOCATION = "60010"


async def _run_all(location: str, term: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            sections = await asyncio.gather(
                scrape_yelp(browser, location, term, _YELP_MIN_RATING, _MIN_REVIEWS),
                scrape_google_maps(browser, location, term, 0, 0),
            )
        finally:
            await browser.close()
    yelp_section, google_section = sections
    google_section = google_section.replace(
        "Google:", "Google (reference only, no rating threshold applied):", 1
    )
    return "\n\n".join([yelp_section, google_section])


async def search_home_services(args: dict) -> dict:
    """Search Yelp (primary — requires rating >= 4.0 and review_count >= 50)
    and Google Maps (reference only, unfiltered) via headless browser for a
    home services provider (insulation, handyman, plumbing, electrical,
    roofing, HVAC, etc.). Defaults to zip 60010 (Barrington) if no location
    is given. No API keys required."""
    location = args.get("location") or _DEFAULT_LOCATION
    term = args.get("service", "")

    if not term:
        return err("service is required (e.g. service='electrician').")

    text = await _run_all(location, term)
    return ok(text)


async def get_home_service_details(args: dict) -> dict:
    """Look up a specific home services provider by name (in the 60010 area
    unless a different location is given) on Yelp and Google Maps for
    rating and review count."""
    name = args.get("name", "")
    location = args.get("location") or _DEFAULT_LOCATION

    if not name:
        return err("name is required.")

    text = await _run_all(location, name)
    return ok(text)
