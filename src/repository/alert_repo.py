"""Data access layer for the alerts table."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import AlertRecord
from ..notifier.base import Alert

logger = logging.getLogger(__name__)


class AlertRepository:
    """CRUD operations for alert records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_alert(self, alert: Alert) -> AlertRecord:
        """Persist an Alert dataclass as an AlertRecord row."""
        record = AlertRecord(
            alert_type=alert.alert_type,
            sku=alert.sku,
            title=alert.title,
            old_value=alert.old_value,
            new_value=alert.new_value,
            extra=json.dumps(alert.extra, ensure_ascii=False),
            created_at=_now_iso(),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def save_alerts(self, alerts: list[Alert]) -> list[AlertRecord]:
        """Persist multiple alerts."""
        return [self.save_alert(a) for a in alerts]

    def get_alerts(
        self,
        page: int = 1,
        page_size: int = 20,
        alert_type: str = "",
        sku: str = "",
    ) -> tuple[list[AlertRecord], int]:
        """Get paginated alert history.

        Returns (records, total_count).
        """
        stmt = select(AlertRecord)
        count_stmt = select(func.count(AlertRecord.id))

        if alert_type:
            stmt = stmt.where(AlertRecord.alert_type == alert_type)
            count_stmt = count_stmt.where(AlertRecord.alert_type == alert_type)

        if sku:
            stmt = stmt.where(AlertRecord.sku == sku)
            count_stmt = count_stmt.where(AlertRecord.sku == sku)

        total = self.session.execute(count_stmt).scalar_one()

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AlertRecord.created_at.desc()).offset(offset).limit(page_size)
        records = list(self.session.execute(stmt).scalars().all())

        return records, total

    def get_latest_alert_time(self) -> str | None:
        """Return the created_at of the most recent alert, or None."""
        stmt = select(AlertRecord.created_at).order_by(AlertRecord.created_at.desc()).limit(1)
        result = self.session.execute(stmt).scalar_one_or_none()
        return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
