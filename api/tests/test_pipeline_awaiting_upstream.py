"""Tests for the pipeline's 'awaiting upstream' state.

P0 #8 from GAP_ANALYSIS.md: the pipeline used to raise
`RuntimeError("Windy Pro has not yet exposed bundle audio ...")` which
marked orders as FAILED with a cryptic message. Users saw a broken clone
for a dependency they had no control over.

Now the pipeline transitions to AWAITING_UPSTREAM with a friendly message,
and /api/v1/orders surfaces it.
"""

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.engine import get_session_factory, init_db
from app.db.models import Order, OrderStatus
from app.services import data_fetcher
from app.services.clone_pipeline import run_elevenlabs_pipeline


def _patch_bundles(monkeypatch, *, unavailable: bool, bundles: list | None = None):
    """Force data_fetcher.fetch_training_bundles to return a given shape."""
    async def fake(identity_id, jwt_token=None, db=None):
        from app.services.data_fetcher import BundlesResult, TrainingBundle
        return BundlesResult(
            bundles=bundles or [],
            unavailable=unavailable,
            stale=False,
            fetched_at=None,
        )
    monkeypatch.setattr(data_fetcher, "fetch_training_bundles", fake)
    # clone_pipeline imports by name, patch the reference there too.
    from app.services import clone_pipeline as cp
    monkeypatch.setattr(cp, "fetch_training_bundles", fake)


@pytest.fixture
def live_keys(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "dev_mode", False)
    monkeypatch.setattr(s, "elevenlabs_api_key", "test-xi-key")
    return s


@pytest.mark.anyio
async def test_pipeline_marks_awaiting_upstream_when_no_recordings(monkeypatch, live_keys):
    await init_db()
    factory = get_session_factory()
    identity_id = f"no-recs-{uuid.uuid4().hex[:6]}"

    async with factory() as db:
        order = Order(
            identity_id=identity_id, provider_id="elevenlabs",
            provider_type="voice", status=OrderStatus.PENDING.value, progress=0,
        )
        db.add(order); await db.commit(); await db.refresh(order)
        order_id = order.id

    _patch_bundles(monkeypatch, unavailable=True)

    await run_elevenlabs_pipeline(
        order_id=order_id, identity_id=identity_id,
        display_name="Test", jwt_token="t",
    )

    async with factory() as db:
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.AWAITING_UPSTREAM.value
        assert "Make a few recordings" in (order.error_message or "")


@pytest.mark.anyio
async def test_pipeline_marks_awaiting_upstream_when_pro_audio_missing(monkeypatch, live_keys):
    """User has recordings (metadata) but Pro hasn't shipped the audio endpoint."""
    await init_db()
    factory = get_session_factory()
    identity_id = f"no-audio-{uuid.uuid4().hex[:6]}"

    async with factory() as db:
        order = Order(
            identity_id=identity_id, provider_id="elevenlabs",
            provider_type="voice", status=OrderStatus.PENDING.value, progress=0,
        )
        db.add(order); await db.commit(); await db.refresh(order)
        order_id = order.id

    from app.services.data_fetcher import TrainingBundle
    bundle = TrainingBundle(
        bundle_id="b1", audio_duration_seconds=60, video_duration_seconds=0,
        word_count=100, quality_score=90, quality_tier="excellent",
        created_at="2026-04-16T10:00:00Z",
    )
    _patch_bundles(monkeypatch, unavailable=False, bundles=[bundle])

    await run_elevenlabs_pipeline(
        order_id=order_id, identity_id=identity_id,
        display_name="Test", jwt_token="t",
    )

    async with factory() as db:
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.AWAITING_UPSTREAM.value
        assert "audio export yet" in (order.error_message or "")


@pytest.mark.anyio
async def test_get_order_surfaces_waiting_on_pro(client):
    """GET /api/v1/orders/{id} returns a friendly estimated_completion."""
    factory = get_session_factory()
    async with factory() as db:
        order = Order(
            identity_id="dev-mock-user-001",
            provider_id="elevenlabs",
            provider_type="voice",
            status=OrderStatus.AWAITING_UPSTREAM.value,
            progress=0,
            error_message="Your recordings are ready, but Windy Pro ...",
        )
        db.add(order); await db.commit(); await db.refresh(order)
        order_id = order.id

    resp = await client.get(f"/api/v1/orders/{order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_upstream"
    assert data["estimated_completion"] == "Waiting on Windy Pro"
    assert "Windy Pro" in data["error_message"]
