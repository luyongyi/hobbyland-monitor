"""Telegram Bot notifier."""

from __future__ import annotations

import logging

import requests

from .base import Alert, Notifier

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_MESSAGE_LEN = 4096  # Telegram limit per message


class TelegramNotifier(Notifier):
    """Sends alerts to a Telegram chat via Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._api_url = _TELEGRAM_API.format(token=bot_token)

    def send(self, alert: Alert) -> None:
        text = self._format_alert(alert)
        self._post(text)

    def send_batch(self, alerts: list[Alert]) -> None:
        """Group alerts into a single message to avoid spam."""
        if not alerts:
            return

        parts: list[str] = []
        current = "📦 <b>Hobbyland 库存监控报告</b>\n\n"

        for alert in alerts:
            block = self._format_alert(alert)
            if len(current) + len(block) + 1 > _MAX_MESSAGE_LEN:
                parts.append(current)
                current = block + "\n"
            else:
                current += block + "\n"

        parts.append(current)

        for part in parts:
            self._post(part)

    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(alert: Alert) -> str:
        """Format a single alert as HTML for Telegram."""
        if alert.alert_type == "back_in_stock":
            return (
                f"{alert.emoji} <b>{alert.label}</b>\n"
                f"  {alert.title}\n"
                f"  库存: {alert.old_value} → {alert.new_value}\n"
                f"  🔗 <a href=\"https://www.hobbylandeshop.com{alert.extra.get('link', '')}\">查看商品</a>"
            )
        elif alert.alert_type == "price_change":
            arrow = "↓" if float(alert.new_value) < float(alert.old_value or 0) else "↑"
            return (
                f"{alert.emoji} <b>{alert.label}</b>\n"
                f"  {alert.title}\n"
                f"  价格: ${alert.old_value} {arrow} ${alert.new_value}\n"
                f"  🔗 <a href=\"https://www.hobbylandeshop.com{alert.extra.get('link', '')}\">查看商品</a>"
            )
        elif alert.alert_type == "good_deal":
            regular = alert.extra.get("regular_price", "?")
            saving = ""
            try:
                reg = float(regular)
                cur = float(alert.new_value)
                pct = (1 - cur / reg) * 100
                saving = f" (省 {pct:.0f}%)"
            except (ValueError, ZeroDivisionError):
                pass
            return (
                f"{alert.emoji} <b>{alert.label}</b>\n"
                f"  {alert.title}\n"
                f"  现价 ${alert.new_value} &lt; 原价 ${regular}{saving}\n"
                f"  🔗 <a href=\"https://www.hobbylandeshop.com{alert.extra.get('link', '')}\">查看商品</a>"
            )
        else:
            return f"{alert.emoji} <b>{alert.label}</b>: {alert.title}"

    def _post(self, html: str) -> None:
        """Send an HTML message to Telegram."""
        try:
            resp = requests.post(
                self._api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": html,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Telegram API returned %d: %s", resp.status_code, resp.text[:200]
                )
        except requests.RequestException as e:
            logger.error("Failed to send Telegram notification: %s", e)
