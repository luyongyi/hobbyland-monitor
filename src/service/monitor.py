"""Core monitoring service: fetch → compare → alert."""

from __future__ import annotations

import logging
from typing import Any

from ..client.hobbylande import HobbylandeClient
from ..config import AlertConfig
from ..notifier.base import Alert, Notifier
from ..repository.alert_repo import AlertRepository
from ..repository.product_repo import ProductRepository
from ..repository.watchlist_repo import WatchlistRepository
from .bandai_msrp import BandaiMsrpService

logger = logging.getLogger(__name__)


class MonitorService:
    """Orchestrates a full scan cycle: fetch products, detect changes, notify."""

    def __init__(
        self,
        client: HobbylandeClient,
        product_repo: ProductRepository,
        watchlist_repo: WatchlistRepository,
        alert_repo: AlertRepository,
        notifiers: list[Notifier],
        alert_config: AlertConfig,
    ) -> None:
        self.client = client
        self.product_repo = product_repo
        self.watchlist_repo = watchlist_repo
        self.alert_repo = alert_repo
        self.notifiers = notifiers
        self.alert_config = alert_config

    def run_scan(self, runner=None) -> None:
        """Execute one complete scan cycle.

        1. Fetch all products from API (reports progress via runner)
        2. Upsert each into DB (detecting changes)
        3. Build alerts for watched SKUs based on their watch types
        4. Persist alerts to DB
        5. Send alerts through all enabled notifiers
        """
        logger.info("=== Scan started ===")

        # Load watched SKUs from database
        watched_skus = self.watchlist_repo.get_watched_skus()
        # Build a map of sku -> set of watch_types for alert filtering
        watch_map: dict[str, set[str]] = {}
        for sku in watched_skus:
            types = self.watchlist_repo.get_watch_types_for_sku(sku)
            watch_map[sku] = set(types)

        logger.info("Watching %d SKU(s)", len(watched_skus))

        # 1. Fetch with progress reporting
        def _on_page(current_page, total_pages, fetched_count, total_count):
            if runner is not None:
                runner.update_progress(
                    state="fetching",
                    current_page=current_page,
                    total_pages=total_pages,
                    fetched_count=fetched_count,
                    total_count=total_count,
                )

        try:
            products = self.client.fetch_all_products(progress_cb=_on_page)
        except Exception:
            logger.exception("Failed to fetch products from API")
            if runner is not None:
                runner.update_progress(state="failed", error="fetch_failed")
            return

        if not products:
            logger.warning("No products returned from API")
            if runner is not None:
                runner.update_progress(state="completed")
            return

        logger.info("Fetched %d products, processing...", len(products))
        if runner is not None:
            runner.update_progress(state="processing", processed_count=0)

        # 2. Upsert & collect alerts
        alerts: list[Alert] = []
        watched_found: set[str] = set()

        for i, raw in enumerate(products, start=1):
            sku = raw.get("sku", "")
            if not sku:
                continue

            is_watched = sku in watched_skus
            if is_watched:
                watched_found.add(sku)

            try:
                price = float(raw.get("price", 0))
                regular_price_raw = raw.get("regular_price")
                regular_price = float(regular_price_raw) if regular_price_raw else None
                stock = int(raw.get("stock", 0))
            except (ValueError, TypeError) as e:
                logger.warning("Skipping product %s: invalid data (%s)", sku, e)
                continue

            result = self.product_repo.upsert_product(
                sku=sku,
                title=raw.get("title", ""),
                price=price,
                regular_price=regular_price,
                stock=stock,
                sell_type=raw.get("sell_type"),
                link=raw.get("link"),
                pic1=raw.get("pic1"),
                is_watched=is_watched,
            )

            # Update processing progress every 25 items (cheap, frequent enough for UI)
            if runner is not None and i % 25 == 0:
                runner.update_progress(processed_count=i)

            # Only build alerts for watched products
            if not is_watched:
                continue

            watch_types = watch_map.get(sku, set())
            product_alerts = self._build_alerts(result, watch_types)
            alerts.extend(product_alerts)

        # Final processed count
        if runner is not None:
            runner.update_progress(processed_count=len(products), alerts_generated=len(alerts))

        # Warn about watched SKUs not found in the API response
        missing = watched_skus - watched_found
        if missing:
            logger.warning(
                "Watched SKUs not found in API response: %s", ", ".join(missing)
            )

        # Enrich PG products with official Bandai JP¥ MSRP once, only for missing data.
        try:
            msrp_service = BandaiMsrpService(self.product_repo.session)
            summary = msrp_service.enrich_pg_products()
            if summary.get("candidates"):
                logger.info("PG MSRP enrichment: %s", summary)
            rg_summary = msrp_service.enrich_rg_products()
            if rg_summary.get("candidates"):
                logger.info("RG MSRP enrichment: %s", rg_summary)
            mgsd_summary = msrp_service.enrich_mgsd_products()
            if mgsd_summary.get("candidates"):
                logger.info("MGSD MSRP enrichment: %s", mgsd_summary)
            mgex_summary = msrp_service.enrich_mgex_products()
            if mgex_summary.get("candidates"):
                logger.info("MGEX MSRP enrichment: %s", mgex_summary)
            mg_summary = msrp_service.enrich_mg_products()
            if mg_summary.get("candidates"):
                logger.info("MG MSRP enrichment: %s", mg_summary)
        except Exception:
            logger.exception("PG MSRP enrichment failed")

        # 3. Persist alerts to DB
        if alerts:
            self.alert_repo.save_alerts(alerts)
            logger.info("Saved %d alert(s) to database", len(alerts))

        # 4. Send alerts via notifiers
        if alerts:
            logger.info("Sending %d alert(s) via notifiers", len(alerts))
            for notifier in self.notifiers:
                try:
                    notifier.send_batch(alerts)
                except Exception:
                    logger.exception(
                        "Notifier %s failed", type(notifier).__name__
                    )
        else:
            logger.info("No alerts to send")

        logger.info("=== Scan complete: %d products, %d alerts ===", len(products), len(alerts))

    # ------------------------------------------------------------------
    # Alert building
    # ------------------------------------------------------------------

    def _build_alerts(self, result: Any, watch_types: set[str]) -> list[Alert]:
        """Build Alert objects from an UpsertResult for a watched product.

        Only creates alerts that match the product's watch type(s):
        - back_in_stock: only if "back_in_stock" is in watch_types
        - discount: only if "discount" is in watch_types
        - lower_price: only if "lower_price" is in watch_types
        """
        alerts: list[Alert] = []
        product = result.product

        # Back-in-stock: stock went from 0 to >0
        if (
            "back_in_stock" in watch_types
            and self.alert_config.back_in_stock
            and result.stock_changed
            and result.old_stock is not None
            and result.old_stock == 0
            and product.stock > 0
        ):
            alerts.append(Alert(
                alert_type="back_in_stock",
                sku=product.sku,
                title=product.title,
                old_value=str(result.old_stock),
                new_value=str(product.stock),
                extra={"link": product.link or "", "pic1": product.pic1 or ""},
            ))

        # Discount alert: price dropped below regular_price (first time going on sale)
        if (
            "discount" in watch_types
            and self.alert_config.price_change
            and result.price_changed
            and result.old_price is not None
            and product.regular_price is not None
            and product.price < product.regular_price
            # Only fire if the old price was >= regular_price (just started discounting)
            and result.old_price >= product.regular_price - 0.005
        ):
            alerts.append(Alert(
                alert_type="discount",
                sku=product.sku,
                title=product.title,
                old_value=f"{result.old_price:.2f}",
                new_value=f"{product.price:.2f}",
                extra={
                    "regular_price": f"{product.regular_price:.2f}",
                    "link": product.link or "",
                    "pic1": product.pic1 or "",
                },
            ))

        # Lower price alert: already-discounted item dropped further in price
        if (
            "lower_price" in watch_types
            and self.alert_config.price_change
            and result.price_changed
            and result.old_price is not None
            and product.regular_price is not None
            and product.price < product.regular_price
            # Only fire if it was already discounted (old price was also < regular)
            and result.old_price < product.regular_price - 0.005
            and product.price < result.old_price - 0.005  # price went down further
        ):
            alerts.append(Alert(
                alert_type="lower_price",
                sku=product.sku,
                title=product.title,
                old_value=f"{result.old_price:.2f}",
                new_value=f"{product.price:.2f}",
                extra={
                    "regular_price": f"{product.regular_price:.2f}",
                    "link": product.link or "",
                    "pic1": product.pic1 or "",
                },
            ))

        # General price change alert (for any watched product, regardless of watch type)
        # This catches price changes not covered by the specific types above
        if (
            self.alert_config.price_change
            and result.price_changed
            and result.old_price is not None
            # Avoid duplicating alerts already created above
            and not any(a.alert_type in ("discount", "lower_price") for a in alerts)
        ):
            alerts.append(Alert(
                alert_type="price_change",
                sku=product.sku,
                title=product.title,
                old_value=f"{result.old_price:.2f}",
                new_value=f"{product.price:.2f}",
                extra={
                    "link": product.link or "",
                    "pic1": product.pic1 or "",
                    "regular_price": f"{product.regular_price:.2f}" if product.regular_price else "",
                },
            ))

        return alerts
