"""SQLAlchemy ORM models for the monitoring database."""

from __future__ import annotations

from sqlalchemy import Index, Integer, REAL, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(REAL, nullable=False)
    regular_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sell_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    pic1: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_watched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(REAL, nullable=False)
    regular_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_price_history_sku_observed", "sku", "observed_at"),
    )


class StockHistory(Base):
    __tablename__ = "stock_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_stock_history_sku_observed", "sku", "observed_at"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    watch_type: Mapped[str] = mapped_column(Text, nullable=False)
    # watch_type values: "back_in_stock" | "discount" | "lower_price"
    # Snapshot of the product's price at the moment we started watching.
    # Used to determine whether a "lower_price" watch has been satisfied.
    baseline_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_watchlist_sku_type", "sku", "watch_type", unique=True),
    )


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_alerts_created", "created_at"),
    )
