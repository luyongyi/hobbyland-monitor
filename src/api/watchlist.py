"""Watchlist CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import Product
from ..repository.product_repo import ProductRepository
from ..repository.watchlist_repo import WatchlistRepository
from .deps import get_db

router = APIRouter(tags=["watchlist"])


class WatchlistItemOut(BaseModel):
    sku: str
    title: str
    price: float
    regular_price: float | None
    stock: int
    pic1: str | None
    watch_type: str
    created_at: str


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
            watch_type=item.watch_type,
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
        watch_type=item.watch_type,
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
