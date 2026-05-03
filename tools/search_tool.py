"""
Web search tool via Tavily API — lets Jessica look up businesses, reviews,
hours, and general information on the web.
"""

import logging
import requests
from config import TAVILY_API_KEY

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


async def web_search(args: dict) -> dict:
    query = args.get("query", "").strip()
    max_results = min(int(args.get("max_results", 5)), 10)

    if not query:
        return _err("query is required")

    if not TAVILY_API_KEY:
        return _err("Web search is not configured (TAVILY_API_KEY missing).")

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": max_results,
    }

    try:
        resp = requests.post(_TAVILY_URL, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        logger.exception("web_search HTTP error")
        return _err(f"Search failed: {e.response.text}")
    except Exception as e:
        logger.exception("web_search failed")
        return _err(f"Search failed: {e}")

    lines = []

    answer = data.get("answer", "")
    if answer:
        lines.append(f"Summary: {answer}\n")

    results = data.get("results", [])
    if not results:
        return _ok("No results found.")

    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")[:300]
        lines.append(f"{i}. {title}\n   {url}\n   {content}")

    return _ok("\n\n".join(lines))
