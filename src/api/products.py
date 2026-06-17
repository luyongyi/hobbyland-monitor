"""Product listing and search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import Product
from ..repository.product_repo import ProductRepository
from ..repository.watchlist_repo import WatchlistRepository
from .deps import get_db

router = APIRouter(tags=["products"])


class ProductOut(BaseModel):
    sku: str
    title: str
    price: float
    regular_price: float | None
    stock: int
    sell_type: str | None
    link: str | None
    pic1: str | None
    updated_at: str
    watch_types: list[str]

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


@router.get("/products", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    stock_filter: str = Query("all"),
    sell_type: str = Query(""),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    """List products with pagination, search, and filters."""
    repo = ProductRepository(db)
    watchlist_repo = WatchlistRepository(db)

    products, total = repo.search_products(
        search=search,
        stock_filter=stock_filter,
        sell_type=sell_type,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    items = []
    for p in products:
        watch_types = watchlist_repo.get_watch_types_for_sku(p.sku)
        items.append(ProductOut(
            sku=p.sku,
            title=p.title,
            price=p.price,
            regular_price=p.regular_price,
            stock=p.stock,
            sell_type=p.sell_type,
            link=p.link,
            pic1=p.pic1,
            updated_at=p.updated_at,
            watch_types=watch_types,
        ))

    return ProductListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/products/{sku}", response_model=ProductOut)
def get_product(sku: str, db: Session = Depends(get_db)) -> ProductOut:
    """Get a single product by SKU."""
    repo = ProductRepository(db)
    watchlist_repo = WatchlistRepository(db)

    product = repo.get_by_sku(sku)
    if product is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Product {sku} not found")

    watch_types = watchlist_repo.get_watch_types_for_sku(sku)
    return ProductOut(
        sku=product.sku,
        title=product.title,
        price=product.price,
        regular_price=product.regular_price,
        stock=product.stock,
        sell_type=product.sell_type,
        link=product.link,
        pic1=product.pic1,
        updated_at=product.updated_at,
        watch_types=watch_types,
    )
