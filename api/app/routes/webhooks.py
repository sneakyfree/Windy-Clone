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
import time

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


def _timestamp_is_fresh(timestamp: str | None, max_age_seconds: int) -> bool:
    """True iff `timestamp` is a parseable epoch-seconds string within the window."""
    if timestamp is None:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    return abs(int(time.time()) - ts) <= max_age_seconds


def _verify_hmac(
    body: bytes,
    signature: str | None,
    secret: str,
    *,
    timestamp: str | None = None,
) -> bool:
    """Constant-time HMAC-SHA256 verifier with optional timestamp-prefixed input.

    Supports two schemes so a receiver can land ahead of senders:

      * **Timestamp scheme** (preferred) — sender includes `X-*-Timestamp` and
        signs `{timestamp}.{body}`. Replay-resistant: a captured (body, sig)
        can't be re-sent after the freshness window without the sender's key.
      * **Legacy scheme** — sender signs `body` only. Accepted as a fallback
        when the timestamp header is absent, or when the timestamped HMAC
        doesn't match (so senders can adopt at their own pace).

    Set `WEBHOOK_REQUIRE_TIMESTAMP=true` to refuse the legacy path. Until
    every sender has adopted the timestamp header, leave it False.
    """
    if not secret or not signature:
        return False
    provided = signature.split("=", 1)[1] if signature.startswith("sha256=") else signature

    # 1) Timestamp scheme — only attempt when we actually have a timestamp.
    if timestamp is not None:
        signed_input = f"{timestamp}.".encode() + body
        expected = hmac.new(secret.encode(), signed_input, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, provided):
            return True

    # 2) Legacy scheme — refused when strict mode is on.
    if get_settings().webhook_require_timestamp:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def _check_timestamp_freshness_or_403(timestamp: str | None, header_name: str) -> None:
    """Common enforcement used by both webhook handlers.

    - If the timestamp header is present, it MUST parse and be fresh — otherwise
      an attacker could attach a far-future timestamp to a captured body+sig.
    - If it's absent and `WEBHOOK_REQUIRE_TIMESTAMP=true`, refuse up front.
    - If it's absent otherwise, fall through (legacy senders still work).
    """
    settings = get_settings()
    if timestamp is None:
        if settings.webhook_require_timestamp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing {header_name} (required when WEBHOOK_REQUIRE_TIMESTAMP=true)",
            )
        return

    if not _timestamp_is_fresh(timestamp, settings.webhook_max_timestamp_age_seconds):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Stale or malformed {header_name}",
        )


class IdentityCreatedPayload(BaseModel):
    """Body emitted by Windy Pro when a new unified identity is provisioned."""
    identity_id: str
    display_name: str | None = None
    email: str | None = None
    source_product: str | None = None
    timestamp: str | None = None


def _verify_windy_pro_signature(
    body: bytes, signature: str | None, timestamp: str | None = None
) -> bool:
    """HMAC-SHA256 verification against WINDY_PRO_WEBHOOK_SECRET."""
    return _verify_hmac(
        body, signature, get_settings().windy_pro_webhook_secret, timestamp=timestamp
    )


@router.post("/identity/created", status_code=status.HTTP_200_OK)
async def handle_identity_created(
    request: Request,
    x_windy_pro_signature: str | None = Header(default=None, alias="X-Windy-Pro-Signature"),
    x_windy_pro_timestamp: str | None = Header(default=None, alias="X-Windy-Pro-Timestamp"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Provision a Clone user on Windy Pro identity creation.

    Creates (idempotently) a UserPreference row on the Phase 1 "Legacy Dashboard"
    tier — no provider selected yet, just tracking so the user lands on an
    initialised dashboard the first time they sign in.
    """
    body = await request.body()

    _check_timestamp_freshness_or_403(x_windy_pro_timestamp, "X-Windy-Pro-Timestamp")
    if not _verify_windy_pro_signature(body, x_windy_pro_signature, x_windy_pro_timestamp):
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
    x_eternitas_timestamp: str | None = Header(default=None, alias="X-Eternitas-Timestamp"),
) -> dict[str, str]:
    """Invalidate the local trust cache for the passport in the webhook body.

    Per the contract, we must NOT wait for TTL — the whole point of the
    webhook is to close the stale-cache window. We drop the entry; the next
    gated request re-fetches from Eternitas.
    """
    body = await request.body()

    _check_timestamp_freshness_or_403(x_eternitas_timestamp, "X-Eternitas-Timestamp")
    if not _verify_hmac(
        body,
        x_eternitas_signature,
        get_settings().eternitas_webhook_secret,
        timestamp=x_eternitas_timestamp,
    ):
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
