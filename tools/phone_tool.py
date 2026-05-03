"""
Bland.ai phone call tools — initiate AI calls, check status, get transcripts.
Always requires Jason's confirmation before dialing.
"""

import logging
import requests
from config import BLAND_API_KEY, BASE_URL, load_context

logger = logging.getLogger(__name__)

_BLAND_BASE = "https://api.bland.ai/v1"
_HEADERS = {"authorization": BLAND_API_KEY, "Content-Type": "application/json"}

# Structured extraction from every completed call
_ANALYSIS_SCHEMA = {
    "outcome": "One of: appointment_scheduled, appointment_cancelled, voicemail_left, information_gathered, callback_requested, no_answer, other",
    "appointment_date": "ISO date (YYYY-MM-DD) if an appointment was scheduled or confirmed, otherwise null",
    "appointment_time": "Time string (e.g. '2:30 PM') if an appointment was scheduled, otherwise null",
    "notes": "Key information gathered, next steps, or anything Jason should know",
    "follow_up_needed": "true or false — whether Jason needs to take further action",
}


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _build_task(objective: str, context: str, owner: str, children: list) -> str:
    obj_lower = objective.lower()

    if any(w in obj_lower for w in ("schedule", "appointment", "book", "reserve")):
        scenario_guidance = (
            "When someone answers, confirm you have the right office, then ask to schedule an appointment. "
            "Ask for available dates and times. Before hanging up, repeat the confirmed date, time, address, "
            "and any prep instructions back to them clearly."
        )
        voicemail = (
            f"If you reach voicemail, say: 'Hi, this is a message for the team — I'm calling on behalf of "
            f"{owner} and would love to schedule an appointment. Could someone call back at their convenience? "
            f"Thank you so much, have a great day.'"
        )
    elif any(w in obj_lower for w in ("cancel", "reschedule", "move", "change")):
        scenario_guidance = (
            "When someone answers, politely explain you need to cancel or reschedule. Provide any reference "
            "details you have, confirm the cancellation or new time explicitly, and thank them."
        )
        voicemail = (
            f"If you reach voicemail, say: 'Hi, I'm calling on behalf of {owner} regarding an upcoming "
            f"appointment — we need to cancel or reschedule. Please call back when you get a chance, "
            f"thank you so much.'"
        )
    elif any(w in obj_lower for w in ("confirm", "check", "verify", "reminder")):
        scenario_guidance = (
            "When someone answers, confirm the specific details you need. Repeat them back to verify accuracy "
            "and thank them warmly before ending the call."
        )
        voicemail = (
            f"If you reach voicemail, leave a brief message for {owner} — state what you were trying to "
            f"confirm and ask them to call back. Keep it short and friendly."
        )
    else:
        scenario_guidance = (
            "Be conversational and direct. Ask your questions clearly, listen carefully, and confirm any "
            "important details before ending the call."
        )
        voicemail = (
            f"If you reach voicemail, leave a brief friendly message on behalf of {owner} — state the "
            f"purpose of the call and ask them to call back at their convenience."
        )

    children_context = ""
    if children and any(w in obj_lower for w in ("child", "kid", "school", "daycare", "pediatr", "doctor", "appoint")):
        names = " and ".join(c["name"] for c in children)
        children_context = f"The children's names are {names}. Use their names naturally if relevant. "

    task = (
        f"You are Jessica, a personal assistant calling on behalf of {owner}. "
        f"You are warm, polite, and professional — like a real human assistant, not a robot. "
        f"Your goal: {objective}. "
    )
    if children_context:
        task += children_context
    if context:
        task += f"Additional context: {context}. "
    task += (
        f"{scenario_guidance} "
        f"{voicemail} "
        "Keep the conversation natural and concise — adapt to what the other person says rather than "
        "reading from a script. If they seem confused or ask you to call back, be gracious and end politely."
    )
    return task


