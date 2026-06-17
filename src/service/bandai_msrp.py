"""Bandai Hobby MSRP enrichment.

First version: PG only. It fetches the official Bandai Hobby PG listing once,
extracts official JPY MSRP, and matches against Hobbyland PG products using
Gundam-specific title normalization.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape

import requests
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.models import Product

logger = logging.getLogger(__name__)

BANDAI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://bandai-hobby.net/item_all/?brand=pg",
}


@dataclass
class OfficialProduct:
    title: str
    msrp_jpy: int
    release_date: str
    detail_url: str
    normalized: str
    tokens: set[str]


class BandaiMsrpService:
    """Fetch and match official Bandai Hobby MSRP data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def enrich_pg_products(self) -> dict:
        """Enrich PG products without MSRP.

        Returns a summary dict with counts.
        """
        stmt = select(Product).where(
            Product.msrp_jpy.is_(None),
            Product.msrp_source.is_(None),
            or_(Product.title.ilike("%PG%"), Product.title.ilike("%Perfect Grade%")),
        )
        candidates = list(self.session.execute(stmt).scalars().all())
        candidates = [p for p in candidates if _is_pg_product(p.title)]

        if not candidates:
            return {"candidates": 0, "matched": 0, "official_count": 0}

        official = self.fetch_pg_official_products()
        matched = 0
        now = _now_iso()

        for product in candidates:
            match, confidence = self._best_match(product.title, official)
            product.msrp_checked_at = now
            if match and confidence >= 88:
                product.msrp_jpy = match.msrp_jpy
                product.msrp_source = "bandai_hobby_official_pg"
                product.msrp_confidence = confidence
                product.official_url = match.detail_url
                matched += 1
                logger.info(
                    "MSRP matched: %s -> %s (JP¥%s, confidence=%s)",
                    product.sku, match.title, match.msrp_jpy, confidence,
                )
            else:
                # Mark checked so we do not keep hammering Bandai for poor matches.
                product.msrp_source = "bandai_hobby_official_pg_not_found"
                product.msrp_confidence = confidence if match else 0

        self.session.flush()
        return {"candidates": len(candidates), "matched": matched, "official_count": len(official)}

    def fetch_pg_official_products(self) -> list[OfficialProduct]:
        """Fetch all official PG products from Bandai Hobby item_all listing."""
        all_items: list[OfficialProduct] = []
        seen: set[str] = set()

        for page in range(1, 30):
            url = "https://bandai-hobby.net/item_all/?brand=pg"
            if page > 1:
                url = f"https://bandai-hobby.net/item_all/?p={page}&brand=pg"

            html = self._fetch(url)
            items = self._parse_list_page(html)
            new = [it for it in items if it.detail_url not in seen]

            if not new:
                break

            for item in new:
                seen.add(item.detail_url)
                all_items.append(item)

            if f"?p={page + 1}&brand=pg" not in html and f"./?p={page + 1}&brand=pg" not in html:
                break

            time.sleep(0.25)

        logger.info("Fetched %d official PG products from Bandai", len(all_items))
        return all_items

    def _fetch(self, url: str) -> str:
        resp = requests.get(url, headers=BANDAI_HEADERS, timeout=20)
        resp.raise_for_status()
        text = resp.text
        if "404 NOT FOUND" in text[:1000]:
            raise RuntimeError(f"Bandai returned 404 fallback for {url}")
        return text

    def _parse_list_page(self, html: str) -> list[OfficialProduct]:
        blocks = re.findall(
            r'<a\s+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*p-card[^"\']*["\'][^>]*>(.*?)</a>',
            html,
            re.S | re.I,
        )
        out: list[OfficialProduct] = []
        for href, block in blocks:
            title_m = re.search(r'<div class="p-card__tit">(.*?)</div>', block, re.S)
            price_m = re.search(r'<div class="p-card__price">(.*?)</div>', block, re.S)
            date_m = re.search(r'<div class="p-card_date">(.*?)</div>', block, re.S)
            if not title_m or not price_m:
                continue
            title = _clean_html(title_m.group(1))
            msrp = _parse_jpy(_clean_html(price_m.group(1)))
            if not msrp:
                continue
            normalized = normalize_title(title)
            out.append(OfficialProduct(
                title=title,
                msrp_jpy=msrp,
                release_date=_clean_html(date_m.group(1)) if date_m else "",
                detail_url=urllib.parse.urljoin("https://bandai-hobby.net/", href),
                normalized=normalized,
                tokens=set(normalized.split()),
            ))
        return out

    def _best_match(self, hobby_title: str, official: list[OfficialProduct]) -> tuple[OfficialProduct | None, int]:
        hobby_norm = normalize_title(hobby_title)
        hobby_tokens = set(hobby_norm.split())
        best: OfficialProduct | None = None
        best_score = 0

        for item in official:
            score = _score_match(hobby_tokens, item.tokens, hobby_norm, item.normalized)
            if score > best_score:
                best = item
                best_score = score

        return best, best_score


