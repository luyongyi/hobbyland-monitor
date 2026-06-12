"""Data access layer: upsert products, record price/stock history, detect changes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import PriceHistory, Product, StockHistory, WatchlistItem

logger = logging.getLogger(__name__)


@dataclass
class UpsertResult:
    """Returned by upsert_product to signal what changed."""

    product: Product
    is_new: bool
    price_changed: bool
    stock_changed: bool
    old_price: float | None = None
    old_stock: int | None = None


class ProductRepository:
    """Data access layer for product CRUD and change detection."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_sku(self, sku: str) -> Product | None:
        stmt = select(Product).where(Product.sku == sku)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_watched_skus(self) -> set[str]:
        """Get all SKUs that have at least one watchlist entry."""
        stmt = select(WatchlistItem.sku).distinct()
        rows = self.session.execute(stmt).scalars().all()
        return set(rows)

    def get_all_watched_products(self) -> list[Product]:
        """Get all products that have at least one watchlist entry."""
        stmt = (
            select(Product)
            .join(WatchlistItem, Product.sku == WatchlistItem.sku)
            .distinct()
        )
        return list(self.session.execute(stmt).scalars().all())

    def search_products(
        self,
        search: str = "",
        stock_filter: str = "all",
        sell_type: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        """Search products with filtering and pagination.

        Returns (products_list, total_count).
        """
        stmt = select(Product)
        count_stmt = select(func.count(Product.id))

        # Apply filters
        if search:
            like = f"%{search}%"
            stmt = stmt.where(Product.title.ilike(like))
            count_stmt = count_stmt.where(Product.title.ilike(like))

        if stock_filter == "in_stock":
            stmt = stmt.where(Product.stock > 0)
            count_stmt = count_stmt.where(Product.stock > 0)
        elif stock_filter == "out_of_stock":
            stmt = stmt.where(Product.stock == 0)
            count_stmt = count_stmt.where(Product.stock == 0)

        if sell_type:
            stmt = stmt.where(Product.sell_type == sell_type)
            count_stmt = count_stmt.where(Product.sell_type == sell_type)

        # Count
        total = self.session.execute(count_stmt).scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Product.updated_at.desc()).offset(offset).limit(page_size)
        products = list(self.session.execute(stmt).scalars().all())

        return products, total

    def get_watch_types_for_sku(self, sku: str) -> list[str]:
        """Get all watch types for a given SKU."""
        stmt = select(WatchlistItem.watch_type).where(WatchlistItem.sku == sku)
        return list(self.session.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_product(
        self,
        sku: str,
        title: str,
        price: float,
        regular_price: float | None,
        stock: int,
        sell_type: str | None,
        link: str | None,
        pic1: str | None = None,
        is_watched: bool = False,
    ) -> UpsertResult:
        """Insert or update a product, detecting price/stock changes.

        On change, appends rows to price_history / stock_history.
        Returns an UpsertResult describing what happened.
        """
        now = _now_iso()
        existing = self.get_by_sku(sku)

        if existing is None:
            # New product
            product = Product(
                sku=sku,
                title=title,
                price=price,
                regular_price=regular_price,
                stock=stock,
                sell_type=sell_type,
                link=link,
                pic1=pic1,
                is_watched=1 if is_watched else 0,
                updated_at=now,
            )
            self.session.add(product)

            # Record initial history
            self._insert_price_history(sku, price, regular_price, now)
            self._insert_stock_history(sku, stock, now)

            self.session.flush()
            return UpsertResult(
                product=product,
                is_new=True,
                price_changed=True,
                stock_changed=True,
            )

        # Existing product — detect changes
        price_changed = abs(existing.price - price) > 0.005
        stock_changed = existing.stock != stock
        old_price = existing.price if price_changed else None
        old_stock = existing.stock if stock_changed else None

        # Record history for changes
        if price_changed:
            self._insert_price_history(sku, price, regular_price, now)

        if stock_changed:
            self._insert_stock_history(sku, stock, now)

        # Update the current state
        existing.title = title
        existing.price = price
        existing.regular_price = regular_price
        existing.stock = stock
        existing.sell_type = sell_type
        existing.link = link
        existing.pic1 = pic1
        existing.is_watched = 1 if is_watched else 0
        existing.updated_at = now

        self.session.flush()

        return UpsertResult(
            product=existing,
            is_new=False,
            price_changed=price_changed,
            stock_changed=stock_changed,
            old_price=old_price,
            old_stock=old_stock,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _insert_price_history(
        self, sku: str, price: float, regular_price: float | None, observed_at: str
    ) -> None:
        self.session.add(
            PriceHistory(
                sku=sku,
                price=price,
                regular_price=regular_price,
                observed_at=observed_at,
            )
        )

    def _insert_stock_history(
        self, sku: str, stock: int, observed_at: str
    ) -> None:
        self.session.add(
            StockHistory(
                sku=sku,
                stock=stock,
                observed_at=observed_at,
            )
        )


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
