"""
Flask webhook server — receives Twilio SMS, dispatches to Jessica agent, replies.
"""

import asyncio
import logging
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from config import (
    FLASK_SECRET_KEY,
    TWILIO_AUTH_TOKEN,
    MY_PHONE_NUMBER,
)
from agent import run_agent
from tools.sms_tool import send_sms

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Start background scheduler (morning briefing + urgent monitor)
from scheduler import start_scheduler
_scheduler = start_scheduler()


def _validate_twilio(req) -> bool:
    """Reject requests that don't have a valid Twilio signature."""
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    signature = req.headers.get("X-Twilio-Signature", "")
    params = req.form.to_dict()
    # Railway sits behind a proxy — use the forwarded URL if available
    forwarded_proto = req.headers.get("X-Forwarded-Proto", req.scheme)
    forwarded_host = req.headers.get("X-Forwarded-Host", req.host)
    url = f"{forwarded_proto}://{forwarded_host}{req.path}"
    return validator.validate(url, params, signature)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


@app.route("/sms", methods=["POST"])
def sms():
    # Validate the request came from Twilio
    if not _validate_twilio(request):
        logger.warning("Rejected request with invalid Twilio signature")
        return Response("Forbidden", status=403)

    from_number = request.form.get("From", "")
    body = request.form.get("Body", "").strip()

    # Strip WhatsApp prefix if present (e.g. "whatsapp:+17732702667" -> "+17732702667")
    normalized_from = from_number.replace("whatsapp:", "")

    # Only accept messages from Jason's whitelisted number
    if normalized_from != MY_PHONE_NUMBER:
        logger.warning("Rejected message from non-whitelisted number: %s", from_number)
        return Response(str(MessagingResponse()), mimetype="text/xml")

    if not body:
        return Response(str(MessagingResponse()), mimetype="text/xml")

    logger.info("Incoming SMS from %s: %s", from_number, body[:80])

    try:
        reply = asyncio.run(run_agent(from_number, body))
    except Exception as e:
        logger.exception("Agent error: %s", e)
        reply = "Sorry, something went wrong on my end. Try again in a moment!"

    resp = MessagingResponse()
    # Twilio supports up to 1600 chars per message segment; split on newlines if huge
    resp.message(reply[:1600])
    return Response(str(resp), mimetype="text/xml")


@app.route("/bland-webhook", methods=["POST"])
def bland_webhook():
    """Receive Bland.ai call completion events and forward a summary to Jason via WhatsApp."""
    data = request.get_json(silent=True) or {}
    call_id = data.get("call_id", "unknown")
    status = data.get("status", "unknown")
    answered_by = data.get("answered_by", "unknown")
    duration = data.get("call_length", 0)
    analysis = data.get("analysis") or {}

    lines = [
        f"Call completed (ID: {call_id})",
        f"Status: {status} | Answered by: {answered_by} | Duration: {duration}s",
    ]

    outcome = analysis.get("outcome", "")
    if outcome:
        lines.append(f"Outcome: {outcome.replace('_', ' ').title()}")
    appt_date = analysis.get("appointment_date")
    appt_time = analysis.get("appointment_time")
    if appt_date:
        lines.append(f"Appointment: {appt_date}{' at ' + appt_time if appt_time else ''}")
    notes = analysis.get("notes")
    if notes:
        lines.append(f"Notes: {notes}")
    if str(analysis.get("follow_up_needed", "")).lower() == "true":
        lines.append("Action needed: follow-up required")

    try:
        asyncio.run(send_sms({"message": "\n".join(lines)}))
    except Exception:
        logger.exception("Failed to send bland webhook notification")

    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
