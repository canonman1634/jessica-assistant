"""
My Bright Day / Bright Horizons school update tools.
Reads school updates by searching for Bright Horizons emails in Gmail.
"""

import base64
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from tools._google_auth import get_google_credentials
from config import TZ

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)

_SCHOOL_QUERY = (
    "from:(brighthorizons.com OR mybrightday OR brightday OR tadpoles) "
    "OR subject:(bright horizons OR daily report OR daycare update)"
)


def _gmail_service():
    creds = get_google_credentials()
    return build("gmail", "v1", credentials=creds)


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _decode_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _decode_body(part)
            if text:
                return text
    return ""


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


async def check_school_updates(args: dict) -> dict:
    days_back = int(args.get("days_back", 1))
    try:
        svc = _gmail_service()
        after_date = (datetime.now(_TZ) - timedelta(days=days_back)).strftime("%Y/%m/%d")
        query = f"({_SCHOOL_QUERY}) after:{after_date}"
        results = svc.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = results.get("messages", [])
        if not messages:
            return _ok(f"No school updates in the last {days_back} day(s).")
        lines = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            snippet = _clean_text(msg.get("snippet", ""))[:150]
            lines.append(
                f"Subject: {headers.get('Subject', '(no subject)')}\n"
                f"Date: {headers.get('Date', '?')}\n"
                f"Preview: {snippet}"
            )
        return _ok(
            f"School updates (last {days_back} day(s)) — {len(messages)} email(s):\n\n"
            + "\n\n---\n\n".join(lines)
        )
    except Exception as e:
        logger.exception("check_school_updates failed")
        return _err(f"Failed to check school updates: {e}")


async def get_daily_report(_args: dict) -> dict:
    try:
        svc = _gmail_service()
        query = f"({_SCHOOL_QUERY}) subject:(daily report OR today's update OR activity)"
        results = svc.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = results.get("messages", [])
        if not messages:
            return _ok("No daily report found. Make sure email notifications are enabled in the My Bright Day app.")
        msg = svc.users().messages().get(userId="me", id=messages[0]["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        body = _clean_text(_decode_body(msg["payload"]))
        return _ok(
            f"Latest Daily Report\n"
            f"From: {headers.get('From', '?')}\n"
            f"Date: {headers.get('Date', '?')}\n"
            f"Subject: {headers.get('Subject', '?')}\n\n"
            f"{body}"
        )
    except Exception as e:
        logger.exception("get_daily_report failed")
        return _err(f"Failed to get daily report: {e}")
