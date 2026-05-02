"""
Twilio outbound WhatsApp tool — used by the scheduler for proactive notifications.
"""

import logging
from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, MY_PHONE_NUMBER

logger = logging.getLogger(__name__)


def send_sms_direct(message: str, to: str = MY_PHONE_NUMBER) -> None:
    """Send a WhatsApp message directly (used by scheduler, not via agent tool)."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message[:1600],
        from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
        to=f"whatsapp:{to}",
    )
    logger.info("Sent proactive WhatsApp message to %s", to)


async def send_sms(args: dict) -> dict:
    message = args.get("message", "")
    if not message:
        return {"content": [{"type": "text", "text": "message is required"}], "is_error": True}
    try:
        send_sms_direct(message)
        return {"content": [{"type": "text", "text": f"Message sent: {message[:80]}..."}]}
    except Exception as e:
        logger.exception("send_sms failed")
        return {"content": [{"type": "text", "text": f"Failed to send message: {e}"}], "is_error": True}
