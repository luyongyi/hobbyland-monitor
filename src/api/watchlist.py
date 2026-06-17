"""Watchlist CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import Product
from ..repository.product_repo import ProductRepository
from ..repository.watchlist_repo import WatchlistRepository
from ..service.exchange_rate import ExchangeRateService
from .deps import get_db

router = APIRouter(tags=["watchlist"])


class WatchlistItemOut(BaseModel):
    sku: str
    title: str
    price: float
    regular_price: float | None
    stock: int
    pic1: str | None
    msrp_jpy: int | None
    msrp_source: str | None
    msrp_confidence: int | None
    official_url: str | None
    msrp_hkd_estimate: float | None
    jpy_hkd_rate: float | None
    watch_type: str
    baseline_price: float | None
    is_satisfied: bool          # 是否已达成（缺货变有货 / 原价变打折 / 价格更低）
    created_at: str


def _is_satisfied(watch_type: str, product, baseline_price: float | None) -> bool:
    """Determine whether a watch goal has been reached."""
    if watch_type == "back_in_stock":
        return product.stock > 0
    if watch_type == "discount":
        # 用户希望此商品打折 → 现价低于原价就算达成
        return (
            product.regular_price is not None
            and product.price < product.regular_price - 0.005
        )
    if watch_type == "lower_price":
        # 用户希望价格继续下降 → 比关注时的基准价更低就算达成
        if baseline_price is None:
            return False
        return product.price < baseline_price - 0.005
    return False


class WatchlistAddRequest(BaseModel):
    sku: str
    watch_type: str  # "back_in_stock" | "discount" | "lower_price"


class SuggestedTypeResponse(BaseModel):
    suggested_type: str
    reasoning: str


WATCH_TYPE_LABELS = {
    "back_in_stock": "到货关注",
    "discount": "打折关注",
    "lower_price": "更低价关注",
}


@router.get("/watchlist", response_model=list[WatchlistItemOut])
def list_watchlist(
    watch_type: str = Query(""),
    db: Session = Depends(get_db),
) -> list[WatchlistItemOut]:
    """List all watched items, optionally filtered by watch type."""
    watchlist_repo = WatchlistRepository(db)
    product_repo = ProductRepository(db)
    rate_record = ExchangeRateService(db).get_latest_jpy_hkd()
    jpy_hkd_rate = rate_record.rate if rate_record else None

    if watch_type:
        items = watchlist_repo.get_by_type(watch_type)
    else:
        items = watchlist_repo.get_all()

    result = []
    for item in items:
        product = product_repo.get_by_sku(item.sku)
        if product is None:
            continue
        result.append(WatchlistItemOut(
            sku=item.sku,
            title=product.title,
            price=product.price,
            regular_price=product.regular_price,
            stock=product.stock,
            pic1=product.pic1,
            msrp_jpy=product.msrp_jpy,
            msrp_source=product.msrp_source,
            msrp_confidence=product.msrp_confidence,
            official_url=product.official_url,
            msrp_hkd_estimate=(round(product.msrp_jpy * jpy_hkd_rate, 2) if product.msrp_jpy and jpy_hkd_rate else None),
            jpy_hkd_rate=jpy_hkd_rate,
            watch_type=item.watch_type,
            baseline_price=item.baseline_price,
            is_satisfied=_is_satisfied(item.watch_type, product, item.baseline_price),
            created_at=item.created_at,
        ))

    return result


@router.post("/watchlist", response_model=WatchlistItemOut, status_code=201)
def add_watch(req: WatchlistAddRequest, db: Session = Depends(get_db)) -> WatchlistItemOut:
    """Add a watch entry for a product."""
    if req.watch_type not in ("back_in_stock", "discount", "lower_price"):
        raise HTTPException(status_code=400, detail=f"Invalid watch_type: {req.watch_type}")

    watchlist_repo = WatchlistRepository(db)
    product_repo = ProductRepository(db)
    rate_record = ExchangeRateService(db).get_latest_jpy_hkd()
    jpy_hkd_rate = rate_record.rate if rate_record else None

    try:
        item = watchlist_repo.add_watch(req.sku, req.watch_type)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))

    product = product_repo.get_by_sku(req.sku)
    return WatchlistItemOut(
        sku=item.sku,
        title=product.title if product else "",
        price=product.price if product else 0,
        regular_price=product.regular_price if product else None,
        stock=product.stock if product else 0,
        pic1=product.pic1 if product else None,
        msrp_jpy=product.msrp_jpy if product else None,
        msrp_source=product.msrp_source if product else None,
        msrp_confidence=product.msrp_confidence if product else None,
        official_url=product.official_url if product else None,
        msrp_hkd_estimate=(round(product.msrp_jpy * jpy_hkd_rate, 2) if product and product.msrp_jpy and jpy_hkd_rate else None),
        jpy_hkd_rate=jpy_hkd_rate,
        watch_type=item.watch_type,
        baseline_price=item.baseline_price,
        is_satisfied=_is_satisfied(item.watch_type, product, item.baseline_price) if product else False,
        created_at=item.created_at,
    )


@router.delete("/watchlist/{sku}/{watch_type}")
def remove_watch(sku: str, watch_type: str, db: Session = Depends(get_db)) -> dict:
    """Remove a watch entry."""
    watchlist_repo = WatchlistRepository(db)
    removed = watchlist_repo.remove_watch(sku, watch_type)
    if not removed:
        raise HTTPException(status_code=404, detail="Watch entry not found")
    return {"detail": "removed"}


@router.get("/watchlist/suggested-type/{sku}", response_model=SuggestedTypeResponse)
def suggested_type(sku: str, db: Session = Depends(get_db)) -> SuggestedTypeResponse:
    """Get the recommended watch type for a product based on its current state."""
    watchlist_repo = WatchlistRepository(db)
    product_repo = ProductRepository(db)

    product = product_repo.get_by_sku(sku)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {sku} not found")

    suggested = watchlist_repo.suggest_watch_type(sku)
    label = WATCH_TYPE_LABELS.get(suggested, suggested)

    # Build reasoning string
    if suggested == "back_in_stock":
        reasoning = f"商品缺货 (库存={product.stock})，建议关注到货提醒"
    elif suggested == "discount":
        reasoning = f"商品有货 (库存={product.stock}) 且未打折 (价格=${product.price:.0f}=原价)，建议关注打折提醒"
    else:  # lower_price
        reasoning = f"商品有货 (库存={product.stock}) 且已打折 (现价${product.price:.0f} < 原价${product.regular_price:.0f})，建议关注更低价提醒"

    return SuggestedTypeResponse(suggested_type=suggested, reasoning=reasoning)
