"""
Shared headless-browser lookup helpers — no API keys. Reads Google Maps and
Yelp search results directly, since neither offers a workable free API
anymore. Used by restaurant_tool.py and home_services_tool.py.

This is inherently more fragile than an API: each site's markup can change
and break the parsing below. Callers should treat a parse failure or a
block as a signal to fix the scraper, not as "nothing found."

Low personal-use volume only — one query at a time, no retries, no proxy
rotation, no CAPTCHA solving. If a site blocks the request, that's reported
as unavailable rather than worked around.
"""

import logging
import re

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
NAV_TIMEOUT_MS = 20_000


def ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


async def new_page(browser):
    context = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 1800})
    page = await context.new_page()
    page.set_default_timeout(NAV_TIMEOUT_MS)
    return context, page


async def scrape_google_maps(browser, location: str, term: str, min_rating: float, min_reviews: int) -> str:
    """Google Maps search, filtered to rating >= min_rating and review_count
    >= min_reviews. Pass min_rating=0 to show results unfiltered."""
    context, page = await new_page(browser)
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
            if rating >= min_rating and reviews >= min_reviews:
                results.append((name, rating, reviews))

        if not results:
            return f"Google: no results parsed, or none met the {min_rating}+ rating / {min_reviews}+ review bar."
        lines = [f"  - {n} — {r}★ ({rv} reviews)" for n, r, rv in results]
        return "Google:\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("Google Maps scrape failed: %s", e)
        return f"Google: could not read results ({e})."
    finally:
        await context.close()


async def scrape_yelp(browser, location: str, term: str, min_rating: float, min_reviews: int) -> str:
    """Yelp search, filtered to rating >= min_rating and review_count >=
    min_reviews. Pass min_rating=0 to show results unfiltered."""
    context, page = await new_page(browser)
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
            if rating >= min_rating and reviews >= min_reviews:
                results.append((name, rating, reviews))

        if not results:
            return f"Yelp: no results parsed, or none met the {min_rating}+ rating / {min_reviews}+ review bar."
        lines = [f"  - {n} — {r}★ ({rv} reviews)" for n, r, rv in results]
        return "Yelp:\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("Yelp scrape failed: %s", e)
        return f"Yelp: could not read results ({e})."
    finally:
        await context.close()
