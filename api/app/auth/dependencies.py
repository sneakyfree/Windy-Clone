"""FastAPI auth dependencies — inject current user into routes."""

from fastapi import Depends, HTTPException, Header, status
from pydantic import BaseModel

from ..config import get_settings
from .jwks import validate_token, extract_identity_id


class CurrentUser(BaseModel):
    """Authenticated user extracted from JWT."""
    identity_id: str
    email: str | None = None
    display_name: str | None = None
    raw_token: str | None = None  # For forwarding to Windy Pro


# ── Dev-mode mock user ──
_DEV_USER = CurrentUser(
    identity_id="dev-mock-user-001",
    email="grant@windypro.com",
    display_name="Grant",
    raw_token=None,
)


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> CurrentUser:
    """
    Validate the Bearer token from Windy Pro and return the current user.

    In dev mode (DEV_MODE=True), if no token is provided, returns a mock user
    so the frontend can be developed without a real Windy Pro connection.
    """
    settings = get_settings()

    # ── No auth header ──
    if not authorization:
        if settings.dev_mode:
            return _DEV_USER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Sign in via Windy Pro.",
        )

    # ── Parse Bearer token ──
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
        )

    token = parts[1]

    try:
        payload = validate_token(token)
    except Exception as exc:
        if settings.dev_mode:
            # In dev mode, gracefully fall back to mock user on auth failure
            return _DEV_USER
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
        )

    identity_id = extract_identity_id(payload)
    if not identity_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing identity claim.",
        )

    return CurrentUser(
        identity_id=identity_id,
        email=payload.get("email"),
        display_name=payload.get("display_name", payload.get("name")),
        raw_token=token,
    )
