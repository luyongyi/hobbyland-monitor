"""Abstract Notifier interface and Alert data class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Alert:
    """Structured alert object passed to notifiers."""

    alert_type: str  # "back_in_stock", "price_change", "good_deal"
    sku: str
    title: str
    old_value: str | None = None  # e.g. "0" for stock, "358.00" for price
    new_value: str = ""           # e.g. "3" for stock, "298.00" for price
    extra: dict = field(default_factory=dict)  # e.g. {"regular_price": "358.00"}

    @property
    def emoji(self) -> str:
        """Convenient emoji prefix per alert type."""
        return {
            "back_in_stock": "🟢",
            "price_change": "💰",
            "good_deal": "🔥",
        }.get(self.alert_type, "📢")

    @property
    def label(self) -> str:
        """Human-readable label for the alert type (Chinese)."""
        return {
            "back_in_stock": "到货提醒",
            "price_change": "价格变动",
            "good_deal": "好价提醒",
        }.get(self.alert_type, self.alert_type)


class Notifier(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    def send(self, alert: Alert) -> None:
        """Send a single alert. Must not raise exceptions in production
        (log errors internally instead)."""
        ...

    def send_batch(self, alerts: list[Alert]) -> None:
        """Send multiple alerts. Default: call send() in a loop.
        Override for batch-optimized channels (e.g. single Telegram message)."""
        for alert in alerts:
            self.send(alert)
