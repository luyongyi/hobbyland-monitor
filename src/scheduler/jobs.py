"""APScheduler setup for the daily scan job."""

from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import SchedulerConfig

logger = logging.getLogger(__name__)


def create_scheduler(
    scan_fn: Callable[[], None],
    config: SchedulerConfig,
) -> BackgroundScheduler:
    """Create and configure the APScheduler instance.

    Uses BackgroundScheduler so it coexists with FastAPI.

    Args:
        scan_fn: The function to call on each scheduled run.
        config: Scheduler configuration (scan_time, timezone).

    Returns:
        A configured (but not yet started) BackgroundScheduler.
    """
    scheduler = BackgroundScheduler(timezone=config.timezone)

    # Parse "HH:MM" from config
    parts = config.scan_time.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0

    scheduler.add_job(
        func=scan_fn,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_scan",
        name="Daily product scan",
        max_instances=1,          # Prevent overlapping runs
        misfire_grace_time=3600,  # If container was down, run within 1 hour
    )

    logger.info(
        "Scheduled daily scan at %02d:%02d (%s)",
        hour, minute, config.timezone,
    )

    return scheduler