def normalize_title(title: str) -> str:
    """Normalize Chinese/Japanese/English Gundam product names to comparable tokens."""
    s = title.lower()
    s = re.sub(r"\[[^\]]+\]|【[^】]+】|《[^》]+》|（[^）]*ver\.?[^）]*）", " ", s, flags=re.I)
    s = s.replace("ｐｇ", "pg").replace("ｕｎｌｅａｓｈｅｄ", "unleashed")
    replacements = {
        "高達": " gundam ",
        "鋼彈": " gundam ",
        "ガンダム": " gundam ",
        "ν": " nu ",
        "ニュー": " nu ",
        "牛": " nu ",
        "パーフェクトストライク": " perfect strike ",
        "完美突擊": " perfect strike ",
        "完美突击": " perfect strike ",
        "ストライクフリーダム": " strike freedom ",
        "突擊自由": " strike freedom ",
        "突击自由": " strike freedom ",
        "ユニコーン": " unicorn ",
        "獨角獸": " unicorn ",
        "独角兽": " unicorn ",
        "バンシィ": " banshee ",
        "報喪女妖": " banshee ",
        "报丧女妖": " banshee ",
        "エクシア": " exia ",
        "能天使": " exia ",
        "ダブルオー": " double o ",
        "00": " double o ",
        "アストレイ": " astray ",
        "紅異端": " red frame ",
        "红异端": " red frame ",
        "レッドフレーム": " red frame ",
        "ザク": " zaku ",
        "シャア": " char ",
        "ウイング": " wing ",
        "飛翼": " wing ",
        "飞翼": " wing ",
        "ゼータ": " zeta ",
        "馬克兔": " mk ii ",
        "mk-ii": " mk ii ",
        "mark ii": " mk ii ",
        "ledユニット": " led unit ",
        "led 組件": " led unit ",
        "led组件": " led unit ",
        "拡張": " extension ",
        "擴張": " extension ",
        "扩展": " extension ",
        "クリア": " clear ",
        "透明": " clear ",
    }
    for k, v in replacements.items():
        s = s.replace(k.lower(), v)
    s = re.sub(r"[^a-z0-9/]+", " ", s)
    s = re.sub(r"\bbandai\b|\b現貨\b|\b預訂\b|\b模型\b|\b組裝\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _score_match(hobby_tokens: set[str], official_tokens: set[str], hobby_norm: str, official_norm: str) -> int:
    score = 0

    # Hard structural signals.
    if "pg" in hobby_tokens and "pg" in official_tokens:
        score += 25
    if "1/60" in hobby_tokens and "1/60" in official_tokens:
        score += 20

    # Important model terms.
    important = {
        "unleashed", "nu", "gundam", "perfect", "strike", "freedom", "unicorn",
        "banshee", "exia", "double", "astray", "red", "frame", "zaku", "wing", "zeta",
        "led", "unit", "extension", "clear", "rx", "78", "2",
    }
    overlap = (hobby_tokens & official_tokens)
    score += min(45, len(overlap & important) * 9)

    # Generic token overlap.
    if hobby_tokens and official_tokens:
        score += int(20 * len(overlap) / max(len(hobby_tokens), len(official_tokens)))

    # Conflict penalties: LED/extension/clear must not be mixed with body kit.
    for special in ["led", "unit", "extension", "clear"]:
        if (special in hobby_tokens) != (special in official_tokens):
            score -= 25

    return max(0, min(100, score))


def _clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", unescape(s)).strip()


def _parse_jpy(s: str) -> int | None:
    m = re.search(r"([0-9,]+)\s*円", s)
    return int(m.group(1).replace(",", "")) if m else None


def _is_pg_product(title: str) -> bool:
    s = title.lower()
    return bool(re.search(r"\bpg\b|perfect grade", s, re.I))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
