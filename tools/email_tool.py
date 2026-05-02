"""
Gmail API tools — search, read, draft, send emails.
Registered as an MCP server for the Claude Agent SDK.
"""

import base64
import email as email_lib
import logging
from email.mime.text import MIMEText
from typing import Any

from claude_agent_sdk import tool, create_sdk_mcp_server
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
    """Extract plain-text body from a Gmail message payload."""
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


@tool(
    "list_unread",
    "List unread emails from Gmail inbox with subject, sender, and snippet. Returns up to 10 emails.",
    {},
)
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


@tool(
    "search_emails",
    "Search Gmail using a query string (e.g. 'from:school subject:report'). Returns up to 10 results.",
    {"query": str, "max_results": int},
)
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


@tool(
    "read_email",
    "Read the full content of an email by its Gmail message ID.",
    {"email_id": str},
)
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


@tool(
    "send_email",
    "Send an email via Gmail. Only call this AFTER Jason has approved the draft.",
    {"to": str, "subject": str, "body": str},
)
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


def build_email_server():
    return create_sdk_mcp_server(
        name="email",
        version="1.0.0",
        tools=[list_unread, search_emails, read_email, send_email],
    )
