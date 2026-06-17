"""FastAPI application entry point for the Hobbyland monitor."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import alerts as alerts_router
from .api import images as images_router
from .api import products as products_router
from .api import scan as scan_router
from .api import watchlist as watchlist_router
from .client.hobbylande import HobbylandeClient
from .config import load_config
from .db.engine import get_session, init_engine
from .notifier.factory import create_notifiers
from .repository.alert_repo import AlertRepository
from .repository.product_repo import ProductRepository
from .repository.watchlist_repo import WatchlistRepository
from .scheduler.jobs import create_scheduler
from .service.exchange_rate import ExchangeRateService
from .service.monitor import MonitorService
from .service.scan_runner import ScanRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Load config
config = load_config("config/config.yaml")

# Initialize engine singleton
engine = init_engine(config.database.path)
logger.info("Database ready at %s", config.database.path)

# Build the API client and notifiers (long-lived)
client = HobbylandeClient(
    base_url=config.api.base_url,
    request_body=config.api.request_body,
    timeout=config.api.timeout,
    page_delay=config.api.page_delay,
)
notifiers = create_notifiers(config)


def _run_scan_cycle(runner=None) -> None:
    """Execute a single scan with its own DB session."""
    with get_session(engine) as session:
        product_repo = ProductRepository(session)
        watchlist_repo = WatchlistRepository(session)
        alert_repo = AlertRepository(session)
        monitor = MonitorService(
            client=client,
            product_repo=product_repo,
            watchlist_repo=watchlist_repo,
            alert_repo=alert_repo,
            notifiers=notifiers,
            alert_config=config.alerts,
        )
        monitor.run_scan(runner=runner)


def _refresh_exchange_rate() -> None:
    """Refresh JPY/HKD exchange rate if stale."""
    with get_session(engine) as session:
        ExchangeRateService(session).refresh_jpy_hkd_if_stale(max_age_minutes=60)


# Build the scan runner and inject into the scan router
scan_runner = ScanRunner(_run_scan_cycle)
scan_router.set_scan_runner(scan_runner)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("🤖 Starting Hobbyland Monitor (FastAPI)")

    # Run initial scan in background (don't block startup)
    logger.info("Triggering initial scan in background...")
    scan_runner.run_async()

    # Refresh exchange rate once on startup (local DB cache; then hourly)
    try:
        _refresh_exchange_rate()
    except Exception:
        logger.exception("Initial exchange rate refresh failed")

    # Start the scheduler in the background
    scheduler = create_scheduler(scan_runner.run, config.scheduler, exchange_rate_fn=_refresh_exchange_rate)
    scheduler.start()
    logger.info(
        "Scheduler running. Daily scan at %s (%s)",
        config.scheduler.scan_time, config.scheduler.timezone,
    )

    yield  # App runs here

    # Shutdown
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)


# Create FastAPI app
app = FastAPI(
    title="Hobbyland Gundam Monitor",
    description="高达模型库存监控系统",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for development (frontend on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(products_router.router, prefix="/api")
app.include_router(watchlist_router.router, prefix="/api")
app.include_router(alerts_router.router, prefix="/api")
app.include_router(images_router.router, prefix="/api")
app.include_router(scan_router.router, prefix="/api")


# Serve static frontend if built
_static_dir = Path("static")
if _static_dir.exists() and (_static_dir / "index.html").exists():
    # Mount the assets sub-directory (Vite builds put hashed files here)
    if (_static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(_static_dir / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Catch-all: serve index.html for Vue Router (HTML5 history mode)."""
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        # If the path is a real file in static/, serve it
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html (SPA routing)
        return FileResponse(str(_static_dir / "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "message": "Hobbyland Monitor API is running",
            "frontend": "not_built",
            "hint": "Build the frontend with `cd frontend && npm run build`",
            "docs": "/docs",
        }


def main() -> None:
    """Run the app with uvicorn (used by `python -m src.main`)."""
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
