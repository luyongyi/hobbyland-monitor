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

# Curated mappings for current Hobbyland PG products whose Chinese/HK names
# differ too much from Bandai's Japanese titles. Values are still from the
# official Bandai Hobby PG listing extracted by this service.
PG_SKU_OVERRIDES = {
    "4573102630568": (29150, "https://bandai-hobby.net/item/01_2878/"),  # Strike Freedom
    "4573102638250": (16500, "https://bandai-hobby.net/item/01_803/"),   # Wing Gundam Zero Custom
    "4573102642332": (22000, "https://bandai-hobby.net/item/01_4475/"),  # Zeta Gundam
    "4573102642349": (20900, "https://bandai-hobby.net/item/01_4947/"),  # Strike Rouge + Skygrasper
    "4573102635440": (19800, "https://bandai-hobby.net/item/01_3718/"),  # Astray Red Frame
    "4573102635457": (28600, "https://bandai-hobby.net/item/01_988/"),   # 00 Raiser
    "4573102672483": (25300, "http://p-bandai.jp/item/item-1000124022"), # Astray Red Frame Kai
    "4573102642301": (13200, "https://bandai-hobby.net/item/01_2876/"),  # MS-06F Zaku II
    "4573102642295": (13200, "https://bandai-hobby.net/item/01_2877/"),  # MS-06S Char Zaku II
    "4573102555823": (25300, "https://bandai-hobby.net/item/01_2067/"),  # 00 Seven Sword/G
    "4573102632814": (34100, "https://p-bandai.jp/item/item-1000164779/"), # Unicorn Perfectibility
}

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
            or_(Product.msrp_source.is_(None), Product.msrp_source == "bandai_hobby_official_pg_not_found"),
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
            product.msrp_checked_at = now

            # Known PG SKU override from Bandai official listing.
            if product.sku in PG_SKU_OVERRIDES:
                msrp, official_url = PG_SKU_OVERRIDES[product.sku]
                product.msrp_jpy = msrp
                product.msrp_source = "bandai_hobby_official_pg_override"
                product.msrp_confidence = 100
                product.official_url = official_url
                matched += 1
                continue

            match, confidence = self._best_match(product.title, official)
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

    def enrich_mg_products(self) -> dict:
        """Enrich MG / MGEX products without MSRP.

        This is the first MG pass: automatic high-confidence title matching only.
        Products that do not reach the confidence threshold are marked not_found
        and can later be covered by curated overrides if needed.
        """
        # Clean up earlier low-confidence MG auto-matches. MG has many variants,
        # and anything below 94 should be reviewed or covered by overrides.
        low_conf_stmt = select(Product).where(
            Product.msrp_source == "bandai_hobby_official_mg",
            Product.msrp_confidence < 94,
        )
        for p in self.session.execute(low_conf_stmt).scalars().all():
            p.msrp_jpy = None
            p.msrp_source = "bandai_hobby_official_mg_not_found"
            p.official_url = None

        stmt = select(Product).where(
            Product.msrp_jpy.is_(None),
            or_(Product.msrp_source.is_(None), Product.msrp_source == "bandai_hobby_official_mg_not_found"),
            Product.title.ilike("%MG%"),
        )
        candidates = list(self.session.execute(stmt).scalars().all())
        candidates = [p for p in candidates if _is_mg_product(p.title)]

        if not candidates:
            return {"candidates": 0, "matched": 0, "official_count": 0}

        official = self.fetch_official_products("mg", max_pages=80)
        matched = 0
        now = _now_iso()

        for product in candidates:
            product.msrp_checked_at = now
            match, confidence = self._best_match(product.title, official)
            # MG has many variants and naming collisions, so require higher confidence
            # than PG to avoid wrong MSRP assignments.
            if match and confidence >= 94:
                product.msrp_jpy = match.msrp_jpy
                product.msrp_source = "bandai_hobby_official_mg"
                product.msrp_confidence = confidence
                product.official_url = match.detail_url
                matched += 1
                logger.info(
                    "MG MSRP matched: %s -> %s (JP¥%s, confidence=%s)",
                    product.sku, match.title, match.msrp_jpy, confidence,
                )
            else:
                product.msrp_source = "bandai_hobby_official_mg_not_found"
                product.msrp_confidence = confidence if match else 0

        self.session.flush()
        return {"candidates": len(candidates), "matched": matched, "official_count": len(official)}

    def fetch_pg_official_products(self) -> list[OfficialProduct]:
        """Fetch all official PG products from Bandai Hobby item_all listing."""
        return self.fetch_official_products("pg", max_pages=30)

    def fetch_official_products(self, brand: str, max_pages: int = 80) -> list[OfficialProduct]:
        """Fetch all official products for a Bandai Hobby brand."""
        all_items: list[OfficialProduct] = []
        seen: set[str] = set()

        for page in range(1, max_pages + 1):
            url = f"https://bandai-hobby.net/item_all/?brand={brand}"
            if page > 1:
                url = f"https://bandai-hobby.net/item_all/?p={page}&brand={brand}"

            html = self._fetch(url)
            items = self._parse_list_page(html)
            new = [it for it in items if it.detail_url not in seen]

            if not new:
                break

            for item in new:
                seen.add(item.detail_url)
                all_items.append(item)

            if f"?p={page + 1}&brand={brand}" not in html and f"./?p={page + 1}&brand={brand}" not in html:
                break

            time.sleep(0.15)

        logger.info("Fetched %d official %s products from Bandai", len(all_items), brand.upper())
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
    s = s.replace("ｐｇ", "pg").replace("ｍｇ", "mg").replace("ｕｎｌｅａｓｈｅｄ", "unleashed")
    s = re.sub(r"perfect\s+grade", " pg ", s, flags=re.I)
    s = re.sub(r"master\s+grade", " mg ", s, flags=re.I)
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
        "デスティニー": " destiny ",
        "命運": " destiny ",
        "命运": " destiny ",
        "インパルス": " impulse ",
        "衝擊": " impulse ",
        "冲击": " impulse ",
        "ペルフェクティビリティ": " perfectibility ",
        "完美獨角獸": " unicorn perfectibility ",
        "完美独角兽": " unicorn perfectibility ",
        "ユニコーン": " unicorn ",
        "獨角獸": " unicorn ",
        "独角兽": " unicorn ",
        "バンシィ": " banshee ",
        "報喪女妖": " banshee ",
        "报丧女妖": " banshee ",
        "エクシア": " exia ",
        "能天使": " exia ",
        "デュナメス": " dynames ",
        "力天使": " dynames ",
        "キュリオス": " kyrios ",
        "主天使": " kyrios ",
        "ヴァーチェ": " virtue ",
        "德天使": " virtue ",
        "ダブルオー": " double o ",
        "アストレイ": " astray ",
        "迷惘": " astray ",
        "紅異端": " red frame ",
        "红异端": " red frame ",
        "紅色機改": " red frame ",
        "红色机改": " red frame ",
        "紅色機": " red frame ",
        "红色机": " red frame ",
        "レッドフレーム": " red frame ",
        "ザク": " zaku ",
        "渣古": " zaku ",
        "量產型": " mass production ",
        "量产型": " mass production ",
        "シャア": " char ",
        "馬沙": " char ",
        "马沙": " char ",
        "ウイング": " wing ",
        "ゼロカスタム": " zero custom ",
        "ゼロ": " zero ",
        "飛翼": " wing ",
        "飞翼": " wing ",
        "ゼータ": " zeta ",
        "z高達": " zeta gundam ",
        "z高达": " zeta gundam ",
        "ν高達": " nu gundam ",
        "ν高达": " nu gundam ",
        "新安州": " sinanju ",
        "シナンジュ": " sinanju ",
        "巴巴托斯": " barbatos ",
        "バルバトス": " barbatos ",
        "陸戰型": " ground type ",
        "陆战型": " ground type ",
        "基拉德卡": " geara doga ",
        "ギラドーガ": " geara doga ",
        "艾比安": " epyon ",
        "エピオン": " epyon ",
        "重砲手": " heavyarms ",
        "重炮手": " heavyarms ",
        "ヘビーアームズ": " heavyarms ",
        "嫣紅突擊": " strike rouge ",
        "嫣红突击": " strike rouge ",
        "ストライクルージュ": " strike rouge ",
        "空中霸王": " skygrasper ",
        "スカイグラスパー": " skygrasper ",
        "七劍": " seven sword ",
        "七剑": " seven sword ",
        "セブンソード": " seven sword ",
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
    # Treat 00 as Double O only when it is a standalone model token, not inside MSZ-006.
    s = re.sub(r"(?<![a-z0-9])00(?![a-z0-9])", " double o ", s)
    s = re.sub(r"[^a-z0-9/]+", " ", s)
    s = re.sub(r"\bbandai\b|\b現貨\b|\b預訂\b|\b模型\b|\b組裝\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _score_match(hobby_tokens: set[str], official_tokens: set[str], hobby_norm: str, official_norm: str) -> int:
    score = 0

    # Hard structural signals.
    if "pg" in hobby_tokens and "pg" in official_tokens:
        score += 25
    if "mg" in hobby_tokens and "mg" in official_tokens:
        score += 25
    if "1/60" in hobby_tokens and "1/60" in official_tokens:
        score += 20
    if "1/100" in hobby_tokens and "1/100" in official_tokens:
        score += 20

    # Important model terms.
    important = {
        "unleashed", "nu", "gundam", "perfect", "strike", "freedom", "unicorn",
        "banshee", "exia", "double", "astray", "red", "frame", "zaku", "wing", "zeta",
        "led", "unit", "extension", "clear", "rx", "78", "2",
        "zeta", "rouge", "skygrasper", "seven", "sword", "mass", "production",
        "char", "zero", "custom", "perfectibility", "astray",
        "destiny", "impulse", "dynames", "kyrios", "virtue", "sinanju",
        "barbatos", "ground", "type", "geara", "doga", "epyon", "heavyarms",
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


def _is_mg_product(title: str) -> bool:
    """MG family, including MGEX, excluding MGSD."""
    s = title.lower()
    if "mgsd" in s:
        return False
    return bool(re.search(r"\bmg\b|mgex|master grade", s, re.I))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
