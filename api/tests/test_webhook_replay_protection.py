"""Tests for P1 #8: timestamped webhook HMAC with backward-compatible rollout.

Covers:
  * Legacy (body-only) HMAC still accepted by default.
  * Timestamp-prefixed HMAC accepted when header present + fresh.
  * Stale timestamp → 403 even with a valid signature.
  * Future-dated timestamp → 403 (symmetric window).
  * WEBHOOK_REQUIRE_TIMESTAMP=true refuses missing-timestamp payloads.
  * Legacy body-only HMAC refused when strict mode + timestamp header present.
"""

import hashlib
import hmac as hmac_mod
import json
import time
import uuid

import pytest

from app.config import get_settings


WEBHOOK_SECRET = "test-windy-pro-webhook-secret"


def _sign_legacy(body: bytes) -> str:
    return hmac_mod.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _sign_timestamped(body: bytes, timestamp: str) -> str:
    signed = f"{timestamp}.".encode() + body
    return hmac_mod.new(WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "windy_pro_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(get_settings(), "webhook_require_timestamp", False)
    monkeypatch.setattr(get_settings(), "webhook_max_timestamp_age_seconds", 300)
    return WEBHOOK_SECRET


def _id_body(tag: str) -> bytes:
    return json.dumps({"identity_id": f"{tag}-{uuid.uuid4().hex[:8]}", "display_name": tag}).encode()


@pytest.mark.anyio
async def test_legacy_hmac_still_works_by_default(client, webhook_secret):
    body = _id_body("legacy")
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": _sign_legacy(body)},
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_timestamped_hmac_accepted_when_fresh(client, webhook_secret):
    body = _id_body("fresh")
    ts = str(int(time.time()))
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={
            "X-Windy-Pro-Signature": _sign_timestamped(body, ts),
            "X-Windy-Pro-Timestamp": ts,
        },
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_stale_timestamp_rejected_even_with_valid_sig(client, webhook_secret):
    """An attacker re-sending yesterday's body+sig must lose."""
    body = _id_body("stale")
    ts = str(int(time.time()) - 3600)  # 1 hour old — outside 5-min window
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={
            "X-Windy-Pro-Signature": _sign_timestamped(body, ts),
            "X-Windy-Pro-Timestamp": ts,
        },
    )
    assert resp.status_code == 403
    assert "Stale" in resp.json()["detail"]


@pytest.mark.anyio
async def test_future_timestamp_rejected(client, webhook_secret):
    """Symmetric window — tomorrow's timestamp also rejected."""
    body = _id_body("future")
    ts = str(int(time.time()) + 3600)
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={
            "X-Windy-Pro-Signature": _sign_timestamped(body, ts),
            "X-Windy-Pro-Timestamp": ts,
        },
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_malformed_timestamp_rejected(client, webhook_secret):
    body = _id_body("malformed")
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={
            "X-Windy-Pro-Signature": _sign_legacy(body),
            "X-Windy-Pro-Timestamp": "not-a-timestamp",
        },
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_strict_mode_refuses_missing_timestamp(client, webhook_secret, monkeypatch):
    """WEBHOOK_REQUIRE_TIMESTAMP=true rejects legacy-only senders."""
    monkeypatch.setattr(get_settings(), "webhook_require_timestamp", True)

    body = _id_body("strict")
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={"X-Windy-Pro-Signature": _sign_legacy(body)},
    )
    assert resp.status_code == 403
    assert "WEBHOOK_REQUIRE_TIMESTAMP" in resp.json()["detail"]


@pytest.mark.anyio
async def test_strict_mode_refuses_legacy_hmac_even_with_timestamp(
    client, webhook_secret, monkeypatch
):
    """In strict mode, a body-only HMAC alongside a timestamp header is still refused."""
    monkeypatch.setattr(get_settings(), "webhook_require_timestamp", True)

    body = _id_body("mixed")
    ts = str(int(time.time()))
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={
            "X-Windy-Pro-Signature": _sign_legacy(body),  # body-only sig
            "X-Windy-Pro-Timestamp": ts,
        },
    )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_strict_mode_accepts_full_scheme(client, webhook_secret, monkeypatch):
    """Strict mode accepts fresh timestamp + timestamped HMAC."""
    monkeypatch.setattr(get_settings(), "webhook_require_timestamp", True)

    body = _id_body("strict-ok")
    ts = str(int(time.time()))
    resp = await client.post(
        "/api/v1/webhooks/identity/created",
        content=body,
        headers={
            "X-Windy-Pro-Signature": _sign_timestamped(body, ts),
            "X-Windy-Pro-Timestamp": ts,
        },
    )
    assert resp.status_code == 200
