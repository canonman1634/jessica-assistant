"""
Restaurant lookup tools — no API keys. Uses a headless browser (Playwright)
to read Google Maps, Yelp, and TripAdvisor search results directly, since
none of those offer a workable free API anymore.

This is inherently more fragile than an API: each site's markup can change
and break the parsing below. Every source is wrapped so a parse failure or
a block just shows up as a labeled note ("Google: could not read results")
instead of taking down the whole search — treat that as a signal to fix the
scraper, not as "no restaurants found."

Low personal-use volume only — one query at a time, no retries, no proxy
rotation, no CAPTCHA solving. If a site blocks the request, that source is
reported as unavailable rather than worked around.
"""

import asyncio
import logging
import re

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_GOOGLE_MIN_RATING = 4.5
_YELP_MIN_RATING = 4.0
_MIN_REVIEWS = 100

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_NAV_TIMEOUT_MS = 20_000


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


async def _new_page(browser):
    context = await browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 1800})
    page = await context.new_page()
    page.set_default_timeout(_NAV_TIMEOUT_MS)
    return context, page


async def _scrape_google(browser, location: str, term: str) -> str:
    context, page = await _new_page(browser)
    try:
        query = f"{term} in {location}"
        await page.goto(f"https://www.google.com/maps/search/{query}", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        cards = await page.locator('div[role="feed"] > div').all()
        results = []
        for card in cards[:25]:
            text = await card.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if not lines:
                continue
            m = re.search(r"(\d\.\d)\((\d[\d,]*)\)", text)
            if not m:
                continue
            rating = float(m.group(1))
            reviews = int(m.group(2).replace(",", ""))
            name = lines[0]
            if rating >= _GOOGLE_MIN_RATING and reviews >= _MIN_REVIEWS:
                results.append((name, rating, reviews))

        if not results:
            return "Google: no results parsed, or none met the 4.5+ rating / 100+ review bar."
        lines = [f"  - {n} — {r}★ ({rv} reviews)" for n, r, rv in results]
        return "Google:\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("Google Maps scrape failed: %s", e)
        return f"Google: could not read results ({e})."
    finally:
        await context.close()


async def _scrape_yelp(browser, location: str, term: str) -> str:
    context, page = await _new_page(browser)
    try:
        await page.goto(
            f"https://www.yelp.com/search?find_desc={term}&find_loc={location}",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(2000)

        links = await page.locator('a[href*="/biz/"]').all()
        seen = set()
        results = []
        for link in links[:40]:
            name = (await link.inner_text()).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            container = link.locator(
                "xpath=ancestor::li[1] | xpath=ancestor::div[contains(@class,'businessName') or position()=1][1]"
            ).first
            try:
                block_text = await container.inner_text()
            except Exception:
                continue
            m_rating = re.search(r"(\d(?:\.\d)?) star rating", block_text)
            m_reviews = re.search(r"\((\d[\d,]*)\)", block_text)
            if not (m_rating and m_reviews):
                continue
            rating = float(m_rating.group(1))
            reviews = int(m_reviews.group(1).replace(",", ""))
            if rating >= _YELP_MIN_RATING and reviews >= _MIN_REVIEWS:
                results.append((name, rating, reviews))

        if not results:
            return "Yelp: no results parsed, or none met the 4.0+ rating / 100+ review bar."
        lines = [f"  - {n} — {r}★ ({rv} reviews)" for n, r, rv in results]
        return "Yelp:\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("Yelp scrape failed: %s", e)
        return f"Yelp: could not read results ({e})."
    finally:
        await context.close()


async def _scrape_tripadvisor(browser, location: str, term: str) -> str:
    context, page = await _new_page(browser)
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
                _scrape_google(browser, location, term),
                _scrape_yelp(browser, location, term),
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
        return _err("location is required (e.g. a specific town/suburb name).")

    text = await _run_all(location, term)
    return _ok(text)


async def get_restaurant_details(args: dict) -> dict:
    """Look up a specific restaurant by name + location across Google, Yelp,
    and TripAdvisor (via headless browser) for rating and review count."""
    name = args.get("name", "")
    location = args.get("location", "")

    if not name or not location:
        return _err("name and location are required.")

    text = await _run_all(location, name)
    return _ok(text)
