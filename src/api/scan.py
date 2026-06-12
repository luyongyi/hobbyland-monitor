"""Scan status endpoint (read-only).

Scans only run automatically: at server startup and every day at the configured
time (default 12:00). Manual triggering is intentionally not exposed to keep
upstream API access minimal.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..repository.alert_repo import AlertRepository
from ..service.scan_runner import ScanRunner
from .deps import get_db

router = APIRouter(tags=["scan"])

# Module-level scan runner reference; set in main.py
_scan_runner: ScanRunner | None = None


def set_scan_runner(runner: ScanRunner) -> None:
    global _scan_runner
    _scan_runner = runner


def get_scan_runner() -> ScanRunner:
    if _scan_runner is None:
        raise RuntimeError("ScanRunner not initialized")
    return _scan_runner


class ScanStatusResponse(BaseModel):
    is_running: bool
    last_alert_at: str | None
    state: str                       # "idle" | "fetching" | "processing" | "completed" | "failed"
    current_page: int
    total_pages: int
    fetched_count: int
    total_count: int
    processed_count: int
    alerts_generated: int
    fetch_percent: int
    process_percent: int
    started_at: str | None
    finished_at: str | None
    error: str | None


@router.get("/scan/status", response_model=ScanStatusResponse)
def scan_status(db: Session = Depends(get_db)) -> ScanStatusResponse:
    """Get detailed scan status and progress (read-only, no upstream access)."""
    runner = get_scan_runner()
    alert_repo = AlertRepository(db)
    progress = runner.progress.to_dict()
    return ScanStatusResponse(
        is_running=runner.is_running,
        last_alert_at=alert_repo.get_latest_alert_time(),
        **progress,
    )
