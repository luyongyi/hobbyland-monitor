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
MGEX_SKU_OVERRIDES = {
    "4573102633682": (17050, "https://bandai-hobby.net/item/01_4230/"),  # MGEX Strike Freedom Gundam
}

RG_SKU_OVERRIDES = {
    "4573102615947": (2750, "https://bandai-hobby.net/item/01_2228/"),   # RG 01 RX-78-2 Gundam
    "PRE-671554": (3850, "https://bandai-hobby.net/item/01_5261/"),      # RG RX-78-2 Gundam Ver.2.0
    "4573102616616": (3520, "https://bandai-hobby.net/item/01_3425/"),   # RG Wing Gundam
    "4573102654427": (4620, "https://bandai-hobby.net/item/01_4923/"),   # RG Gundam Epyon
    "4573102604255": (6050, "https://bandai-hobby.net/item/01_3306/"),   # RG Zeong
    "4573102616050": (5280, "https://bandai-hobby.net/item/01_1408/"),   # RG Sazabi
    "4573102616197": (4180, "https://bandai-hobby.net/item/01_660/"),    # RG Sinanju
    "4573102616203": (4510, "https://bandai-hobby.net/item/01_1085/"),   # RG Unicorn
    "4573102554604": (3850, "https://bandai-hobby.net/item/01_833/"),    # RG Astray Gold Frame Amatsu Mina
    "4573102616180": (3080, "https://bandai-hobby.net/item/01_387/"),    # RG Astray Red Frame
    "4573102616005": (3080, "https://bandai-hobby.net/item/01_96/"),     # RG Exia
    "4573102616142": (3080, "https://bandai-hobby.net/item/01_3721/"),   # RG Freedom
    "4573102616029": (3080, "https://bandai-hobby.net/item/01_251/"),    # RG Wing Gundam Zero EW
    "4573102616043": (3080, "https://bandai-hobby.net/item/01_558/"),     # RG 00 Qan[T]
    "4573102615992": (3630, "https://bandai-hobby.net/item/01_2883/"),    # RG Zeta Gundam
    "4573102615954": (3080, "https://bandai-hobby.net/item/01_2230/"),    # RG Char's Zaku II
    "4573102615961": (3080, "https://bandai-hobby.net/item/01_2224/"),    # RG Mass Production Zaku II
    "4573102616159": (3080, "https://bandai-hobby.net/item/01_3726/"),    # RG Justice Gundam
    "4573102616173": (3850, "https://bandai-hobby.net/item/01_5895/"),    # RG Strike Freedom Gundam
    "4573102616166": (3080, "https://bandai-hobby.net/item/01_5802/"),    # RG Destiny Gundam
    "4573102616135": (3080, "https://bandai-hobby.net/item/01_3720/"),    # RG Aile Strike Gundam
    "4573102616012": (3080, "https://bandai-hobby.net/item/01_151/"),     # RG Char's Z'Gok
    "4573102630537": (3080, "https://bandai-hobby.net/item/01_466/"),     # RG Wing Gundam EW
    "4573102616210": (4730, "https://bandai-hobby.net/item/01_1259/"),    # RG Banshee Norn
    "4573102630858": (3080, "https://bandai-hobby.net/item/01_1299/"),    # RG Tallgeese EW
    "4573102630520": (2750, "https://bandai-hobby.net/item/01_5740/"),    # RG Skygrasper Launcher/Sword Pack
    "4573102633583": (3850, "https://bandai-hobby.net/item/01_4104/"),    # RG God Gundam
    "4573102616036": (3630, "https://bandai-hobby.net/item/01_317/"),     # RG 00 Raiser
    "4573102555861": (6270, "https://bandai-hobby.net/item/01_2028/"),    # RG Full Armor Unicorn
    "4573102615978": (2750, "https://bandai-hobby.net/item/01_2881/"),    # RG Gundam Mk-II Titans
    "4573102615985": (3080, "https://bandai-hobby.net/item/01_2882/"),    # RG Gundam Mk-II AEUG
    "4573102576170": (2750, "https://bandai-hobby.net/item/01_2251/"),    # RG Crossbone Gundam X1
    "4573102673961": (8800, "https://bandai-hobby.net/item/01_5394/"),    # RG Akatsuki Gundam Oowashi
    "4573102685582": (3850, "https://bandai-hobby.net/item/01_5544/"),    # RG Shining Gundam
    "4573102687050": (3850, "https://bandai-hobby.net/item/01_5544/"),    # RG Shining Gundam
    "4573102630841": (2750, "https://bandai-hobby.net/item/01_756/"),     # RG Build Strike Full Package
    "4573102688743": (4620, "https://bandai-hobby.net/item/01_5968/"),    # RG Wing Gundam Zero
    "4573102619150": (4950, "https://bandai-hobby.net/item/01_3524/"),    # RG Hi-Nu Gundam
}

