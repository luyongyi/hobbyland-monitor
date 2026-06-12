"""Notifier factory — instantiate notifiers from config."""

from __future__ import annotations

import logging

from ..config import AppConfig, NotifierConfig
from .base import Notifier
from .log_notifier import LogNotifier
from .telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def create_notifiers(config: AppConfig) -> list[Notifier]:
    """Read the notifiers section of config, instantiate all enabled notifiers,
    and return them as a list.
    """
    notifiers: list[Notifier] = []
    ncfg = config.notifiers

    # Log notifier — always add as fallback
    if ncfg.log.enabled:
        notifiers.append(LogNotifier())
        logger.info("Enabled notifier: LogNotifier")

    # Telegram notifier
    if ncfg.telegram.enabled:
        token = ncfg.telegram.bot_token
        chat_id = ncfg.telegram.chat_id
        if token and chat_id:
            notifiers.append(TelegramNotifier(bot_token=token, chat_id=chat_id))
            logger.info("Enabled notifier: TelegramNotifier")
        else:
            logger.warning(
                "Telegram notifier enabled but bot_token or chat_id is missing. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."
            )

    if not notifiers:
        logger.warning("No notifiers enabled! Adding LogNotifier as fallback.")
        notifiers.append(LogNotifier())

    return notifiers
