"""Webhook routes — /api/v1/webhooks/*

Inbound notifications from Windy Pro (identity lifecycle) and providers.
HMAC-SHA256 over the raw body, hex-digest, constant-time compare.
Same shape as Windy Mail's Eternitas revocation webhook.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.engine import get_db
from ..db.models import UserPreference
from ..services import trust_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_hmac(body: bytes, signature: str | None, secret: str) -> bool:
    """Generic HMAC-SHA256 verifier (shared shape across webhook sources)."""
    if not secret or not signature:
        return False
    provided = signature.split("=", 1)[1] if signature.startswith("sha256=") else signature
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


class IdentityCreatedPayload(BaseModel):
    """Body emitted by Windy Pro when a new unified identity is provisioned."""
    identity_id: str
    display_name: str | None = None
    email: str | None = None
    source_product: str | None = None
    timestamp: str | None = None


def _verify_windy_pro_signature(body: bytes, signature: str | None) -> bool:
    """HMAC-SHA256 verification against WINDY_PRO_WEBHOOK_SECRET."""
    return _verify_hmac(body, signature, get_settings().windy_pro_webhook_secret)


@router.post("/identity/created", status_code=status.HTTP_200_OK)
async def handle_identity_created(
    request: Request,
    x_windy_pro_signature: str | None = Header(default=None, alias="X-Windy-Pro-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Provision a Clone user on Windy Pro identity creation.

    Creates (idempotently) a UserPreference row on the Phase 1 "Legacy Dashboard"
    tier — no provider selected yet, just tracking so the user lands on an
    initialised dashboard the first time they sign in.
    """
    body = await request.body()

    if not _verify_windy_pro_signature(body, x_windy_pro_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Windy-Pro-Signature",
        )

    try:
        payload = IdentityCreatedPayload(**json.loads(body))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed payload: {exc}",
        )

    settings = get_settings()
    dashboard_url = f"{settings.dashboard_url.rstrip('/')}/legacy"

    existing = await db.execute(
        select(UserPreference).where(UserPreference.identity_id == payload.identity_id)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("identity.created webhook: existing user %s", payload.identity_id)
        return {"status": "existing", "dashboard_url": dashboard_url}

    pref = UserPreference(
        identity_id=payload.identity_id,
        default_provider="",  # Phase 1: no provider chosen yet
        email_notifications=True,
        push_notifications=False,
    )
    db.add(pref)
    await db.commit()

    logger.info("identity.created webhook: provisioned user %s", payload.identity_id)
    return {"status": "provisioned", "dashboard_url": dashboard_url}


# ────────────────────────── Eternitas trust.changed ────────────────────────


class TrustChangedPayload(BaseModel):
    """Matches eternitas/docs/trust-api.md `trust.changed` envelope.

    Either the band pair or the clearance pair is populated (not always both).
    We only use `passport` / `passport_id` to invalidate our local cache — the
    next gated request does a fresh GET /api/v1/trust/{passport}.
    """
    event: str | None = None
    event_type: str | None = None
    passport: str | None = None
    passport_id: str | None = None
    reason: str | None = None
    old_band: str | None = None
    new_band: str | None = None
    old_clearance: str | None = None
    new_clearance: str | None = None
    timestamp: str | None = None


@router.post("/trust/changed", status_code=status.HTTP_200_OK)
async def handle_trust_changed(
    request: Request,
    x_eternitas_signature: str | None = Header(default=None, alias="X-Eternitas-Signature"),
) -> dict[str, str]:
    """Invalidate the local trust cache for the passport in the webhook body.

    Per the contract, we must NOT wait for TTL — the whole point of the
    webhook is to close the stale-cache window. We drop the entry; the next
    gated request re-fetches from Eternitas.
    """
    body = await request.body()

    if not _verify_hmac(body, x_eternitas_signature, get_settings().eternitas_webhook_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    try:
        payload = TrustChangedPayload(**json.loads(body))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed payload: {exc}")

    passport = payload.passport or payload.passport_id
    if not passport:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing passport")

    trust_client.invalidate(passport)
    logger.info(
        "trust.changed: invalidated %s (reason=%s, band=%s→%s, clearance=%s→%s)",
        passport,
        payload.reason,
        payload.old_band,
        payload.new_band,
        payload.old_clearance,
        payload.new_clearance,
    )
    return {"status": "invalidated", "passport": passport}
