"""Log-based notifier — always-on fallback that writes to structured logs."""

from __future__ import annotations

import json
import logging

from .base import Alert, Notifier

logger = logging.getLogger(__name__)


class LogNotifier(Notifier):
    """Writes alerts as structured log lines. Always safe, never fails."""

    def send(self, alert: Alert) -> None:
        payload = {
            "alert_type": alert.alert_type,
            "sku": alert.sku,
            "title": alert.title,
            "old_value": alert.old_value,
            "new_value": alert.new_value,
            "extra": alert.extra,
        }
        logger.info("ALERT %s %s: %s → %s | %s",
                     alert.emoji, alert.label,
                     alert.old_value, alert.new_value,
                     alert.title)
        logger.debug("Alert payload: %s", json.dumps(payload, ensure_ascii=False))
