"""
Bland.ai phone call tools — initiate AI calls, check status, get transcripts.
Always requires Jason's confirmation before dialing.
"""

import logging
import requests
from config import BLAND_API_KEY

logger = logging.getLogger(__name__)

_BLAND_BASE = "https://api.bland.ai/v1"
_HEADERS = {"authorization": BLAND_API_KEY, "Content-Type": "application/json"}


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


async def make_call(args: dict) -> dict:
    phone = args.get("phone_number", "")
    objective = args.get("objective", "")
    provider = args.get("provider_name", "")
    context = args.get("context", "")

    if not phone or not objective:
        return _err("phone_number and objective are required")

    task = (
        f"You are calling on behalf of Jason. "
        f"Introduce yourself as: 'Hi, I'm calling on behalf of Jason.' "
        f"Your goal: {objective}. "
    )
    if context:
        task += f"Additional context: {context}. "
    task += (
        "Be polite and professional. If you need to leave a voicemail, "
        "briefly state the purpose and ask them to call Jason back. "
        "Confirm any scheduled appointment details clearly before ending the call."
    )

    payload = {
        "phone_number": phone,
        "task": task,
        "voice": "maya",
        "wait_for_greeting": True,
        "record": True,
        "max_duration": 10,
    }

    try:
        resp = requests.post(f"{_BLAND_BASE}/calls", json=payload, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        call_id = data.get("call_id", "unknown")
        return _ok(
            f"Call initiated to {provider or phone}! Call ID: {call_id}\n"
            f"I'll report back with the outcome once the call completes. "
            f"Use check_call_status with call ID {call_id} to get results."
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
        return _ok(
            f"Call {call_id}:\n"
            f"Status: {data.get('status', 'unknown')}\n"
            f"Answered by: {data.get('answered_by', 'unknown')}\n"
            f"Duration: {data.get('call_length', 0)} seconds"
        )
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
