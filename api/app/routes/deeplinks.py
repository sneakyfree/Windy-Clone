"""Deep-link resolver for the `windyclone://` scheme.

Mirrors the frontend parser in `web/src/lib/parseWindyCloneUrl.ts` and the
windy-pro-mobile sanitization pattern (_layout.tsx:288-444): reject path
traversal, restrict to SAFE_ID_RE, cap length at 128.

Agents and the Windy Pro Electron shell call this to validate a deep link
*before* redirecting the user, so a malformed link never results in a
client-side navigation we can't audit.
"""

import re
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

SCHEME = "windyclone"
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_ID_LEN = 128
MAX_URL_LEN = 512


def _sanitize_id(raw: str) -> str | None:
    cleaned = raw.strip()
    if not cleaned or len(cleaned) > MAX_ID_LEN:
        return None
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        return None
    if not SAFE_ID_RE.match(cleaned):
        return None
    return cleaned


def _resolve(url: str) -> dict | None:
    """Return {route, params} for a valid windyclone:// URL, else None."""
    if not url or len(url) > MAX_URL_LEN:
        return None

    parts = urlsplit(url)
    if parts.scheme.lower() != SCHEME:
        return None

    # urlsplit treats `windyclone://dashboard` as `netloc=dashboard, path=""`.
    # Normalise so `netloc/path` segments read the same way regardless.
    combined = parts.netloc
    if parts.path:
        combined = f"{combined}/{parts.path.lstrip('/')}"
    segments = [s for s in combined.split("/") if s]
    if not segments:
        return None

    head = segments[0].lower()

    if head == "dashboard" and len(segments) == 1:
        return {"route": "/legacy", "params": {}}

    if head == "discover" and len(segments) == 1:
        return {"route": "/discover", "params": {}}

    if head == "studio" and len(segments) == 2:
        clone_id = _sanitize_id(segments[1])
        if not clone_id:
            return None
        return {"route": f"/studio/clone/{clone_id}", "params": {"cloneId": clone_id}}

    if head == "order" and len(segments) == 2:
        order_id = _sanitize_id(segments[1])
        if not order_id:
            return None
        return {"route": f"/order/{order_id}", "params": {"orderId": order_id}}

    return None


@router.get("/resolve")
async def resolve_deeplink(
    url: str = Query(..., description="A windyclone:// deep link to resolve."),
):
    """Resolve a `windyclone://` URL to an internal route.

    Returns 400 on unknown scheme, unknown path, malformed segments, or any
    input that fails path-traversal / character-set checks.
    """
    resolved = _resolve(url)
    if resolved is None:
        raise HTTPException(status_code=400, detail="Invalid or unsupported windyclone:// URL")
    return {"scheme": SCHEME, **resolved}
