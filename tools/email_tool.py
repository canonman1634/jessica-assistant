"""
Gmail API tools — search, read, draft, send emails.
"""

import base64
import logging
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from tools._google_auth import get_google_credentials

logger = logging.getLogger(__name__)


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


def send_email_direct(to: str, subject: str, body: str) -> None:
    """Send an email synchronously (used by scheduler, not via agent tool)."""
    svc = _gmail_service()
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info("Sent direct email to %s — %s", to, subject)


async def list_unread(_args: dict) -> dict:
    try:
        svc = _gmail_service()
        results = svc.users().messages().list(
            userId="me", q="is:unread in:inbox", maxResults=10
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return _ok("No unread emails.")
        lines = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            snippet = msg.get("snippet", "")[:100]
            lines.append(
                f"ID: {m['id']}\n"
                f"From: {headers.get('From', '?')}\n"
                f"Subject: {headers.get('Subject', '(no subject)')}\n"
                f"Preview: {snippet}"
            )
        return _ok(f"Unread emails ({len(messages)}):\n\n" + "\n\n---\n\n".join(lines))
    except Exception as e:
        logger.exception("list_unread failed")
        return _err(f"Failed to list emails: {e}")


async def search_emails(args: dict) -> dict:
    query = args.get("query", "")
    max_results = min(int(args.get("max_results", 10)), 20)
    try:
        svc = _gmail_service()
        results = svc.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return _ok(f"No emails found for query: {query}")
        lines = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            snippet = msg.get("snippet", "")[:100]
            lines.append(
                f"ID: {m['id']}\n"
                f"From: {headers.get('From', '?')}\n"
                f"Subject: {headers.get('Subject', '(no subject)')}\n"
                f"Date: {headers.get('Date', '?')}\n"
                f"Preview: {snippet}"
            )
        return _ok(f"Found {len(messages)} email(s):\n\n" + "\n\n---\n\n".join(lines))
    except Exception as e:
        logger.exception("search_emails failed")
        return _err(f"Search failed: {e}")


async def read_email(args: dict) -> dict:
    email_id = args.get("email_id", "")
    if not email_id:
        return _err("email_id is required")
    try:
        svc = _gmail_service()
        msg = svc.users().messages().get(
            userId="me", id=email_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        body = _decode_body(msg["payload"])[:3000]
        return _ok(
            f"From: {headers.get('From', '?')}\n"
            f"To: {headers.get('To', '?')}\n"
            f"Subject: {headers.get('Subject', '(no subject)')}\n"
            f"Date: {headers.get('Date', '?')}\n\n"
            f"{body}"
        )
    except Exception as e:
        logger.exception("read_email failed")
        return _err(f"Failed to read email: {e}")


async def send_email(args: dict) -> dict:
    to = args.get("to", "")
    subject = args.get("subject", "")
    body = args.get("body", "")
    if not all([to, subject, body]):
        return _err("to, subject, and body are all required")
    try:
        svc = _gmail_service()
        mime = MIMEText(body)
        mime["to"] = to
        mime["subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return _ok(f"Email sent to {to} with subject '{subject}'.")
    except Exception as e:
        logger.exception("send_email failed")
        return _err(f"Failed to send email: {e}")
