"""
Restaurant lookup tools — no API keys. Reads Google Maps, Yelp, and
TripAdvisor search results via a headless browser (Playwright). See
tools/_web_lookup.py for the shared Google/Yelp scraping and its caveats.
"""

import asyncio
import logging
import re

from playwright.async_api import async_playwright

from tools._web_lookup import err, new_page, ok, scrape_google_maps, scrape_yelp

logger = logging.getLogger(__name__)

_GOOGLE_MIN_RATING = 4.5
_YELP_MIN_RATING = 4.0
_MIN_REVIEWS = 100


async def _scrape_tripadvisor(browser, location: str, term: str) -> str:
    context, page = await new_page(browser)
    try:
        await page.goto(
            f"https://www.tripadvisor.com/Search?q={term}+{location}",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(2000)

        body_text = await page.locator("body").inner_text()
        # TripAdvisor renders "Name ... 4.5 of 5 bubbles ... 1,234 reviews"
        # in the search results; scan line-by-line for that pattern near a
        # plausible business name.
        blocks = re.split(r"\n(?=[A-Z0-9])", body_text)
        results = []
        for b in blocks:
            m_rating = re.search(r"(\d\.\d) of 5 bubbles", b)
            m_reviews = re.search(r"([\d,]+) reviews?", b)
            if not (m_rating and m_reviews):
                continue
            name_line = b.strip().split("\n")[0][:80]
            rating = float(m_rating.group(1))
            reviews = int(m_reviews.group(1).replace(",", ""))
            results.append((name_line, rating, reviews))

        results = results[:10]
        if not results:
            return "TripAdvisor: no results parsed."
        lines = [f"  - {n} — {r}★ ({rv} reviews)" for n, r, rv in results]
        return "TripAdvisor (reference only, no rating threshold applied):\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("TripAdvisor scrape failed: %s", e)
        return f"TripAdvisor: could not read results ({e})."
    finally:
        await context.close()


async def _run_all(location: str, term: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            sections = await asyncio.gather(
                scrape_google_maps(browser, location, term, _GOOGLE_MIN_RATING, _MIN_REVIEWS),
                scrape_yelp(browser, location, term, _YELP_MIN_RATING, _MIN_REVIEWS),
                _scrape_tripadvisor(browser, location, term),
            )
        finally:
            await browser.close()
    return "\n\n".join(sections)


async def search_restaurants(args: dict) -> dict:
    """Search Google Maps, Yelp, and TripAdvisor (via headless browser, no
    API keys) for restaurants near a location. Google requires rating >= 4.5
    and review_count >= 100; Yelp requires rating >= 4.0 and review_count
    >= 100; TripAdvisor is shown unfiltered, as a reference only. Always
    attempts all three sources and labels results by source, even if one
    fails to parse."""
    location = args.get("location", "")
    term = args.get("term", "restaurants")

    if not location:
        return err("location is required (e.g. a specific town/suburb name).")

    text = await _run_all(location, term)
    return ok(text)


async def get_restaurant_details(args: dict) -> dict:
    """Look up a specific restaurant by name + location across Google, Yelp,
    and TripAdvisor (via headless browser) for rating and review count."""
    name = args.get("name", "")
    location = args.get("location", "")

    if not name or not location:
        return err("name and location are required.")

    text = await _run_all(location, name)
    return ok(text)
