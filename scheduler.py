"""
APScheduler jobs:
  1. Nightly session cleanup at 2:00 AM CT
  2. Nightly dream (memory consolidation) at 3:00 AM CT
"""

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TZ
from session_store import purge_old_sessions
from dreamer import dream

logger = logging.getLogger(__name__)
_TZ = ZoneInfo(TZ)


def nightly_cleanup():
    removed = purge_old_sessions()
    if removed:
        logger.info("Purged %d old sessions", removed)


def nightly_dream():
    """Consolidate and deduplicate the user's memory file using Claude Haiku."""
    try:
        summary = dream()
        logger.info("Dream complete: %s", summary)
    except Exception:
        logger.exception("Dreamer failed")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=_TZ)

    scheduler.add_job(
        nightly_cleanup,
        CronTrigger(hour=2, minute=0, timezone=_TZ),
        id="nightly_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        nightly_dream,
        CronTrigger(hour=3, minute=0, timezone=_TZ),
        id="nightly_dream",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started — nightly cleanup at 2 AM CT, dream at 3 AM CT")
    return scheduler
