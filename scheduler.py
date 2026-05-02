"""
APScheduler jobs for proactive notifications:
  1. Morning briefing at 7:00 AM CT
  2. Urgent alert monitor every 15 minutes
  3. Nightly session cleanup
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import TZ, load_context
from tools.sms_tool import send_sms_direct
from session_store import purge_old_sessions

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_agent_for_briefing(prompt: str) -> str:
    """Run the agent synchronously for scheduler-triggered tasks."""
    from agent import run_agent
    from config import MY_PHONE_NUMBER
    return asyncio.run(run_agent(MY_PHONE_NUMBER, prompt))


# ── Jobs ──────────────────────────────────────────────────────────────────────

def morning_briefing():
    """Send Jason a morning summary: emails + school updates + calendar."""
    logger.info("Running morning briefing")
    try:
        ctx = load_context()
        today = datetime.now(_TZ).strftime("%A, %B %-d")
        prompt = (
            f"Good morning! It's {today}. Please give me a morning briefing:\n"
            "1. Summary of unread emails (subject lines + who they're from)\n"
            "2. Any school updates from My Bright Day\n"
            "3. What's on my calendar today\n"
            "Keep it concise — this is a morning text."
        )
        reply = _run_agent_for_briefing(prompt)
        send_sms_direct(f"☀️ Good morning, Jason!\n\n{reply}")
    except Exception:
        logger.exception("Morning briefing failed")


def urgent_monitor():
    """Check for urgent emails or school alerts every 15 minutes."""
    logger.info("Running urgent monitor check")
    try:
        ctx = load_context()
        keywords = ctx.get("urgent_keywords", [])
        vip_list = ctx.get("vip_senders", {}).get("list", [])

        keyword_query = " OR ".join(f'subject:"{k}"' for k in keywords[:5])
        vip_query = " OR ".join(f"from:{v}" for v in vip_list[:5])

        # Check within the last 20 minutes to avoid re-alerting
        from googleapiclient.discovery import build
        from tools._google_auth import get_google_credentials
        from datetime import timezone

        after = datetime.now(timezone.utc) - timedelta(minutes=20)
        after_str = after.strftime("%Y/%m/%d")

        svc = build("gmail", "v1", credentials=get_google_credentials())
        q_parts = []
        if keyword_query:
            q_parts.append(f"({keyword_query})")
        if vip_query:
            q_parts.append(f"({vip_query})")
        if not q_parts:
            return

        full_query = f"is:unread ({' OR '.join(q_parts)}) after:{after_str}"
        results = svc.users().messages().list(
            userId="me", q=full_query, maxResults=5
        ).execute()
        messages = results.get("messages", [])

        if not messages:
            return

        lines = []
        for m in messages:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            lines.append(
                f"• From: {headers.get('From', '?')}\n"
                f"  Subject: {headers.get('Subject', '(no subject)')}"
            )

        alert = "🚨 Urgent email alert!\n\n" + "\n\n".join(lines)
        alert += "\n\nReply to me if you need help handling these."
        send_sms_direct(alert)

    except Exception:
        logger.exception("Urgent monitor failed")


def nightly_cleanup():
    removed = purge_old_sessions()
    if removed:
        logger.info("Purged %d old sessions", removed)


# ── Scheduler setup ───────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    ctx = load_context()
    briefing_cfg = ctx.get("morning_briefing", {})
    hour = briefing_cfg.get("hour", 7)
    minute = briefing_cfg.get("minute", 0)

    scheduler = BackgroundScheduler(timezone=_TZ)

    scheduler.add_job(
        morning_briefing,
        CronTrigger(hour=hour, minute=minute, timezone=_TZ),
        id="morning_briefing",
        replace_existing=True,
    )
    scheduler.add_job(
        urgent_monitor,
        IntervalTrigger(minutes=15),
        id="urgent_monitor",
        replace_existing=True,
    )
    scheduler.add_job(
        nightly_cleanup,
        CronTrigger(hour=2, minute=0, timezone=_TZ),
        id="nightly_cleanup",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started — briefing at %02d:%02d CT, urgent monitor every 15 min", hour, minute)
    return scheduler
