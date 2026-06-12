"""Configuration loader using Pydantic + YAML."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-config models
# ---------------------------------------------------------------------------

class ApiConfig(BaseModel):
    base_url: str = "https://backend.hobbylandeshop.com"
    request_body: dict[str, Any] = Field(
        default_factory=lambda: {"category": ["model_area", "gundam_zone"]}
    )
    timeout: int = 30
    page_delay: float = 1.5


class SchedulerConfig(BaseModel):
    scan_time: str = "12:00"       # "HH:MM" format
    timezone: str = "Asia/Shanghai"


class LogNotifierConfig(BaseModel):
    enabled: bool = True


class TelegramNotifierConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


class NotifierConfig(BaseModel):
    log: LogNotifierConfig = LogNotifierConfig()
    telegram: TelegramNotifierConfig = TelegramNotifierConfig()


class AlertConfig(BaseModel):
    back_in_stock: bool = True
    price_change: bool = True
    good_deal: bool = True


class DatabaseConfig(BaseModel):
    path: str = "data/monitor.db"


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    api: ApiConfig = ApiConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    notifiers: NotifierConfig = NotifierConfig()
    alerts: AlertConfig = AlertConfig()
    database: DatabaseConfig = DatabaseConfig()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: str | Path = "config/config.yaml") -> AppConfig:
    """Load and validate the YAML config file.

    Environment variables override sensitive fields:
      - TELEGRAM_BOT_TOKEN overrides notifiers.telegram.bot_token
      - TELEGRAM_CHAT_ID  overrides notifiers.telegram.chat_id
    """
    p = Path(path)
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    # watched_skus has moved to the database (managed via the web UI).
    # Silently ignore any leftover watched_skus key in old config files.
    raw.pop("watched_skus", None)

    config = AppConfig(**raw)

    # Env var overrides for secrets
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        config.notifiers.telegram.bot_token = env_token
    env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if env_chat_id:
        config.notifiers.telegram.chat_id = env_chat_id

    return config