async def make_call(args: dict) -> dict:
    phone = args.get("phone_number", "")
    objective = args.get("objective", "")
    provider = args.get("provider_name", "")
    context = args.get("context", "")

    if not phone or not objective:
        return _err("phone_number and objective are required")

    ctx = load_context()
    owner = ctx["owner"]["name"]
    children = ctx.get("children", [])

    task = _build_task(objective, context, owner, children)

    payload = {
        "phone_number": phone,
        "task": task,
        "first_sentence": f"Hi, my name is Jessica — I'm calling on behalf of {owner}.",
        "voice": "maya",
        "model": "enhanced",
        "wait_for_greeting": True,
        "record": True,
        "max_duration": 10,
        "interruption_threshold": 75,
        "analysis_schema": _ANALYSIS_SCHEMA,
    }

    if BASE_URL:
        payload["webhook"] = f"{BASE_URL}/bland-webhook"

    try:
        resp = requests.post(f"{_BLAND_BASE}/calls", json=payload, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        call_id = data.get("call_id", "unknown")
        notify = (
            " I'll automatically send you a summary when it's done."
            if BASE_URL else
            f" Use check_call_status with call ID {call_id} to get results."
        )
        return _ok(
            f"Call initiated to {provider or phone}! Call ID: {call_id}\n{notify}"
        )
    except requests.HTTPError as e:
        logger.exception("make_call HTTP error")
        return _err(f"Failed to initiate call: {e.response.text}")
    except Exception as e:
        logger.exception("make_call failed")
        return _err(f"Failed to initiate call: {e}")


async def check_call_status(args: dict) -> dict:
    call_id = args.get("call_id", "")
    if not call_id:
        return _err("call_id is required")
    try:
        resp = requests.get(f"{_BLAND_BASE}/calls/{call_id}", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        lines = [
            f"Call {call_id}:",
            f"Status: {data.get('status', 'unknown')}",
            f"Answered by: {data.get('answered_by', 'unknown')}",
            f"Duration: {data.get('call_length', 0)} seconds",
        ]

        analysis = data.get("analysis")
        if analysis:
            lines.append("\nCall summary:")
            outcome = analysis.get("outcome", "")
            if outcome:
                lines.append(f"  Outcome: {outcome.replace('_', ' ').title()}")
            appt_date = analysis.get("appointment_date")
            appt_time = analysis.get("appointment_time")
            if appt_date:
                lines.append(f"  Appointment: {appt_date}{' at ' + appt_time if appt_time else ''}")
            notes = analysis.get("notes")
            if notes:
                lines.append(f"  Notes: {notes}")
            if str(analysis.get("follow_up_needed", "")).lower() == "true":
                lines.append("  Follow-up needed")

        return _ok("\n".join(lines))
    except Exception as e:
        logger.exception("check_call_status failed")
        return _err(f"Failed to get call status: {e}")


async def get_transcript(args: dict) -> dict:
    call_id = args.get("call_id", "")
    if not call_id:
        return _err("call_id is required")
    try:
        resp = requests.get(f"{_BLAND_BASE}/calls/{call_id}/correct", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        transcript = data.get("transcript", "")
        if not transcript:
            call_resp = requests.get(f"{_BLAND_BASE}/calls/{call_id}", headers=_HEADERS, timeout=15)
            turns = call_resp.json().get("transcripts", [])
            transcript = "\n".join(f"{t.get('user', 'Unknown')}: {t.get('text', '')}" for t in turns)
        return _ok(f"Transcript for call {call_id}:\n\n{transcript[:3000]}")
    except Exception as e:
        logger.exception("get_transcript failed")
        return _err(f"Failed to get transcript: {e}")


async def list_recent_calls(args: dict) -> dict:
    limit = min(int(args.get("limit", 5)), 10)
    try:
        resp = requests.get(f"{_BLAND_BASE}/calls", headers=_HEADERS, params={"limit": limit}, timeout=15)
        resp.raise_for_status()
        calls = resp.json().get("calls", [])
        if not calls:
            return _ok("No recent calls found.")
        lines = [
            f"• ID: {c.get('call_id')} | Status: {c.get('status')} | "
            f"To: {c.get('to')} | Duration: {c.get('call_length', 0)}s"
            for c in calls
        ]
        return _ok("Recent calls:\n" + "\n".join(lines))
    except Exception as e:
        logger.exception("list_recent_calls failed")
        return _err(f"Failed to list calls: {e}")
