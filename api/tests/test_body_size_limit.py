"""Tests for BodySizeLimitMiddleware (P1 #6).

Wave-7 probe: POST /api/v1/orders accepted a 10 MB body. Now it's capped.
"""

import pytest


@pytest.mark.anyio
async def test_body_under_limit_passes(client):
    body = {"provider_id": "elevenlabs", "clone_type": "voice"}
    resp = await client.post("/api/v1/orders", json=body)
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_10mb_body_rejected_at_default_cap(client):
    """The original Wave-7 repro: 10 MB body on /api/v1/orders → 413."""
    huge = "A" * (10 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/orders",
        content=f'{{"provider_id":"elevenlabs","clone_type":"voice","x":"{huge}"}}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_invalid_content_length_rejected(client):
    resp = await client.post(
        "/api/v1/orders",
        content='{"provider_id":"elevenlabs","clone_type":"voice"}',
        headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
    )
    assert resp.status_code == 400
