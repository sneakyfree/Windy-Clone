"""Tests for /api/v1/webhooks/identity/created."""

import hashlib
import hmac
import json
import uuid

import pytest

from app.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import UserPreference
from sqlalchemy import select


WEBHOOK_SECRET = "test-windy-pro-webhook-secret"


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_secret(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "windy_pro_webhook_secret", WEBHOOK_SECRET)
    return WEBHOOK_SECRET


@pytest.mark.anyio
async def test_identity_webhook_rejects_missing_signature(client, webhook_secret):
    body = json.dumps({"identity_id": "id-x", "display_name": "X"}).encode()
    resp = await client.post("/api/v1/webhooks/identity/created", content=body)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_identity_webhook_rejects_bad_signature(client, webhook_secret):
    body = json.dumps({"identity_id": "id-x", "display_name": "X"}).encode()
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": "deadbeef"},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_identity_webhook_provisions_user_preference(client, webhook_secret):
    identity_id = f"id-new-{uuid.uuid4().hex[:8]}"
    body = json.dumps(
        {"identity_id": identity_id, "display_name": "Grant", "email": "grant@pro.com"}
    ).encode()
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": _sign(body)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "provisioned"
    assert data["dashboard_url"].endswith("/legacy")

    factory = get_session_factory()
    async with factory() as session:
        pref = (
            await session.execute(
                select(UserPreference).where(UserPreference.identity_id == identity_id)
            )
        ).scalar_one()
        assert pref.default_provider == ""  # Phase 1: no provider yet


@pytest.mark.anyio
async def test_identity_webhook_is_idempotent(client, webhook_secret):
    body = json.dumps({"identity_id": f"id-dup-{uuid.uuid4().hex[:8]}", "display_name": "Dup"}).encode()
    sig = _sign(body)
    first = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": sig},
    )
    second = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": sig},
    )
    assert first.json()["status"] == "provisioned"
    assert second.json()["status"] == "existing"


@pytest.mark.anyio
async def test_identity_webhook_accepts_sha256_prefix(client, webhook_secret):
    body = json.dumps({"identity_id": f"id-prefix-{uuid.uuid4().hex[:8]}", "display_name": "P"}).encode()
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": f"sha256={_sign(body)}"},
    )
    assert resp.status_code == 200


# ────────────────────── Eternitas trust.changed webhook ─────────────────────


ETERNITAS_SECRET = "test-eternitas-webhook-secret"


def _sign_eternitas(body: bytes) -> str:
    return hmac.new(ETERNITAS_SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def eternitas_webhook_secret(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "eternitas_webhook_secret", ETERNITAS_SECRET)
    return ETERNITAS_SECRET


@pytest.mark.anyio
async def test_trust_changed_rejects_bad_signature(client, eternitas_webhook_secret):
    body = json.dumps({"event": "trust.changed", "passport": "ET26-XXXX"}).encode()
    resp = await client.post(
        "/api/v1/webhooks/trust/changed",
        content=body,
        headers={"X-Eternitas-Signature": "deadbeef"},
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_trust_changed_invalidates_cache(client, eternitas_webhook_secret, monkeypatch):
    """Webhook delivery must flush the local cache so the next gate re-fetches."""
    from app.services import trust_client
    from app.services.trust_client import TrustLevel

    passport = f"ET26-FLIP-{uuid.uuid4().hex[:6]}"
    # Seed cache with a stale CLEARED entry.
    trust_client._cache[passport] = (trust_client.time.monotonic() + 999, TrustLevel.CLEARED)
    assert trust_client._cache_get(passport) is TrustLevel.CLEARED

    body = json.dumps(
        {
            "event": "trust.changed",
            "event_type": "trust.changed",
            "passport": passport,
            "reason": "integrity_band: good→fair",
            "old_band": "good",
            "new_band": "fair",
        }
    ).encode()
    resp = await client.post(
        "/api/v1/webhooks/trust/changed",
        content=body,
        headers={"X-Eternitas-Signature": _sign_eternitas(body)},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "invalidated", "passport": passport}
    assert trust_client._cache_get(passport) is None