MG_SKU_OVERRIDES = {
    "4573102630445": (4620, "https://bandai-hobby.net/item/01_1788/"),   # Heavyarms EW
    "4573102554567": (5720, "https://bandai-hobby.net/item/01_5837/"),   # Geara Doga
    "4573102630421": (5720, "https://bandai-hobby.net/item/01_1779/"),   # Epyon EW
    "4573102567673": (4950, "https://bandai-hobby.net/item/01_2127/"),   # Dynames
    "4573102630827": (7590, "https://p-bandai.jp/item/item-1000141550/"), # 00 Raiser
    "4573102595478": (5500, "https://bandai-hobby.net/item/01_2785/"),   # Kyrios
    "4573102616128": (4840, "https://bandai-hobby.net/item/01_1349/"),   # F91 Ver.2.0
    "4573102579898": (5390, "https://bandai-hobby.net/item/01_1681/"),   # Force Impulse
    "4573102615824": (7700, "https://bandai-hobby.net/item/01_1668/"),   # Destiny Gundam Extreme Blast Mode
    "4573102630438": (4620, "https://bandai-hobby.net/item/01_1786/"),   # Sandrock EW
    "4573102616111": (5390, "https://bandai-hobby.net/item/01_542/"),    # Freedom Ver.2.0
    "4573102621719": (5500, "https://bandai-hobby.net/item/01_3754/"),   # Dom
    "4573102615862": (4620, "https://bandai-hobby.net/item/01_981/"),    # Exia
    "4573102615916": (7700, "https://bandai-hobby.net/item/01_1642/"),   # Hi-Nu Gundam
    "4573102629074": (5280, "https://bandai-hobby.net/item/01_1796/"),   # Aegis Gundam
    "4573102630414": (5940, "https://bandai-hobby.net/item/01_1688/"),   # Infinite Justice Gundam
    "4573102615909": (4180, "https://bandai-hobby.net/item/01_2813/"),   # Aile Strike Gundam
    "4573102630513": (5940, "https://bandai-hobby.net/item/01_829/"),    # Providence Gundam
    "4573102619198": (5500, "https://bandai-hobby.net/item/01_3523/"),   # Eclipse Gundam
    "4573102629067": (4400, "https://bandai-hobby.net/item/01_1794/"),   # Buster Gundam
    "4573102631503": (5720, "https://bandai-hobby.net/item/01_1019/"),   # Justice Gundam
    "4573102616067": (5720, "https://bandai-hobby.net/item/01_5643/"),   # Strike Freedom Gundam
    "4573102629043": (5060, "https://bandai-hobby.net/item/01_1789/"),   # Duel Gundam Assault Shroud
    "4573102641182": (5390, "https://bandai-hobby.net/item/01_1698/"),   # Sword Impulse Gundam
    "4573102615855": (4620, "https://bandai-hobby.net/item/01_1701/"),   # Gouf Ver.2.0
    "4573102615756": (3300, "https://p-bandai.jp/item/item-1000114334"), # Gouf Custom
    "4573102635754": (4840, "https://bandai-hobby.net/item/01_1394/"),   # Jegan
    "4573102581846": (4730, "https://bandai-hobby.net/item/01_2402/"),   # Gunner Zaku Warrior Luna
    "4573102628428": (4290, "https://bandai-hobby.net/item/01_3591/"),   # AGE-1 Normal
    "4573102640970": (5390, "https://bandai-hobby.net/item/01_5713/"),   # Delta Plus
    "4573102621726": (5500, "https://bandai-hobby.net/item/01_3772/"),   # Rick Dom
    "4573102615763": (3960, "https://bandai-hobby.net/item/01_2597/"),   # Z'Gok
    "4549660156291": (5940, "https://bandai-hobby.net/item/01_829/"),    # Providence Gundam
    "4573102638397": (3520, "https://bandai-hobby.net/item/01_1629/"),   # Master Gundam
    "4573102617880": (8800, "https://bandai-hobby.net/item/01_3656/"),   # Virtue
    "4573102683533": (6600, "https://bandai-hobby.net/item/01_5469/"),   # Gundam Vidar
    "4573102661371": (5280, "https://bandai-hobby.net/item/01_356/"),    # Fenice Rinascita
    "4573102628459": (4620, "https://bandai-hobby.net/item/01_5774/"),   # Tallgeese EW
    "4573102615473": (4730, "https://bandai-hobby.net/item/01_3389/"),   # Mobile Ginn
    "4573102631473": (5060, "https://bandai-hobby.net/item/01_4827/"),   # Acguy
    "4573102635075": (4840, "https://bandai-hobby.net/item/01_919/"),    # Kampfer
    "4573102638380": (4290, "https://bandai-hobby.net/item/01_1025/"),   # GP03S Stamen
    "4573102628435": (5060, "https://bandai-hobby.net/item/01_2280/"),   # AGE-2 Normal
    "4573102628442": (5060, "https://bandai-hobby.net/item/01_1797/"),   # AGE-2 Dark Hound
    "4573102630407": (5500, "https://p-bandai.jp/item/item-1000144878"), # Blast Impulse Gundam
    "4573102629050": (4400, "https://bandai-hobby.net/item/01_1792/"),   # Blitz Gundam
    "4573102615923": (8580, "https://bandai-hobby.net/item/01_338/"),    # Hyaku Shiki Ver.2.0
    "4573102640956": (5390, "https://bandai-hobby.net/item/01_3984/"),   # Altron Gundam EW
    "4573102628411": (4620, "https://bandai-hobby.net/item/01_1765/"),   # Deathscythe EW
    "4573102615886": (5390, "https://bandai-hobby.net/item/01_1775/"),   # Deathscythe Hell EW
    "4573102615879": (5390, "https://bandai-hobby.net/item/01_985/"),    # 00 Qan[T]
    "4573102635082": (4840, "https://bandai-hobby.net/item/01_1201/"),   # Qubeley
    "4573102631930": (4840, "https://bandai-hobby.net/item/01_3147/"),   # Qubeley Mk-II Puru Two
    "4573102657367": (8300, "https://bandai-hobby.net/item/01_5353/"),   # Musha Gundam Mk-II Tokugawa
    "4573102672315": (7040, "https://bandai-hobby.net/item/01_1753/"),   # Musha Gundam Mk-II
    "4573102641281": (4950, "https://bandai-hobby.net/item/01_1645/"),   # Strike Noir Gundam
    "4573102631497": (4180, "https://bandai-hobby.net/item/01_33/"),     # Gundam X
    "4573102635402": (3740, "https://bandai-hobby.net/item/01_3790/"),   # Hi-Zack
    "4573102629173": (14080, "https://bandai-hobby.net/item/01_1463/"),  # The O
    "4573102663733": (5390, "https://bandai-hobby.net/item/01_5649/"),   # Crossbone Gundam X1 Full Cloth
    "4573102635365": (4840, "https://bandai-hobby.net/item/01_1588/"),   # GP02A
    "4573102638229": (3190, "https://bandai-hobby.net/item/01_1448/"),   # GP01
    "4573102635396": (4290, "https://bandai-hobby.net/item/01_2667/"),   # Gogg
    "4573102631930": (4840, "https://bandai-hobby.net/item/01_3147/"),   # Qubeley Mk-II Puru Two
    "4573102672292": (8800, "https://bandai-hobby.net/item/01_1695/"),   # Shin Musha Gundam Sengoku no Jin
    "4573102630810": (4400, "https://bandai-hobby.net/item/01_983/"),    # GN-X
    "4573102661364": (5500, "https://bandai-hobby.net/item/01_55/"),     # Sengoku Astray
    "4573102638403": (2750, "https://bandai-hobby.net/item/01_1746/"),   # Shining Gundam
    "4573102635112": (5720, "https://bandai-hobby.net/item/01_5677/"),   # ReZEL
    "4573102692306": (4290, "https://bandai-hobby.net/item/01_1248/"),   # GM Command Colony Type
    "4573102628848": (4290, "https://bandai-hobby.net/item/01_3592/"),   # AGE-1 Titus
    "4573102631985": (5940, "https://bandai-hobby.net/item/01_5687/"),   # ReZEL Commander
    "4573102631480": (4400, "https://bandai-hobby.net/item/01_5797/"),   # Jesta
    "4573102635310": (7370, "http://p-bandai.jp/item/item-1000125385"),  # Avalanche Exia Dash
    "4573102672346": (5500, "https://bandai-hobby.net/item/01_1678/"),   # Launcher/Sword Strike Gundam
    "4573102672339": (7700, "https://bandai-hobby.net/item/01_1642/"),   # Hi-Nu Gundam
}

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

    def enrich_rg_products(self) -> dict:
        """Enrich RG products without MSRP.

        Conservative first pass: explicit overrides + very high confidence title
        matches only. Clear/color/coating/limited variants are intentionally
        left empty unless explicitly covered.
        """
        stmt = select(Product).where(
            Product.msrp_jpy.is_(None),
            or_(Product.msrp_source.is_(None), Product.msrp_source == "bandai_hobby_official_rg_not_found"),
            Product.title.ilike("%RG%"),
        )
        candidates = list(self.session.execute(stmt).scalars().all())
        candidates = [p for p in candidates if _is_rg_product(p.title)]
        if not candidates:
            return {"candidates": 0, "matched": 0, "official_count": 0}

        official = self.fetch_official_products("rg", max_pages=40)
        matched = 0
        now = _now_iso()

        for product in candidates:
            product.msrp_checked_at = now

            if product.sku in RG_SKU_OVERRIDES:
                msrp, official_url = RG_SKU_OVERRIDES[product.sku]
                product.msrp_jpy = msrp
                product.msrp_source = "bandai_hobby_official_rg_override"
                product.msrp_confidence = 100
                product.official_url = official_url
                matched += 1
                continue

            match, confidence = self._best_match(product.title, official)
            if match and confidence >= 96:
                product.msrp_jpy = match.msrp_jpy
                product.msrp_source = "bandai_hobby_official_rg"
                product.msrp_confidence = confidence
                product.official_url = match.detail_url
                matched += 1
                logger.info(
                    "RG MSRP matched: %s -> %s (JP¥%s, confidence=%s)",
                    product.sku, match.title, match.msrp_jpy, confidence,
                )
            else:
                product.msrp_source = "bandai_hobby_official_rg_not_found"
                product.msrp_confidence = confidence if match else 0

        self.session.flush()
        return {"candidates": len(candidates), "matched": matched, "official_count": len(official)}

    def enrich_mgex_products(self) -> dict:
        """Enrich MGEX products without MSRP."""
        stmt = select(Product).where(
            Product.msrp_jpy.is_(None),
            or_(
                Product.msrp_source.is_(None),
                Product.msrp_source == "bandai_hobby_official_mgex_not_found",
                Product.msrp_source == "bandai_hobby_official_mg_not_found",
            ),
            Product.title.ilike("%MGEX%"),
        )
        candidates = list(self.session.execute(stmt).scalars().all())
        if not candidates:
            return {"candidates": 0, "matched": 0, "official_count": 0}

        official = self.fetch_official_products("mgex", max_pages=10)
        matched = 0
        now = _now_iso()

        for product in candidates:
            product.msrp_checked_at = now

            if product.sku in MGEX_SKU_OVERRIDES:
                msrp, official_url = MGEX_SKU_OVERRIDES[product.sku]
                product.msrp_jpy = msrp
                product.msrp_source = "bandai_hobby_official_mgex_override"
                product.msrp_confidence = 100
                product.official_url = official_url
                matched += 1
                continue

            match, confidence = self._best_match(product.title, official)
            if match and confidence >= 88:
                product.msrp_jpy = match.msrp_jpy
                product.msrp_source = "bandai_hobby_official_mgex"
                product.msrp_confidence = confidence
                product.official_url = match.detail_url
                matched += 1
                logger.info(
                    "MGEX MSRP matched: %s -> %s (JP¥%s, confidence=%s)",
                    product.sku, match.title, match.msrp_jpy, confidence,
                )
            else:
                product.msrp_source = "bandai_hobby_official_mgex_not_found"
                product.msrp_confidence = confidence if match else 0

        self.session.flush()
        return {"candidates": len(candidates), "matched": matched, "official_count": len(official)}

    def enrich_mg_products(self) -> dict:
        """Enrich MG products without MSRP.

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

            if product.sku in MG_SKU_OVERRIDES:
                msrp, official_url = MG_SKU_OVERRIDES[product.sku]
                product.msrp_jpy = msrp
                product.msrp_source = "bandai_hobby_official_mg_override"
                product.msrp_confidence = 100
                product.official_url = official_url
                matched += 1
                continue

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
        "ダブルオーライザー": " double o raiser ",
        "ライザー": " raiser ",
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
        "トランザム": " trans am ",
        "trans-am": " trans am ",
        "メタリック": " metallic ",
        "金屬": " metallic ",
        "金属": " metallic ",
        "チタニウム": " titanium ",
        "透明": " clear ",
        "クリアカラー": " clear ",
        "動畫配色": " anime color ",
        "动画配色": " anime color ",
        "限定": " limited ",
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
    for special in ["led", "unit", "extension", "clear", "metallic", "titanium", "trans", "am", "limited", "anime"]:
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


def _is_rg_product(title: str) -> bool:
    return bool(re.search(r"\brg\b|real grade", title, re.I))


def _is_mg_product(title: str) -> bool:
    """MG family, including MGEX, excluding MGSD."""
    s = title.lower()
    if "mgsd" in s:
        return False
    return bool(re.search(r"\bmg\b|mgex|master grade", s, re.I))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
