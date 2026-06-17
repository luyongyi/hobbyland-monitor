"""APScheduler setup for recurring jobs."""

from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import SchedulerConfig

logger = logging.getLogger(__name__)


def create_scheduler(
    scan_fn: Callable[[], None],
    config: SchedulerConfig,
    exchange_rate_fn: Callable[[], None] | None = None,
) -> BackgroundScheduler:
    """Create and configure the APScheduler instance.

    Uses BackgroundScheduler so it coexists with FastAPI.
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
        max_instances=1,
        misfire_grace_time=3600,
    )

    logger.info("Scheduled daily scan at %02d:%02d (%s)", hour, minute, config.timezone)

    if exchange_rate_fn is not None:
        scheduler.add_job(
            func=exchange_rate_fn,
            trigger=IntervalTrigger(hours=1),
            id="hourly_exchange_rate",
            name="Hourly JPY/HKD exchange rate refresh",
            max_instances=1,
            misfire_grace_time=600,
        )
        logger.info("Scheduled hourly JPY/HKD exchange rate refresh")

    return scheduler
