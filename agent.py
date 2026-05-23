"""
Jessica — Anthropic SDK orchestrator.
Receives a message from Jason, runs the agent with all tools, returns a reply string.
"""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

from config import load_context, ANTHROPIC_API_KEY, TZ
from session_store import get_session_id, save_session_id
from tools.email_tool import list_unread, search_emails, read_email, send_email
from tools.calendar_tool import list_upcoming, check_availability, create_event, update_event
from tools.phone_tool import make_call, check_call_status, get_transcript, list_recent_calls
from tools.school_tool import check_school_updates, get_daily_report
from tools.sms_tool import send_sms

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_TZ = ZoneInfo(TZ)

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
    "send_sms": send_sms,
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
    {"name": "send_sms", "description": "Send a proactive WhatsApp/SMS notification to Jason. Use for urgent alerts or follow-ups.", "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
]

# ── Conversation history (in-memory, keyed by phone number) ───────────────────
_conversations: dict[str, list] = {}


def _build_sports_context(sports: dict) -> str:
    teams = sports.get("teams", [])
    if not teams:
        return ""
    lines = ["\n## Sports & venues"]
    for team in teams:
        notes = team.get("seating_notes", {})
        lines.append(f"- {team['name']} ({team['league']}) play at {team['venue']}, {team['venue_city']}")
        if notes.get("family_recommendation"):
            lines.append(f"  Family seating: {notes['family_recommendation']}")
        if notes.get("venue_notes"):
            lines.append(f"  Venue notes: {notes['venue_notes']}")
    return "\n".join(lines) + "\n"


def _build_system_prompt() -> str:
    ctx = load_context()
    owner = ctx["owner"]["name"]
    tz = ctx["owner"]["timezone"]
    children = ctx.get("children", [])
    now = datetime.now(_TZ).strftime("%A, %B %-d, %Y at %-I:%M %p CT")
    children_lines = "\n".join(
        f"  - {c['name']} (born {c['birthday']}, attends {c.get('school', 'Bright Horizons')})"
        for c in children
    )
    sports_lines = _build_sports_context(ctx.get("sports", {}))
    return f"""You are Jessica, a warm and friendly personal executive assistant for {owner}.

## Your personality
- Warm, personable, and efficient — like a trusted friend who happens to be incredibly organized
- Concise but never cold; use a natural, conversational tone
- Use first names when referring to family members
- Respond via WhatsApp, so keep things readable: use short paragraphs or bullet points for lists

## Family context
- Owner: {owner} (timezone: {tz})
- Current time: {now}
- Children:
{children_lines}
- Both children attend Bright Horizons daycare (My Bright Day app)
{sports_lines}
## Your capabilities
- Check, search, and send emails (Gmail)
- Check and create Google Calendar events
- Make phone calls on {owner}'s behalf using an AI calling service
- Check school/daycare updates from My Bright Day
- Send proactive WhatsApp notifications

## Rules you ALWAYS follow
1. **Phone calls**: Before making any call, tell {owner}: who you'll call, the number, and what you'll say. Wait for explicit approval ("yes", "go ahead", "do it") before using make_call.
2. **Emails**: Before sending any email, show {owner} the full draft (To, Subject, Body). Wait for approval before using send_email.
3. **Privacy**: Never store sensitive information beyond what's needed for the immediate task.
4. **Uncertainty**: If unsure about a phone number, date, or detail — ask before acting."""


async def _run_tool(name: str, args: dict) -> str:
    handler = _TOOL_HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    result = await handler(args)
    content = result.get("content", [])
    return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


def _sanitize_history(history: list) -> list:
    """Remove any tool_use/tool_result pairs that are incomplete or unmatched."""
    clean = []
    for msg in history:
        content = msg.get("content", "")
        # Skip assistant messages that contain tool_use blocks without following tool_results
        if msg["role"] == "assistant" and isinstance(content, list):
            has_tool_use = any(
                getattr(b, "type", None) == "tool_use" or (isinstance(b, dict) and b.get("type") == "tool_use")
                for b in content
            )
            if has_tool_use:
                # Only keep if the next message is a tool_result
                idx = history.index(msg)
                if idx + 1 >= len(history):
                    continue  # Drop dangling tool_use at end of history
                next_msg = history[idx + 1]
                next_content = next_msg.get("content", [])
                if not isinstance(next_content, list) or not any(
                    (isinstance(b, dict) and b.get("type") == "tool_result") for b in next_content
                ):
                    continue  # Drop unmatched tool_use
        # Skip orphaned tool_result messages
        if msg["role"] == "user" and isinstance(content, list) and content and (
            isinstance(content[0], dict) and content[0].get("type") == "tool_result"
        ):
            idx = history.index(msg)
            if idx == 0:
                continue
            prev_msg = history[idx - 1]
            prev_content = prev_msg.get("content", [])
            if not isinstance(prev_content, list) or not any(
                getattr(b, "type", None) == "tool_use" or (isinstance(b, dict) and b.get("type") == "tool_use")
                for b in prev_content
            ):
                continue
        clean.append(msg)
    return clean


async def run_agent(phone: str, message: str) -> str:
    """Process an incoming WhatsApp message and return Jessica's reply."""
    if phone not in _conversations:
        _conversations[phone] = []

    # Sanitize history before appending new message
    _conversations[phone] = _sanitize_history(_conversations[phone])
    _conversations[phone].append({"role": "user", "content": message})

    # Keep last 20 messages to avoid context blowout
    history = _conversations[phone][-20:]

    max_iterations = 10
    for _ in range(max_iterations):
        try:
            response = _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=_build_system_prompt(),
                tools=_TOOLS,
                messages=history,
            )
        except Exception as e:
            # If API rejects the history, clear it and retry with just the current message
            logger.warning("API error with history, resetting conversation: %s", e)
            _conversations[phone] = []
            history = [{"role": "user", "content": message}]
            response = _client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=_build_system_prompt(),
                tools=_TOOLS,
                messages=history,
            )

        # Add assistant response to history
        assistant_content = response.content
        history.append({"role": "assistant", "content": assistant_content})
        logger.info("Stop reason: %s", response.stop_reason)

        if response.stop_reason == "end_turn":
            reply = "\n".join(
                block.text for block in assistant_content
                if hasattr(block, "text")
            ).strip()
            _conversations[phone] = history
            return reply or "Done!"

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    logger.info("Calling tool: %s with %s", block.name, block.input)
                    result_text = await _run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

            history.append({"role": "user", "content": tool_results})
            continue

        break

    _conversations[phone] = history
    return "Sorry, I ran into an issue. Please try again!"
