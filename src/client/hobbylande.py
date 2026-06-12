"""HTTP client for the Hobbylande backend API."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Default headers to mimic the frontend
_DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.hobbylandeshop.com",
    "Referer": "https://www.hobbylandeshop.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


class HobbylandeClient:
    """Client for the Hobbylande product API.

    Fetches product listings with pagination support.
    """

    def __init__(
        self,
        base_url: str = "https://backend.hobbylandeshop.com",
        request_body: dict[str, Any] | None = None,
        timeout: int = 30,
        page_delay: float = 1.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_body = request_body or {"category": ["model_area", "gundam_zone"]}
        self.timeout = timeout
        self.page_delay = page_delay

    def fetch_all_products(
        self,
        progress_cb=None,
    ) -> list[dict[str, Any]]:
        """Fetch ALL pages from the product list API.

        Iterates page 1..N until total_pages is exhausted.
        Returns a flat list of raw product dicts as returned by the API.

        progress_cb: optional callable(current_page, total_pages, fetched_count, total_count)
                     invoked after each successful page fetch.
        """
        all_products: list[dict[str, Any]] = []
        page = 1

        while True:
            logger.info("Fetching page %d ...", page)
            data = self._fetch_page(page)

            if data is None:
                logger.warning("Failed to fetch page %d, stopping pagination", page)
                break

            products = data.get("list", [])
            all_products.extend(products)
            total_pages = data.get("total_pages", 1)
            total_count = data.get("total", 0)
            logger.info(
                "Page %d/%d: got %d products (total so far: %d/%d)",
                page, total_pages, len(products), len(all_products), total_count,
            )

            # Notify progress observer
            if progress_cb is not None:
                try:
                    progress_cb(page, total_pages, len(all_products), total_count)
                except Exception:
                    logger.exception("progress_cb raised")

            if page >= total_pages:
                break

            page += 1
            time.sleep(self.page_delay)

        logger.info("Fetch complete: %d products across %d pages", len(all_products), page)
        return all_products

    def fetch_single_product(self, name: str) -> dict[str, Any] | None:
        """Fetch a single product by name via POST /api/product.

        Returns the product dict or None if not found.
        """
        url = f"{self.base_url}/api/product"
        try:
            resp = requests.post(
                url,
                json={"name": name},
                headers=_DEFAULT_HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") == 0:
                return body.get("data")
            logger.warning("API error for product '%s': %s", name, body.get("message"))
            return None
        except requests.RequestException as e:
            logger.error("Request failed for product '%s': %s", name, e)
            return None

    def _fetch_page(self, page: int) -> dict[str, Any] | None:
        """Fetch a single page of products.

        Returns the `data` dict from the API response, or None on failure.
        """
        url = f"{self.base_url}/api/products"
        body = {**self.request_body, "page": page}

        try:
            resp = requests.post(
                url,
                json=body,
                headers=_DEFAULT_HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = resp.json()

            if result.get("code") != 0:
                logger.warning(
                    "API returned error on page %d: code=%s message=%s",
                    page,
                    result.get("code"),
                    result.get("message"),
                )
                return None

            return result.get("data")

        except requests.RequestException as e:
            logger.error("Request failed for page %d: %s", page, e)
            return None
        except ValueError as e:
            logger.error("Invalid JSON response for page %d: %s", page, e)
            return None
