"""Alert history endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..repository.alert_repo import AlertRepository
from .deps import get_db

router = APIRouter(tags=["alerts"])


class AlertOut(BaseModel):
    id: int
    alert_type: str
    sku: str
    title: str
    old_value: str | None
    new_value: str
    extra: dict
    created_at: str


class AlertListResponse(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    page_size: int


ALERT_TYPE_LABELS = {
    "back_in_stock": "到货提醒",
    "discount": "打折提醒",
    "lower_price": "更低价提醒",
    "price_change": "价格变动",
    "good_deal": "好价提醒",
}


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    alert_type: str = Query(""),
    sku: str = Query(""),
    db: Session = Depends(get_db),
) -> AlertListResponse:
    """List alert history with pagination and filtering."""
    repo = AlertRepository(db)

    records, total = repo.get_alerts(
        page=page,
        page_size=page_size,
        alert_type=alert_type,
        sku=sku,
    )

    items = []
    for r in records:
        extra = {}
        try:
            extra = json.loads(r.extra) if r.extra else {}
        except (json.JSONDecodeError, TypeError):
            pass

        items.append(AlertOut(
            id=r.id,
            alert_type=r.alert_type,
            sku=r.sku,
            title=r.title,
            old_value=r.old_value,
            new_value=r.new_value,
            extra=extra,
            created_at=r.created_at,
        ))

    return AlertListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
