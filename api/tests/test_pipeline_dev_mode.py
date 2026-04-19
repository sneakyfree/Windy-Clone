"""Tests for Wave-12 M-1: the dev-mode / missing-key pipeline short-circuit
must update the Order row instead of leaving it silently `pending`.

Prior behaviour (Wave-11 finding M-1): the pipeline bailed out early without
touching the order, so /my-clones showed "Pending 0%" forever. Now the
short-circuit leaves a status + error_message that the UI can render.
"""

import uuid

import pytest
from sqlalchemy import select

from app.db.engine import get_session_factory, init_db
from app.db.models import Order, OrderStatus
from app.config import get_settings
from app.services.clone_pipeline import run_elevenlabs_pipeline


async def _seed_order(identity_id: str = "dev-mock-user-001") -> str:
    """Insert a fresh pending ElevenLabs order and return its ID."""
    await init_db()
    factory = get_session_factory()
    order_id = str(uuid.uuid4())
    async with factory() as db:
        db.add(
            Order(
                id=order_id,
                identity_id=identity_id,
                provider_id="elevenlabs",
                provider_type="voice",
                status=OrderStatus.PENDING.value,
                progress=0,
            )
        )
        await db.commit()
    return order_id


async def _fetch_order(order_id: str) -> Order:
    factory = get_session_factory()
    async with factory() as db:
        row = (
            await db.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        # Detach from session for safe attribute reads after close.
        await db.refresh(row)
        return row


@pytest.mark.anyio
async def test_dev_mode_marks_order_awaiting_upstream_with_message(monkeypatch):
    """Wave-12 M-1 fix: dev-mode short-circuit updates the order, not silent."""
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_mode", True)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "")

    order_id = await _seed_order()
    await run_elevenlabs_pipeline(
        order_id=order_id,
        identity_id="dev-mock-user-001",
        display_name="Dev Test",
        jwt_token=None,
    )

    order = await _fetch_order(order_id)
    assert order.status == OrderStatus.AWAITING_UPSTREAM.value, (
        f"dev-mode order should be AWAITING_UPSTREAM, got {order.status}"
    )
    assert order.error_message, "dev-mode short-circuit must populate error_message"
    assert "dev mode" in order.error_message.lower()
    # The prior M-1 symptom was progress=0 on a status=pending row forever.
    # Progress-stays-0 is fine; the important thing is the status actually
    # moved off pending so the UI can render a banner.
    assert order.status != OrderStatus.PENDING.value


@pytest.mark.anyio
async def test_missing_key_non_dev_marks_order_failed(monkeypatch):
    """When ops forgets to wire ELEVENLABS_API_KEY in prod, orders FAIL with
    an explanation rather than silently pending."""
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "")

    order_id = await _seed_order()
    await run_elevenlabs_pipeline(
        order_id=order_id,
        identity_id="dev-mock-user-001",
        display_name="Unkeyed Test",
        jwt_token=None,
    )

    order = await _fetch_order(order_id)
    assert order.status == OrderStatus.FAILED.value
    assert order.error_message
    assert "elevenlabs_api_key" in order.error_message.lower()


@pytest.mark.anyio
async def test_vanished_order_still_no_crash(monkeypatch):
    """Regression guard: the pipeline must still tolerate an order that
    doesn't exist (never-existed / deleted), even after the Wave-12 status
    update branch."""
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_mode", True)

    # Should not raise, should not commit anything.
    await run_elevenlabs_pipeline(
        order_id="never-existed-99999",
        identity_id="dev-mock-user-001",
        display_name=None,
        jwt_token=None,
    )
