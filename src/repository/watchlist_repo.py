"""Data access layer for the watchlist table."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import Product, WatchlistItem

logger = logging.getLogger(__name__)


class WatchlistRepository:
    """CRUD operations for the watchlist."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_all(self) -> list[WatchlistItem]:
        stmt = select(WatchlistItem).order_by(WatchlistItem.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def get_by_type(self, watch_type: str) -> list[WatchlistItem]:
        stmt = (
            select(WatchlistItem)
            .where(WatchlistItem.watch_type == watch_type)
            .order_by(WatchlistItem.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_watch_types_for_sku(self, sku: str) -> list[str]:
        stmt = select(WatchlistItem.watch_type).where(WatchlistItem.sku == sku)
        return list(self.session.execute(stmt).scalars().all())

    def get_watched_skus(self) -> set[str]:
        stmt = select(WatchlistItem.sku).distinct()
        return set(self.session.execute(stmt).scalars().all())

    def add_watch(self, sku: str, watch_type: str) -> WatchlistItem:
        """Add a watch entry. Raises ValueError if SKU not found in products."""
        # Verify the product exists
        product = self.session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        if product is None:
            raise ValueError(f"Product with SKU {sku} not found")

        # Snapshot the current price as the baseline for this watch.
        # For lower_price watches, this is the price the user is hoping to drop below.
        item = WatchlistItem(
            sku=sku,
            watch_type=watch_type,
            baseline_price=product.price,
            created_at=_now_iso(),
        )
        self.session.add(item)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise ValueError(f"Already watching {sku} with type {watch_type}")

        # Also update the is_watched flag on the product
        product.is_watched = 1

        return item

    def remove_watch(self, sku: str, watch_type: str) -> bool:
        """Remove a watch entry. Returns True if removed, False if not found."""
        stmt = (
            select(WatchlistItem)
            .where(WatchlistItem.sku == sku, WatchlistItem.watch_type == watch_type)
        )
        item = self.session.execute(stmt).scalar_one_or_none()
        if item is None:
            return False

        self.session.delete(item)
        self.session.flush()

        # Check if this SKU still has other watch entries
        remaining = self.get_watch_types_for_sku(sku)
        if not remaining:
            # No more watches, update is_watched flag
            product = self.session.execute(
                select(Product).where(Product.sku == sku)
            ).scalar_one_or_none()
            if product:
                product.is_watched = 0

        return True

    def suggest_watch_type(self, sku: str) -> str:
        """Suggest a watch type for a product based on its current state.

        Logic:
          - stock == 0 → "back_in_stock"
          - stock > 0 and price < regular_price → "lower_price"
          - stock > 0 and price >= regular_price → "discount"
        """
        product = self.session.execute(
            select(Product).where(Product.sku == sku)
        ).scalar_one_or_none()
        if product is None:
            raise ValueError(f"Product with SKU {sku} not found")

        if product.stock == 0:
            return "back_in_stock"
        if product.regular_price and product.price < product.regular_price:
            return "lower_price"
        return "discount"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
