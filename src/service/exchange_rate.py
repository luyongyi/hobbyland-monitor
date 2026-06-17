"""Exchange rate service.

Fetches JPY -> HKD exchange rate hourly and stores it in SQLite. The UI uses
this only as a reference conversion for Bandai official JP¥ MSRP.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import ExchangeRate

logger = logging.getLogger(__name__)

_RATE_URL = "https://open.er-api.com/v6/latest/JPY"


class ExchangeRateService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_jpy_hkd(self) -> ExchangeRate | None:
        stmt = (
            select(ExchangeRate)
            .where(
                ExchangeRate.base_currency == "JPY",
                ExchangeRate.target_currency == "HKD",
            )
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def refresh_jpy_hkd_if_stale(self, max_age_minutes: int = 60) -> ExchangeRate | None:
        """Fetch JPY->HKD rate if missing or older than max_age_minutes."""
        latest = self.get_latest_jpy_hkd()
        if latest and latest.fetched_at:
            try:
                fetched_at = datetime.fromisoformat(latest.fetched_at)
                if datetime.now(timezone.utc) - fetched_at < timedelta(minutes=max_age_minutes):
                    return latest
            except ValueError:
                pass

        return self.fetch_jpy_hkd()

    def fetch_jpy_hkd(self) -> ExchangeRate | None:
        """Fetch and persist current JPY->HKD exchange rate."""
        try:
            resp = requests.get(_RATE_URL, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            rate = float(data["rates"]["HKD"])
        except Exception as e:
            logger.warning("Failed to fetch JPY->HKD exchange rate: %s", e)
            return self.get_latest_jpy_hkd()

        record = ExchangeRate(
            base_currency="JPY",
            target_currency="HKD",
            rate=rate,
            source="open.er-api.com",
            fetched_at=_now_iso(),
        )
        self.session.add(record)
        self.session.flush()
        logger.info("Fetched exchange rate: 1 JPY = %.6f HKD", rate)
        return record


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
