"""SQLAlchemy engine and session factory."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .models import Base

logger = logging.getLogger(__name__)


def create_engine(db_path: str) -> sa.engine.Engine:
    """Create a SQLAlchemy engine for SQLite at the given path.

    Enables WAL mode for better concurrent read performance.
    Creates tables if they don't exist.
    Runs lightweight migrations for schema changes.
    """
    # Ensure the parent directory exists
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(f"sqlite:///{db_path}", echo=False)

    # Enable WAL mode for better concurrency
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=WAL"))
        conn.commit()

    # Create tables
    Base.metadata.create_all(engine)

    # Lightweight migrations for existing databases
    _run_migrations(engine)

    return engine


def _run_migrations(engine: sa.engine.Engine) -> None:
    """Run lightweight schema migrations for existing databases."""
    with engine.connect() as conn:
        # Add pic1 column if missing
        try:
            conn.execute(sa.text("ALTER TABLE products ADD COLUMN pic1 TEXT"))
            conn.commit()
            logger.info("Migration: added pic1 column to products table")
        except OperationalError:
            pass  # Column already exists

        # Add baseline_price column to watchlist if missing
        try:
            conn.execute(sa.text("ALTER TABLE watchlist ADD COLUMN baseline_price REAL"))
            conn.commit()
            logger.info("Migration: added baseline_price column to watchlist table")
        except OperationalError:
            pass

        # Migrate is_watched=1 rows into the watchlist table
        _migrate_watched_to_watchlist(conn)

        conn.commit()


def _migrate_watched_to_watchlist(conn: sa.engine.Connection) -> None:
    """One-time migration: copy is_watched=1 products into the watchlist table."""
    # Check if there are any watched products to migrate
    result = conn.execute(
        sa.text("SELECT sku, price, regular_price, stock FROM products WHERE is_watched = 1")
    )
    rows = result.fetchall()
    if not rows:
        return

    now = _now_iso()
    migrated = 0
    for row in rows:
        sku, price, regular_price, stock = row
        # Determine watch type based on current state
        watch_type = _suggest_watch_type(stock, price, regular_price)
        try:
            conn.execute(
                sa.text(
                    "INSERT OR IGNORE INTO watchlist (sku, watch_type, created_at) "
                    "VALUES (:sku, :watch_type, :created_at)"
                ),
                {"sku": sku, "watch_type": watch_type, "created_at": now},
            )
            migrated += 1
        except OperationalError:
            pass

    if migrated > 0:
        logger.info("Migration: moved %d watched products into watchlist table", migrated)


def _suggest_watch_type(stock: int, price: float, regular_price: float | None) -> str:
    """Suggest a watch type based on the product's current state."""
    if stock == 0:
        return "back_in_stock"
    if regular_price and price < regular_price:
        return "lower_price"
    return "discount"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_session(engine: sa.engine.Engine) -> Generator[Session, None, None]:
    """Context-managed session factory.

    Commits on clean exit, rolls back on exception.
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Module-level engine singleton, initialized by main.py at startup
engine: sa.engine.Engine = None  # type: ignore


def init_engine(db_path: str) -> sa.engine.Engine:
    """Initialize the module-level engine singleton."""
    global engine
    engine = create_engine(db_path)
    return engine
