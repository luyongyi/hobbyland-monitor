"""Image proxy with persistent on-disk cache.

Product images on static.hobbylandeshop.com almost never change once published,
so we fetch each one once and cache it under data/images/ forever. After the
first request for a given path, all subsequent requests are served from local
disk and the upstream is never contacted.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["images"])

UPSTREAM_BASE = "https://static.hobbylandeshop.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.hobbylandeshop.com/",
}

# Persistent cache directory (lives in the same place as the SQLite DB).
CACHE_DIR = Path("data/images")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Map common extensions to content types.
_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# Allow only safe path segments — no traversal, no shell metacharacters.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._\-]+$")


def _safe_path(path: str) -> Path | None:
    """Validate the requested path and return the resolved on-disk cache path.

    Returns None if the path is unsafe. We require every segment to match
    a strict whitelist so neither "..", absolute paths, nor URL-encoded
    traversal can escape the cache directory.
    """
    if not path or path.startswith("/") or ".." in path.split("/"):
        return None
    segments = path.split("/")
    for seg in segments:
        if not _SAFE_SEGMENT.match(seg):
            return None
    # Limit total path length to keep filesystems happy.
    if len(path) > 256:
        return None
    return CACHE_DIR / path


def _content_type_for(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


@router.get("/images/{path:path}")
async def proxy_image(path: str) -> Response:
    """Serve a product image from local cache, fetching it once if needed."""
    cache_path = _safe_path(path)
    if cache_path is None:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Cache hit — serve from disk, never touch upstream.
    if cache_path.is_file():
        return FileResponse(
            str(cache_path),
            media_type=_content_type_for(cache_path),
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    # Cache miss — fetch from upstream exactly once and persist.
    upstream_url = f"{UPSTREAM_BASE}/{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(upstream_url, headers=DEFAULT_HEADERS)
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch image %s: %s", upstream_url, e)
        raise HTTPException(status_code=502, detail="Failed to fetch image")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Upstream returned non-200")

    # Atomically write the cache file (write to tmp, then rename).
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    try:
        tmp_path.write_bytes(resp.content)
        tmp_path.replace(cache_path)
    except OSError as e:
        logger.warning("Failed to cache image %s: %s", cache_path, e)
        # Still serve the bytes we already have, even if caching failed.

    content_type = resp.headers.get("content-type") or _content_type_for(cache_path)
    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
