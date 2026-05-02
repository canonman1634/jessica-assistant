"""
Jessica — Claude Agent SDK orchestrator.
Receives a message from Jason, runs the agent with all tools, returns a reply string.
"""

import logging
import os
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, ResultMessage, SystemMessage

from config import load_context, ANTHROPIC_API_KEY

# Ensure the API key is available to the Claude Code CLI subprocess
os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
from session_store import get_session_id, save_session_id
from tools.email_tool import build_email_server
from tools.calendar_tool import build_calendar_server
from tools.phone_tool import build_phone_server
from tools.school_tool import build_school_server
from tools.sms_tool import build_sms_server

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """
You are Jessica, a warm and friendly personal executive assistant for {owner_name}.

## Your personality
- Warm, personable, and efficient — like a trusted friend who happens to be incredibly organized
- Concise but never cold; use a natural, conversational tone
- Use first names when referring to family members
- Respond via SMS, so keep things readable: use short paragraphs or bullet points for lists

## Family context
- Owner: {owner_name} (timezone: {timezone})
- Children:
{children_list}
- Both children attend Bright Horizons daycare (My Bright Day app)

## Your capabilities
- Check, search, and send emails (Gmail)
- Check and create Google Calendar events
- Make phone calls on {owner_name}'s behalf using an AI calling service
- Check school/daycare updates from My Bright Day
- Send proactive SMS notifications

## Rules you ALWAYS follow
1. **Phone calls**: Before making any call, text {owner_name} with: who you'll call, the phone number, and what you'll say. Wait for explicit approval ("yes", "go ahead", "do it") before dialing.
2. **Emails**: Before sending any email, show {owner_name} the full draft (To, Subject, Body). Wait for approval before sending.
3. **Privacy**: Never store sensitive information beyond what's needed for the immediate task.
4. **Uncertainty**: If you're unsure about something (a phone number, a date, etc.), ask before acting.

## Tone examples
- Good: "Got it! I'll draft an email to Dr. Smith — take a look: ..."
- Good: "Graham had a great day at Bright Horizons! Here's his daily report: ..."
- Avoid: Overly formal language, unnecessary disclaimers, repeating instructions back verbatim

Today's date/time is available via the current context. {owner_name}'s timezone is {timezone}.
""".strip()


def _build_system_prompt() -> str:
    ctx = load_context()
    owner = ctx["owner"]["name"]
    tz = ctx["owner"]["timezone"]
    children = ctx.get("children", [])
    children_lines = "\n".join(
        f"  - {c['name']} (born {c['birthday']}, attends {c.get('school', 'Bright Horizons')})"
        for c in children
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(
        owner_name=owner,
        timezone=tz,
        children_list=children_lines,
    )


async def run_agent(phone: str, message: str) -> str:
    """Process an incoming SMS message and return Jessica's reply."""
    session_id = get_session_id(phone)

    mcp_servers = {
        "email": build_email_server(),
        "calendar": build_calendar_server(),
        "phone": build_phone_server(),
        "school": build_school_server(),
        "sms": build_sms_server(),
    }

    options = ClaudeAgentOptions(
        system_prompt=_build_system_prompt(),
        mcp_servers=mcp_servers,
        allowed_tools=[
            "mcp__email__search_emails",
            "mcp__email__read_email",
            "mcp__email__send_email",
            "mcp__email__list_unread",
            "mcp__calendar__check_availability",
            "mcp__calendar__list_upcoming",
            "mcp__calendar__create_event",
            "mcp__calendar__update_event",
            "mcp__phone__make_call",
            "mcp__phone__check_call_status",
            "mcp__phone__get_transcript",
            "mcp__phone__list_recent_calls",
            "mcp__school__check_school_updates",
            "mcp__school__get_daily_report",
            "mcp__sms__send_sms",
        ],
        **({"resume": session_id} if session_id else {}),
    )

    reply_parts = []
    new_session_id = session_id

    async for event in query(prompt=message, options=options):
        if isinstance(event, SystemMessage) and event.subtype == "init":
            new_session_id = event.data.get("session_id", session_id)
        elif isinstance(event, AssistantMessage):
            for block in event.content:
                if hasattr(block, "text") and block.text:
                    reply_parts.append(block.text)
        elif isinstance(event, ResultMessage):
            if event.subtype == "success" and event.result:
                # Use the final result if we didn't collect assistant text
                if not reply_parts:
                    reply_parts.append(event.result)

    if new_session_id:
        save_session_id(phone, new_session_id)

    return "\n".join(reply_parts).strip() or "Done!"
