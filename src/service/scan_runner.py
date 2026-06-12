"""Scan runner: thin wrapper for executing a scan with progress tracking."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ScanProgress:
    """Snapshot of the current/last scan progress."""

    state: str = "idle"                      # "idle" | "fetching" | "processing" | "completed" | "failed"
    current_page: int = 0
    total_pages: int = 0
    fetched_count: int = 0                   # products fetched from API so far
    total_count: int = 0                     # total products reported by API
    processed_count: int = 0                 # products upserted into DB so far
    alerts_generated: int = 0                # alerts generated in this scan
    started_at: str | None = None            # ISO timestamp of scan start
    finished_at: str | None = None           # ISO timestamp of scan end
    error: str | None = None                 # error message if state == "failed"

    @property
    def fetch_percent(self) -> int:
        if self.total_pages == 0:
            return 0
        return min(100, int(self.current_page * 100 / self.total_pages))

    @property
    def process_percent(self) -> int:
        if self.fetched_count == 0:
            return 0
        return min(100, int(self.processed_count * 100 / self.fetched_count))

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "fetched_count": self.fetched_count,
            "total_count": self.total_count,
            "processed_count": self.processed_count,
            "alerts_generated": self.alerts_generated,
            "fetch_percent": self.fetch_percent,
            "process_percent": self.process_percent,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


class ScanRunner:
    """Runs a scan and exposes live progress. Thread-safe."""

    def __init__(self, scan_fn: Callable[["ScanRunner"], None]) -> None:
        """scan_fn receives the runner so it can call .update_progress() etc."""
        self._scan_fn = scan_fn
        self._running = False
        self._lock = threading.Lock()
        self._progress = ScanProgress()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def progress(self) -> ScanProgress:
        return self._progress

    def update_progress(self, **kwargs) -> None:
        """Update fields on the current progress snapshot."""
        for key, value in kwargs.items():
            if hasattr(self._progress, key):
                setattr(self._progress, key, value)

    def run(self) -> None:
        """Run a scan synchronously. Skips if already running."""
        with self._lock:
            if self._running:
                logger.info("Scan already running, skipping")
                return
            self._running = True

        # Reset progress for this run
        self._progress = ScanProgress(
            state="fetching",
            started_at=_now_iso(),
        )

        try:
            self._scan_fn(self)
            self._progress.state = "completed"
        except Exception as e:
            logger.exception("Scan failed with error")
            self._progress.state = "failed"
            self._progress.error = str(e)
        finally:
            self._progress.finished_at = _now_iso()
            with self._lock:
                self._running = False

    def run_async(self) -> None:
        """Run a scan in a background thread. Returns immediately."""
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
