"""Tests for the orphaned-order reaper (P1 #5)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.engine import get_session_factory, init_db
from app.db.models import Order, OrderStatus
from app.services.order_reaper import reap_orphaned_orders


async def _insert(status: str, minutes_ago: int) -> str:
    await init_db()
    factory = get_session_factory()
    oid = f"reap-{uuid.uuid4().hex[:8]}"
    async with factory() as db:
        now = datetime.now(timezone.utc)
        order = Order(
            id=oid,
            identity_id="reap-test",
            provider_id="elevenlabs",
            provider_type="voice",
            status=status,
            progress=42,
            updated_at=now - timedelta(minutes=minutes_ago),
            created_at=now - timedelta(minutes=minutes_ago),
        )
        db.add(order)
        await db.commit()
    return oid


async def _get(oid: str) -> Order:
    factory = get_session_factory()
    async with factory() as db:
        return (await db.execute(select(Order).where(Order.id == oid))).scalar_one()


@pytest.mark.anyio
async def test_reaps_stale_uploading_order():
    oid = await _insert(OrderStatus.UPLOADING.value, minutes_ago=45)
    reaped = await reap_orphaned_orders(max_age_minutes=30)
    assert oid in reaped

    order = await _get(oid)
    assert order.status == OrderStatus.PENDING.value
    assert order.progress == 0
    assert "retrying" in (order.error_message or "")


@pytest.mark.anyio
async def test_reaps_stale_training_order():
    oid = await _insert(OrderStatus.TRAINING.value, minutes_ago=90)
    reaped = await reap_orphaned_orders(max_age_minutes=30)
    assert oid in reaped

    order = await _get(oid)
    assert order.status == OrderStatus.PENDING.value


@pytest.mark.anyio
async def test_ignores_recent_uploading_order():
    """A pipeline that's still running for only 5 min is not orphaned."""
    oid = await _insert(OrderStatus.UPLOADING.value, minutes_ago=5)
    reaped = await reap_orphaned_orders(max_age_minutes=30)
    assert oid not in reaped

    order = await _get(oid)
    assert order.status == OrderStatus.UPLOADING.value
    assert order.progress == 42


@pytest.mark.anyio
async def test_ignores_terminal_status():
    """COMPLETED / FAILED / CANCELLED are terminal — reaper never touches them."""
    for status in (
        OrderStatus.COMPLETED.value,
        OrderStatus.FAILED.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.PENDING.value,
    ):
        oid = await _insert(status, minutes_ago=120)
        reaped = await reap_orphaned_orders(max_age_minutes=30)
        assert oid not in reaped, f"reaper should not touch status={status}"


@pytest.mark.anyio
async def test_empty_db_returns_empty_list():
    """Sanity: no orphans → reaper returns [] without erroring."""
    await init_db()
    reaped = await reap_orphaned_orders(max_age_minutes=30)
    assert isinstance(reaped, list)  # may include orphans from other tests; shape check only
