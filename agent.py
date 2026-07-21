"""
Jessica — tool registry and system-prompt builder.
Defines the tools and per-capability skill docs an agent acts as Jessica
with; see skills/*.md for the procedural instructions each tool follows.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import load_context, TZ
from tools.email_tool import list_unread, search_emails, read_email, send_email
from tools.calendar_tool import list_upcoming, check_availability, create_event, update_event
from tools.phone_tool import make_call, check_call_status, get_transcript, list_recent_calls
from tools.school_tool import check_school_updates, get_daily_report
from tools.restaurant_tool import search_restaurants, get_restaurant_details
from tools.home_services_tool import search_home_services, get_home_service_details
from tools.memory_tool import remember, forget, load_memory_for_prompt, load_relevant_memory_for_prompt
from tools import vector_memory

logger = logging.getLogger(__name__)

_TZ = ZoneInfo(TZ)

_SKILLS_DIR = Path(__file__).parent / "skills"

# Tools whose successful calls are worth an episodic audit-trail entry.
_EPISODIC_TOOLS = {
    "send_email", "create_event", "update_event", "make_call",
}


def _load_procedural_memory() -> str:
    """Concatenate the git-committed skill docs — how to act, loaded fresh every turn."""
    if not _SKILLS_DIR.exists():
        return ""
    blocks = []
    for path in sorted(_SKILLS_DIR.glob("*.md")):
        blocks.append(path.read_text().strip())
    return "\n\n---\n\n".join(blocks)

# ── Tool registry ─────────────────────────────────────────────────────────────

_TOOL_HANDLERS = {
    "list_unread": list_unread,
    "search_emails": search_emails,
    "read_email": read_email,
    "send_email": send_email,
    "list_upcoming": list_upcoming,
    "check_availability": check_availability,
    "create_event": create_event,
    "update_event": update_event,
    "make_call": make_call,
    "check_call_status": check_call_status,
    "get_transcript": get_transcript,
    "list_recent_calls": list_recent_calls,
    "check_school_updates": check_school_updates,
    "get_daily_report": get_daily_report,
    "search_restaurants": search_restaurants,
    "get_restaurant_details": get_restaurant_details,
    "search_home_services": search_home_services,
    "get_home_service_details": get_home_service_details,
    "remember": remember,
    "forget": forget,
}

_TOOLS = [
    {"name": "list_unread", "description": "List unread emails from Gmail inbox with subject, sender, and snippet. Returns up to 10 emails.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "search_emails", "description": "Search Gmail using a query string (e.g. 'from:school subject:report'). Returns up to 10 results.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
    {"name": "read_email", "description": "Read the full content of an email by its Gmail message ID.", "input_schema": {"type": "object", "properties": {"email_id": {"type": "string"}}, "required": ["email_id"]}},
    {"name": "send_email", "description": "Send an email via Gmail. Only call this AFTER Jason has approved the draft.", "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}},
    {"name": "list_upcoming", "description": "List upcoming calendar events. Optionally specify how many days ahead to look (default 7).", "input_schema": {"type": "object", "properties": {"days_ahead": {"type": "integer"}}}},
    {"name": "check_availability", "description": "Check if a specific time slot is free on the calendar.", "input_schema": {"type": "object", "properties": {"date": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}}, "required": ["date", "start_time", "end_time"]}},
    {"name": "create_event", "description": "Create a new calendar event. Only call after Jason has confirmed the details.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "date": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "description": {"type": "string"}, "location": {"type": "string"}}, "required": ["title", "date", "start_time", "end_time"]}},
    {"name": "update_event", "description": "Update an existing calendar event by event ID.", "input_schema": {"type": "object", "properties": {"event_id": {"type": "string"}, "title": {"type": "string"}, "date": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"}, "description": {"type": "string"}}, "required": ["event_id"]}},
    {"name": "make_call", "description": "Initiate an AI phone call via Bland.ai. IMPORTANT: Only call this tool AFTER Jason has explicitly approved the call.", "input_schema": {"type": "object", "properties": {"phone_number": {"type": "string"}, "objective": {"type": "string"}, "context": {"type": "string"}, "provider_name": {"type": "string"}}, "required": ["phone_number", "objective"]}},
    {"name": "check_call_status", "description": "Check the status and outcome of a Bland.ai call by its call ID.", "input_schema": {"type": "object", "properties": {"call_id": {"type": "string"}}, "required": ["call_id"]}},
    {"name": "get_transcript", "description": "Get the full transcript of a completed Bland.ai call by its call ID.", "input_schema": {"type": "object", "properties": {"call_id": {"type": "string"}}, "required": ["call_id"]}},
    {"name": "list_recent_calls", "description": "List recent Bland.ai calls with their status and outcomes.", "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "check_school_updates", "description": "Check for recent My Bright Day / Bright Horizons emails. Returns updates from the last N days.", "input_schema": {"type": "object", "properties": {"days_back": {"type": "integer"}}}},
    {"name": "get_daily_report", "description": "Get the full content of the most recent My Bright Day daily report email.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "search_restaurants", "description": "Look up restaurants near a location via a headless browser against Google Maps (primary, 4.5+ rating / 100+ reviews), Yelp (4.0+ rating / 100+ reviews), and TripAdvisor (shown unfiltered, reference only), labeled by source (a source is noted if it fails to parse or gets blocked). No phone numbers are returned. Pass a specific town/suburb/neighborhood as location, not a wide region.", "input_schema": {"type": "object", "properties": {"location": {"type": "string"}, "term": {"type": "string"}}, "required": ["location"]}},
    {"name": "get_restaurant_details", "description": "Look up a specific restaurant by name + location across Google, Yelp, and TripAdvisor (via headless browser) for rating and review count, labeled by source. No phone numbers are returned.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "location": {"type": "string"}}, "required": ["name", "location"]}},
    {"name": "search_home_services", "description": "Look up a home services provider (insulation, handyman, plumbing, electrical, roofing, HVAC, etc.) via a headless browser. Always scoped to zip 60010 (Barrington) unless a different location is explicitly given. Yelp is the primary filter (4.0+ rating / 50+ reviews); Google Maps is shown unfiltered, as a reference only. No API keys, no phone numbers returned.", "input_schema": {"type": "object", "properties": {"location": {"type": "string"}, "service": {"type": "string"}}, "required": ["service"]}},
    {"name": "get_home_service_details", "description": "Look up a specific home services provider by name on Yelp and Google Maps for rating and review count. Defaults to the 60010 area unless a different location is given.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "location": {"type": "string"}}, "required": ["name"]}},
    {"name": "remember", "description": "Persist a fact for future sessions. category: 'people' (key=name, value=description), 'prefs' (key=preference, value=value), or 'notes' (key=the note itself). Call this whenever Jason shares a persistent fact (a contact, preference, or anything worth keeping).", "input_schema": {"type": "object", "properties": {"category": {"type": "string", "enum": ["people", "prefs", "notes"]}, "key": {"type": "string"}, "value": {"type": "string"}}, "required": ["category", "key"]}},
    {"name": "forget", "description": "Remove a stored fact from memory. Provide category and the key (or keyword for notes) to delete.", "input_schema": {"type": "object", "properties": {"category": {"type": "string", "enum": ["people", "prefs", "notes"]}, "key": {"type": "string"}}, "required": ["category", "key"]}},
]


def _build_system_prompt(current_message: str = "") -> str:
    ctx = load_context()
    owner = ctx["owner"]["name"]
    tz = ctx["owner"]["timezone"]
    children = ctx.get("children", [])
    now = datetime.now(_TZ).strftime("%A, %B %-d, %Y at %-I:%M %p CT")
    children_lines = "\n".join(
        f"  - {c['name']} (born {c['birthday']}, attends {c.get('school', 'Bright Horizons')})"
        for c in children
    )
    memory_block = load_memory_for_prompt()
    procedural_block = _load_procedural_memory()

    relevant_block = ""
    if current_message:
        relevant_block = load_relevant_memory_for_prompt(current_message)

    return f"""You are Jessica, a warm and friendly personal executive assistant for {owner}.

