"""FastAPI dependency injection."""

from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from ..db import engine as engine_module
from ..db.engine import get_session


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for a single request."""
    if engine_module.engine is None:
        raise RuntimeError("Database engine not initialized")
    with get_session(engine_module.engine) as session:
        yield session
