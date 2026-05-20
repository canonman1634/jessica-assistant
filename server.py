"""
Flask webhook server — receives Twilio SMS, dispatches to Jessica agent, replies.
"""

import asyncio
import logging
from flask import Flask, request, Response, redirect
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
from config import (
    FLASK_SECRET_KEY,
    TWILIO_AUTH_TOKEN,
    TWILIO_ACCOUNT_SID,
    TWILIO_PHONE_NUMBER,
    MY_PHONE_NUMBER,
    APP_URL,
)
from agent import run_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Start background scheduler (morning briefing + urgent monitor)
from scheduler import start_scheduler
_scheduler = start_scheduler()

# In-memory state store for OAuth flows (short-lived, single-process)
_pending_oauth_states: dict[str, str] = {}  # state -> "pending"


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


@app.route("/auth", methods=["GET"])
def auth_start():
    """Redirect to Google's OAuth consent page."""
    from tools._google_auth import get_auth_url
    if not APP_URL:
        return Response("APP_URL environment variable is not set.", status=500)
    redirect_uri = f"{APP_URL}/auth/callback"
    auth_url, state = get_auth_url(redirect_uri)
    _pending_oauth_states[state] = "pending"
    return redirect(auth_url)


@app.route("/auth/callback", methods=["GET"])
def auth_callback():
    """Handle Google OAuth redirect, save the new token, notify the user."""
    from tools._google_auth import exchange_code
    code = request.args.get("code")
    state = request.args.get("state", "")
    error = request.args.get("error")

    if error:
        logger.warning("OAuth error: %s", error)
        return Response(f"Authorization failed: {error}", status=400)

    if state not in _pending_oauth_states:
        return Response("Invalid or expired state parameter.", status=400)

    _pending_oauth_states.pop(state, None)

    if not APP_URL:
        return Response("APP_URL environment variable is not set.", status=500)

    try:
        redirect_uri = f"{APP_URL}/auth/callback"
        exchange_code(code, redirect_uri)
        logger.info("Google account successfully reauthorized")
        _notify_owner("✅ Google account reconnected! I can access your email and calendar again.")
        return Response(
            "<html><body><h2>✅ Success!</h2><p>Jessica is reconnected to your Google account. "
            "You can close this tab.</p></body></html>",
            mimetype="text/html",
        )
    except Exception as e:
        logger.exception("OAuth token exchange failed: %s", e)
        return Response(f"Failed to save credentials: {e}", status=500)


def _notify_owner(message: str):
    """Send a WhatsApp message to the owner's number."""
    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        to = f"whatsapp:{MY_PHONE_NUMBER}" if not MY_PHONE_NUMBER.startswith("whatsapp:") else MY_PHONE_NUMBER
        frm = f"whatsapp:{TWILIO_PHONE_NUMBER}" if not TWILIO_PHONE_NUMBER.startswith("whatsapp:") else TWILIO_PHONE_NUMBER
        client.messages.create(body=message, from_=frm, to=to)
    except Exception as e:
        logger.warning("Failed to send owner notification: %s", e)


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
