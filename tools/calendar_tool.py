"""
Google Calendar tools — check availability, list events, create/update events.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from claude_agent_sdk import tool, create_sdk_mcp_server
from googleapiclient.discovery import build

from tools._google_auth import get_google_credentials
from config import TZ

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)


def _calendar_service():
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds)


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _fmt_event(e: dict) -> str:
    start = e.get("start", {})
    time_str = start.get("dateTime", start.get("date", "?"))
    return f"• {e.get('summary', '(no title)')} — {time_str}"


@tool(
    "list_upcoming",
    "List upcoming calendar events. Optionally specify how many days ahead to look (default 7).",
    {"days_ahead": int},
)
async def list_upcoming(args: dict) -> dict:
    days = int(args.get("days_ahead", 7))
    try:
        svc = _calendar_service()
        now = datetime.now(_TZ)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()
        result = svc.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        if not events:
            return _ok(f"No events in the next {days} days.")
        lines = [_fmt_event(e) for e in events]
        return _ok(f"Upcoming events (next {days} days):\n" + "\n".join(lines))
    except Exception as e:
        logger.exception("list_upcoming failed")
        return _err(f"Failed to list events: {e}")


@tool(
    "check_availability",
    "Check if a specific time slot is free on the calendar.",
    {"date": str, "start_time": str, "end_time": str},
)
async def check_availability(args: dict) -> dict:
    date = args.get("date", "")
    start_time = args.get("start_time", "")
    end_time = args.get("end_time", "")
    if not all([date, start_time, end_time]):
        return _err("date, start_time, and end_time are required (e.g. '2026-05-15', '14:00', '15:00')")
    try:
        svc = _calendar_service()
        time_min = datetime.fromisoformat(f"{date}T{start_time}").replace(tzinfo=_TZ).isoformat()
        time_max = datetime.fromisoformat(f"{date}T{end_time}").replace(tzinfo=_TZ).isoformat()
        result = svc.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
        ).execute()
        events = result.get("items", [])
        if not events:
            return _ok(f"You're free on {date} from {start_time} to {end_time}.")
        conflicts = [_fmt_event(e) for e in events]
        return _ok(
            f"Conflict found on {date} {start_time}–{end_time}:\n" + "\n".join(conflicts)
        )
    except Exception as e:
        logger.exception("check_availability failed")
        return _err(f"Failed to check availability: {e}")


@tool(
    "create_event",
    "Create a new calendar event. Only call after Jason has confirmed the details.",
    {"title": str, "date": str, "start_time": str, "end_time": str, "description": str, "location": str},
)
async def create_event(args: dict) -> dict:
    title = args.get("title", "")
    date = args.get("date", "")
    start_time = args.get("start_time", "")
    end_time = args.get("end_time", "")
    if not all([title, date, start_time, end_time]):
        return _err("title, date, start_time, and end_time are required")
    try:
        svc = _calendar_service()
        event = {
            "summary": title,
            "description": args.get("description", ""),
            "location": args.get("location", ""),
            "start": {
                "dateTime": datetime.fromisoformat(f"{date}T{start_time}").replace(tzinfo=_TZ).isoformat(),
                "timeZone": TZ,
            },
            "end": {
                "dateTime": datetime.fromisoformat(f"{date}T{end_time}").replace(tzinfo=_TZ).isoformat(),
                "timeZone": TZ,
            },
        }
        created = svc.events().insert(calendarId="primary", body=event).execute()
        return _ok(f"Event created: '{title}' on {date} {start_time}–{end_time}. ID: {created['id']}")
    except Exception as e:
        logger.exception("create_event failed")
        return _err(f"Failed to create event: {e}")


@tool(
    "update_event",
    "Update an existing calendar event by event ID.",
    {"event_id": str, "title": str, "date": str, "start_time": str, "end_time": str, "description": str},
)
async def update_event(args: dict) -> dict:
    event_id = args.get("event_id", "")
    if not event_id:
        return _err("event_id is required")
    try:
        svc = _calendar_service()
        existing = svc.events().get(calendarId="primary", eventId=event_id).execute()
        if args.get("title"):
            existing["summary"] = args["title"]
        if args.get("description"):
            existing["description"] = args["description"]
        if args.get("date") and args.get("start_time"):
            existing["start"] = {
                "dateTime": datetime.fromisoformat(
                    f"{args['date']}T{args['start_time']}"
                ).replace(tzinfo=_TZ).isoformat(),
                "timeZone": TZ,
            }
        if args.get("date") and args.get("end_time"):
            existing["end"] = {
                "dateTime": datetime.fromisoformat(
                    f"{args['date']}T{args['end_time']}"
                ).replace(tzinfo=_TZ).isoformat(),
                "timeZone": TZ,
            }
        updated = svc.events().update(
            calendarId="primary", eventId=event_id, body=existing
        ).execute()
        return _ok(f"Event updated: '{updated.get('summary')}' — {updated.get('start', {}).get('dateTime', '?')}")
    except Exception as e:
        logger.exception("update_event failed")
        return _err(f"Failed to update event: {e}")


def build_calendar_server():
    return create_sdk_mcp_server(
        name="calendar",
        version="1.0.0",
        tools=[list_upcoming, check_availability, create_event, update_event],
    )