## Your personality
- Warm, personable, and efficient — like a trusted friend who happens to be incredibly organized
- Concise but never cold; use a natural, conversational tone
- Use first names when referring to family members
- Keep replies readable: short paragraphs or bullet points for lists

## Family context
- Owner: {owner} (timezone: {tz})
- Current time: {now}
- Children:
{children_lines}
- Both children attend Bright Horizons daycare (My Bright Day app)

## What you remember about {owner}
{memory_block}

## Relevant to this message
{relevant_block or "(nothing specifically retrieved)"}

## Your capabilities
- Check, search, and send emails (Gmail)
- Check and create Google Calendar events
- Make phone calls on {owner}'s behalf using an AI calling service
- Check school/daycare updates from My Bright Day
- Remember and forget facts across sessions

## How to operate each capability
{procedural_block}

## Rules you ALWAYS follow
1. **Privacy**: Never store sensitive information beyond what's needed for the immediate task.
2. **Uncertainty**: If unsure about a phone number, date, or detail — ask before acting.
3. Follow the per-capability rules above (email, calendar, phone, memory) exactly — they take precedence over general judgment."""


def _log_episodic_tool_action(tool_name: str, args: dict, result_text: str) -> None:
    """Write an audit-trail episodic card for an action Jessica actually took."""
    summaries = {
        "send_email": lambda a: f"Sent email to {a.get('to')} — subject: {a.get('subject')}",
        "create_event": lambda a: f"Created calendar event '{a.get('title')}' on {a.get('date')} {a.get('start_time')}",
        "update_event": lambda a: f"Updated calendar event {a.get('event_id')}",
        "make_call": lambda a: f"Placed call to {a.get('phone_number')} — objective: {a.get('objective')}",
    }
    summary = summaries.get(tool_name, lambda a: f"Called {tool_name} with {a}")(args)
    card_id = f"epi-{datetime.now(_TZ).strftime('%Y%m%d')}-{tool_name}-{uuid.uuid4().hex[:8]}"
    vector_memory.add_episodic(card_id, summary, {
        "type": "tool_action", "tool": tool_name,
        "date": datetime.now(_TZ).isoformat(),
    })


async def _run_tool(name: str, args: dict) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    result = await handler(args)
    content = result.get("content", [])
    return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
