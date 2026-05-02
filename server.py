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

    # Only accept messages from Jason's whitelisted number
    if from_number != MY_PHONE_NUMBER:
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
